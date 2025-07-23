from sqlalchemy.orm import Session
from sqlalchemy import func, select
from fastapi import HTTPException
from . import models

def create_figure(db: Session, data, image_url: str | None):
    fig = models.Figure(**data, image_url=image_url)
    db.add(fig)
    db.commit()
    db.refresh(fig)
    return fig

def get_all_figures_with_qty(db: Session):
    sub = (db.query(models.StockMovement.figure_id,
                    func.coalesce(func.sum(models.StockMovement.quantity), 0).label("qty"))
             .group_by(models.StockMovement.figure_id).subquery())
    return (db.query(models.Figure, sub.c.qty)
              .outerjoin(sub, models.Figure.id == sub.c.figure_id)
              .all())


def add_movement(db, figure_id: int, qty: int, mtype: str, sale_price=None):
    # ① 计算当前库存
    current_qty = db.scalar(
        select(func.coalesce(func.sum(models.StockMovement.quantity), 0))
        .where(models.StockMovement.figure_id == figure_id)
    )

    # ② 如果是出库（qty 为负），检查库存是否足够
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
    fig = db.query(models.Figure).get(figure_id)
    db.delete(fig)
    db.commit()

def get_same_figure(db, data: dict):
    return db.query(models.Figure).filter_by(
        manufacturer=data["manufacturer"],
        brand=data["brand"],
        character=data["character"],
        model_name=data["model_name"],
        cost_price=data["cost_price"],
    ).first()