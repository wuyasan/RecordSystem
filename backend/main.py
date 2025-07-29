import os, uuid, shutil, pathlib, io
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles   # ← 新增 import
from sqlalchemy.orm import Session
from sqlalchemy import func, select, Numeric
from .database import Base, engine, SessionLocal
from . import schemas, crud, models
from decimal import Decimal
from fastapi.encoders import jsonable_encoder
from supabase import create_client, Client

# ---------- 数据库初始化 ----------
Base.metadata.create_all(bind=engine)

def supabase_public_url(path: str) -> str | None:
    """
    直接按规则拼接公开 URL，避免 SDK 返回结构差异带来的 None。
    需要：bucket 为 Public，或存储策略允许匿名读取。
    """
    if not (SUPABASE_URL and SUPABASE_BUCKET and path):
        return None
    base = SUPABASE_URL.rstrip("/")
    bucket = SUPABASE_BUCKET.strip("/")
    p = path.lstrip("/")
    return f"{base}/storage/v1/object/public/{bucket}/{p}"

BASE_DIR   = pathlib.Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)  

app = FastAPI(title="Figures Inventory API")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "figures")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- CORS（全开放，生产环境请收紧） ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------- DB Session 依赖 ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/figures/", response_model=schemas.Figure)
async def create_figure(
    manufacturer: str = Form(...),
    brand:        str = Form(...),
    character:    str = Form(...),
    model_name:   str = Form(...),
    cost_price:   float = Form(...),
    ip:           str | None = Form(None),

    quantity:     int  = Form(1),                 # ★ 新增：首次入库数量
    image:  UploadFile | None = File(None),

    db: Session = Depends(get_db),
):
    """ ① 若已存在同款 → 直接给库存 +quantity  
       ② 否则创建新品（必须上传图片），再写一条 IN 流水 """

    data = dict(
        manufacturer = manufacturer,
        brand        = brand,
        character    = character,
        model_name   = model_name,
        cost_price   = cost_price,
        ip           = ip,
    )

    # ───────── 1. 查重：存在则只加库存 ─────────
    fig = crud.get_same_figure(db, data)
    if fig:
        crud.add_movement(db, fig.id, quantity, "IN")

        stock, total_sales = (
            db.query(
                func.coalesce(func.sum(models.StockMovement.quantity), 0),
                func.coalesce(
                    func.sum(
                        models.StockMovement.sale_price *
                        (-models.StockMovement.quantity)
                    ),
                    0,
                ),
            )
            .filter(models.StockMovement.figure_id == fig.id)
            .one()
        )

        return (
            schemas.Figure.from_orm(fig)
            .copy(update={
                "qty":         int(stock),
                "total_sales": float(total_sales),
            })
        )

    # ───────── 2. 新品校验 ─────────
    if quantity <= 0:
        raise HTTPException(400, "新品数量必须大于 0")

    if image is None or not image.filename.strip():
        raise HTTPException(400, "新品必须上传图片")

    # ───────── 3. 保存图片（Supabase 优先，失败回本地） ─────────
    ext      = pathlib.Path(image.filename).suffix
    filename = f"{uuid.uuid4()}{ext}"
    image_url: str

    if supabase:
        bucket   = supabase.storage.from_(SUPABASE_BUCKET)
        obj_path = f"images/{filename}"

        # 1) 先尝试删除同名对象（若不存在也不会抛错）
        bucket.remove([obj_path])

        # 2) 再上传
        data_bytes = await image.read()
        rsp = bucket.upload(
            obj_path,
            io.BytesIO(data_bytes),
            {"content-type": image.content_type or "application/octet-stream"},
        )
        if rsp.get("error"):
            raise HTTPException(500, f"Supabase 上传失败: {rsp['error']['message']}")

        # 3) 取公网 URL
        image_url = bucket.get_public_url(obj_path)
        print(f"✓ Supabase 上传成功: {obj_path}\n  公网 URL: {image_url}")

    else:
        # -------- 本地 static/ ----------
        dest = STATIC_DIR / filename
        with dest.open("wb") as f:
            shutil.copyfileobj(image.file, f)
        image_url = f"/static/{filename}"
        print(f"✓ 本地保存图片到: {dest}")

        # ───────── 4. 创建 figure & 首次入库 ─────────
        fig = crud.create_figure(db, data, image_url)
        crud.add_movement(db, fig.id, quantity, "IN")

    return (
        schemas.Figure.from_orm(fig)
        .copy(update={
            "qty":         quantity,
            "total_sales": 0.0,
        })
    )

