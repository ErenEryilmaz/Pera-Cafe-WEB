from pydantic import BaseModel
from typing import Optional, List


# ── Müşteri modelleri ────────────────────────────────────────

class LoginRequest(BaseModel):
    phone: str


class RegisterRequest(BaseModel):
    phone: str
    first_name: str
    last_name: str


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    user_name: str = ""
    lang: str = "tr"
    gender: str = "female"  # "female" | "male"


class OrderCreateReq(BaseModel):
    table_no: str = "Kiosk"
    member_phone: Optional[str] = None
    items: List[dict] = []   # [{name, qty, price}]
    notes: Optional[str] = None


# ── Admin modelleri ──────────────────────────────────────────

class AdminLoginReq(BaseModel):
    username: str
    password: str


class ProductUpdateReq(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None
    is_cold: Optional[bool] = None


class ProductCreateReq(BaseModel):
    category_id: int
    name: str
    price: float
    stock: int = 50
    is_cold: bool = False


class CategoryCreateReq(BaseModel):
    name: str


class OrderStatusReq(BaseModel):
    status: str   # pending | preparing | ready | completed | cancelled


class CampaignCreateReq(BaseModel):
    title: str
    type: str                      # buy_x_get_y | percentage | fixed
    config: dict                   # {"buy":2,"get":1} | {"percent":10} | {"amount":20}
    description: Optional[str] = None
    badge_color: str = "#E67E22"
    is_active: bool = True
    start_date: Optional[str] = None   # "YYYY-MM-DD"
    end_date: Optional[str] = None


class CampaignUpdateReq(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    config: Optional[dict] = None
    description: Optional[str] = None
    badge_color: Optional[str] = None
    is_active: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
