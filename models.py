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
