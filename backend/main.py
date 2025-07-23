import os, uuid, shutil, pathlib
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles   # ← 新增 import
from sqlalchemy.orm import Session
from sqlalchemy import func, select, Numeric
from .database import Base, engine, SessionLocal
from . import schemas, crud, models
from decimal import Decimal
from fastapi.encoders import jsonable_encoder

# ---------- 数据库初始化 ----------
Base.metadata.create_all(bind=engine)

BASE_DIR   = pathlib.Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)  

app = FastAPI(title="Figures Inventory API")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
    ip: str | None    = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    data = dict(
        manufacturer=manufacturer,
        brand=brand,
        character=character,
        model_name=model_name,
        cost_price=cost_price,
        ip=ip,
    )

    # ---------- 查重 ----------
    fig = crud.get_same_figure(db, data)
    if fig:
        # 1) 库存 +1
        crud.add_movement(db, fig.id, 1, "IN")

        # 2) 重新计算最新库存 & 总销售额
        stock, total_sales = (
            db.query(
                func.coalesce(func.sum(models.StockMovement.quantity), 0),
                func.coalesce(
                    func.sum(
                        models.StockMovement.sale_price
                        * (-models.StockMovement.quantity)
                    ),
                    0,
                ),
            )
            .filter(models.StockMovement.figure_id == fig.id)
            .one()
        )

        # 3) 返回 Pydantic 对象
        return (
            schemas.Figure.from_orm(fig)
            .copy(update={"qty": int(stock), "total_sales": float(total_sales)})
        )

    # ---------- 新品但没传图片 -> 400 ----------
    no_image = (
        image is None or                # 参数缺失
        image.filename.strip() == ""    # 空文件
    )
    if no_image:
        raise HTTPException(400, "新品必须上传图片")

    # ---------- 保存图片 ----------
    ext   = pathlib.Path(image.filename).suffix
    fname = f"{uuid.uuid4()}{ext}"
    static = pathlib.Path(__file__).parent / "static"
    static.mkdir(exist_ok=True)
    dest  = static / fname
    with dest.open("wb") as f:
        shutil.copyfileobj(image.file, f)
    image_url = f"/static/{fname}"

    # ---------- 创建新品 ----------
    fig = crud.create_figure(db, data, image_url)
    return schemas.Figure.from_orm(fig).copy(update={"qty": 0})

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
    q = select(
        models.Figure.manufacturer,
        models.Figure.brand,
        models.Figure.character,
        models.Figure.model_name,
        models.Figure.ip.distinct()
    ).distinct()
    rows = db.execute(q).all()
    manu, brand, chara, model = zip(*rows) if rows else ([], [], [], [])
    return {
        "manufacturer": sorted(set(manu)),
        "brand":        sorted(set(brand)),
        "character":    sorted(set(chara)),
        "model_name":   sorted(set(model)),
        "ip":           sorted(set(ip)),
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