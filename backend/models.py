from sqlalchemy import (
    Column, Integer, String, Numeric,
    Text, DateTime, func, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


# -------------------- Figure --------------------
class Figure(Base):
    __tablename__ = "figures"

    id            = Column(Integer, primary_key=True, index=True)
    manufacturer  = Column(String, nullable=False)
    brand         = Column(String, nullable=False)
    character     = Column(String, nullable=False)
    model_name    = Column(String, nullable=False)
    # msrp / 建议售价可留可删（允许 NULL）
    msrp          = Column(Numeric(10, 2))
    cost_price    = Column(Numeric(10, 2), nullable=False)
    ip            = Column(String(120))  
    image_url     = Column(Text)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # ★ back_populates 必须和 StockMovement.figure 对应
    movements     = relationship(
        "StockMovement",
        back_populates="figure",
        cascade="all, delete-orphan"
    )


# ---------------- StockMovement -----------------
class StockMovement(Base):
    __tablename__ = "stock_movements"

    id            = Column(Integer, primary_key=True, index=True)
    figure_id     = Column(Integer, ForeignKey("figures.id", ondelete="CASCADE"))
    quantity      = Column(Integer, nullable=False)
    movement_type = Column(
        String(3),
        CheckConstraint("movement_type IN ('IN','OUT')"),
        nullable=False
    )
    sale_price    = Column(Numeric(10, 2))         # 出库时填写
    moved_at      = Column(DateTime(timezone=True), server_default=func.now())

    # ★ 这里的名字必须写成 figure
    figure        = relationship("Figure", back_populates="movements")