# ---------- 列表 + 选项 ----------
@app.get("/figures/", response_model=list[schemas.Figure])
def list_figures(db: Session = Depends(get_db)):
    rows = (
        db.query(
            models.Figure,
            func.coalesce(func.sum(models.StockMovement.quantity), 0).label("stock"),
            func.coalesce(func.sum(models.StockMovement.sale_price * (-models.StockMovement.quantity)
                                   .cast(Numeric)), 0).label("sales")  # 总销售额
        )
        .outerjoin(models.StockMovement)
        .group_by(models.Figure.id)
        .all()
    )
    return [
        schemas.Figure.from_orm(fig).copy(update={
            "qty": stock,
            "total_sales": float(sales)
        })
        for fig, stock, sales in rows
    ]

# ★ 新增：一次性把筛选选项给前端
@app.get("/filters")
def get_filters(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            models.Figure.manufacturer,
            models.Figure.brand,
            models.Figure.character,
            models.Figure.model_name,
            models.Figure.ip,
        ).distinct()
    ).all()

    if rows:
        manu, brand, chara, model, ip_vals = zip(*rows)
    else:
        manu = brand = chara = model = ip_vals = []

    return {
        "manufacturer": sorted(set(manu)),
        "brand":        sorted(set(brand)),
        "character":    sorted(set(chara)),
        "model_name":   sorted(set(model)),
        "ip":           sorted(set(ip_vals)),
    }
# ---------- 销售明细 ----------
@app.get("/figures/{fig_id}/sales")
def figure_sales(fig_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(
            models.StockMovement.quantity,
            models.StockMovement.sale_price,
            models.StockMovement.moved_at
        )
        .filter(models.StockMovement.figure_id == fig_id,
                models.StockMovement.movement_type == "OUT")
        .order_by(models.StockMovement.moved_at.desc())
        .all()
    )
    data = [
        {
            "quantity":   abs(r.quantity),                            # 负数 → 正数
            "sale_price": float(r.sale_price) if isinstance(r.sale_price, Decimal) else r.sale_price,
            "moved_at":   r.moved_at,
        }
        for r in rows
    ]
    return jsonable_encoder(data)

# ---------- 删除 ----------
@app.delete("/figures/{figure_id}")
def delete_figure(figure_id: int, db: Session = Depends(get_db)):
    crud.delete_figure(db, figure_id)
    return {"ok": True}

# ---------- 入库 / 出库 ----------
@app.post("/stock/outbound")
def outbound(mov: schemas.StockMovementCreate, db: Session = Depends(get_db)):
    if mov.quantity <= 0:
        raise HTTPException(400, "Quantity must be >0 for outbound")
    return crud.add_movement(db, mov.figure_id, -mov.quantity, "OUT", mov.sale_price)

@app.post("/stock/inbound")          # ← 这里不要写成 "/stock/inbound/"
def inbound(mov: schemas.StockMovementCreate, db: Session = Depends(get_db)):
    return crud.add_movement(db, mov.figure_id, mov.quantity, "IN")

# ---------- 修改 ----------
@app.put("/figures/{fig_id}", response_model=schemas.Figure)
def update_figure_api(
    fig_id: int,
    payload: schemas.FigureUpdate,
    db: Session = Depends(get_db),
):
    data    = payload.dict(exclude_unset=True)
    new_qty = data.pop("qty", None)   # 把 qty 拿出来，其余字段进 data
    fig = crud.update_figure(db, fig_id, data, new_qty)

    stock, total_sales = (
        db.query(
            func.coalesce(func.sum(models.StockMovement.quantity), 0),
            func.coalesce(
                func.sum(
                    models.StockMovement.sale_price *
                    (-models.StockMovement.quantity)
                ), 0
            ),
        )
        .filter(models.StockMovement.figure_id == fig_id)
        .one()
    )

    return schemas.Figure.from_orm(fig).copy(
        update={
            "qty":         int(stock),
            "total_sales": float(total_sales),
        }
    )