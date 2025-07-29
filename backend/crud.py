from sqlalchemy.orm import Session
from sqlalchemy import func, select
from fastapi import HTTPException
from . import models

# ───────────────────────── 公共工具 ──────────────────────────
def get_stock(db: Session, fig_id: int) -> int:
    """返回指定手办当前库存（sum(quantity)）"""
    return db.scalar(
        select(func.coalesce(func.sum(models.StockMovement.quantity), 0))
        .where(models.StockMovement.figure_id == fig_id)
    )

# ───────────────────────── 业务函数 ──────────────────────────
def create_figure(db: Session, data, image_url: str | None):
    fig = models.Figure(**data, image_url=image_url)
    db.add(fig)
    db.commit()
    db.refresh(fig)
    return fig

def get_all_figures_with_qty(db: Session):
    sub = (
        db.query(
            models.StockMovement.figure_id,
            func.coalesce(func.sum(models.StockMovement.quantity), 0).label("qty")
        )
        .group_by(models.StockMovement.figure_id)
        .subquery()
    )
    return (
        db.query(models.Figure, sub.c.qty)
        .outerjoin(sub, models.Figure.id == sub.c.figure_id)
        .all()
    )

def add_movement(db, figure_id: int, qty: int,
                 mtype: str, sale_price=None):
    current_qty = get_stock(db, figure_id)          # 🔹 用统一方法
    if qty < 0 and current_qty + qty < 0:
        raise HTTPException(400, "库存不足，无法出库")

    mov = models.StockMovement(
        figure_id=figure_id,
        quantity=qty,
        movement_type=mtype,
        sale_price=sale_price,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov

def delete_figure(db: Session, figure_id: int):
    fig = db.get(models.Figure, figure_id)
    if not fig:
        raise HTTPException(404, "Figure not found")
    db.delete(fig)
    db.commit()

def get_same_figure(db, data: dict):
    return (
        db.query(models.Figure)
        .filter_by(
            manufacturer=data["manufacturer"],
            brand=data["brand"],
            character=data["character"],
            model_name=data["model_name"],
            cost_price=data["cost_price"],
        )
        .first()
    )

def update_figure(db: Session, fig_id: int,
                  data: dict, new_qty: int | None = None):
    fig: models.Figure = db.get(models.Figure, fig_id)
    if not fig:
        raise HTTPException(404, "Figure not found")

    # 基本字段
    for k, v in data.items():
        if v is not None and hasattr(fig, k):
            setattr(fig, k, v)

    # 如需改库存
    if new_qty is not None:
        current_qty = get_stock(db, fig_id)         # 🔹 统一取库存
        delta = new_qty - current_qty
        if delta:
            add_movement(db, fig_id, delta,
                         "IN" if delta > 0 else "OUT")

    db.commit()
    db.refresh(fig)
    return fig