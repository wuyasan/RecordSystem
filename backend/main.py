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
    ip: str | None      = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    # ---- 业务字段：用 payload，不要用 data 防止被文件字节覆盖
    payload = dict(
        manufacturer=manufacturer,
        brand=brand,
        character=character,
        model_name=model_name,
        cost_price=cost_price,
        ip=ip,
    )

    # ---- 查重：完全相同则库存 +1 并返回最新汇总
    existed = crud.get_same_figure(db, payload)
    if existed:
        crud.add_movement(db, existed.id, 1, "IN")
        stock, total_sales = (
            db.query(
                func.coalesce(func.sum(models.StockMovement.quantity), 0),
                func.coalesce(
                    func.sum(
                        models.StockMovement.sale_price * (-models.StockMovement.quantity)
                    ),
                    0,
                ),
            )
            .filter(models.StockMovement.figure_id == existed.id)
            .one()
        )
        return schemas.Figure.from_orm(existed).copy(
            update={"qty": int(stock), "total_sales": float(total_sales)}
        )

    # ---- 新品必须有图片
    if image is None or not image.filename.strip():
        raise HTTPException(400, "新品必须上传图片")

    image_url: str | None = None

    # 优先走 Supabase
    if supabase:
        file_bytes = await image.read()
        ext = pathlib.Path(image.filename).suffix or ".jpg"
        key = f"images/{uuid.uuid4()}{ext}"

        # 上传
        up = supabase.storage.from_(SUPABASE_BUCKET).upload(key, file_bytes)
        # 这里不依赖 SDK 的返回结构，自己拼公开 URL
        pub_url = supabase_public_url(key)
        print(f"✓ Supabase 上传成功: {key}\n  公网 URL: {pub_url}")
        image_url = pub_url

        # 为了兼容后续逻辑，把文件指针复位（虽然之后不用）
        image.file.seek(0)

    # 若没配置 Supabase，则落地到本地 static
    if image_url is None:
        ext = pathlib.Path(image.filename).suffix
        fname = f"{uuid.uuid4()}{ext}"
        dest  = STATIC_DIR / fname
        with dest.open("wb") as f:
            shutil.copyfileobj(image.file, f)
        image_url = f"/static/{fname}"

    # ---- 创建新品
    fig = crud.create_figure(db, payload, image_url)
    return schemas.Figure.from_orm(fig).copy(update={"qty": 0, "total_sales": 0.0})

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
    db: Session = Depends(get_db)
):
    data = payload.dict(exclude_unset=True)
    new_qty = data.pop("qty", None)      # 单独拎出来
    fig = crud.update_figure(db, fig_id, data, new_qty)

    # 重新汇总库存、销售额
    stock, total_sales = (
        db.query(
            func.coalesce(func.sum(models.StockMovement.quantity), 0),
            func.coalesce(
                func.sum(
                    models.StockMovement.sale_price * (-models.StockMovement.quantity)
                ), 0
            ),
        )
        .filter(models.StockMovement.figure_id == fig_id)
        .one()
    )
    return schemas.Figure.from_orm(fig).copy(
        update={"qty": int(stock), "total_sales": float(total_sales)}
    )