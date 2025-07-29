from pydantic import BaseModel, ConfigDict, conint
from typing import Optional
from datetime import datetime

# ---------- Figure ----------
class FigureBase(BaseModel):
    manufacturer: str
    brand:        str
    character:    str
    model_name:   str
    cost_price:   float
    ip: Optional[str] = None

class SalesItem(BaseModel):
    sale_price: float
    moved_at:   datetime

class Figure(FigureBase):
    id: int
    image_url: Optional[str]
    qty: int = 0
    total_sales: float = 0            # ★ 新增

    # 前端点开才请求明细 ➜ 不放在 Figure 内
    model_config = ConfigDict(from_attributes=True)
    # 如果你只想用字典，写成：
    # model_config = {"from_attributes": True}

# ---------- 入/出库 ----------
class FigureCreate(FigureBase):
    pass

class StockMovementCreate(BaseModel):
    figure_id: int
    quantity: conint(strict=True, ge=1)
    sale_price: float | None = None   # 入库可不填

class FigureUpdate(BaseModel):
    """前端可选填，未提交的字段不会改"""
    manufacturer: Optional[str] = None
    brand:        Optional[str] = None
    character:    Optional[str] = None
    model_name:   Optional[str] = None
    cost_price:   Optional[float] = None
    ip:           Optional[str] = None
    qty:          Optional[int]  = None   # ★ 允许直接修改库存