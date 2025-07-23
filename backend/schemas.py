from pydantic import BaseModel, ConfigDict, conint
from typing import Optional
from datetime import datetime

# ---------- Figure ----------
class FigureBase(BaseModel):
    manufacturer: str
    brand: str
    character: str
    model_name: str
    cost_price: float
    ip: str | None = None

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