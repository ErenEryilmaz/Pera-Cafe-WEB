"""
Pera Kafe — Temiz Versiyon + Admin Panel
Avatar kodu yok. Yönetici paneli /static/admin.html adresinde.

KURULUM:
  pip install fastapi uvicorn google-generativeai mysql-connector-python gtts python-dotenv bcrypt
  uvicorn main:app --reload --port 8000

.env:
  GOOGLE_API_KEY=...
  MYSQL_HOST=...  MYSQL_PORT=...  MYSQL_USER=...  MYSQL_PASSWORD=...  MYSQL_DATABASE=...
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=admin123   ← İlk çalıştırmada değiştirin!
"""

from fastapi.responses import RedirectResponse
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import mysql.connector
import json, re, io, base64, os, time, secrets, hashlib
from gtts import gTTS
from dotenv import load_dotenv
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi.responses import FileResponse

load_dotenv()

MY_API_KEY     = os.getenv("GOOGLE_API_KEY")
DB_HOST        = os.getenv("MYSQL_HOST")
DB_PORT        = os.getenv("MYSQL_PORT")
DB_USER        = os.getenv("MYSQL_USER")
DB_PASSWORD    = os.getenv("MYSQL_PASSWORD")
DB_NAME        = os.getenv("MYSQL_DATABASE")
ADMIN_USER     = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS     = os.getenv("ADMIN_PASSWORD", "admin123")

# Basit token store (production'da Redis kullanın)
active_tokens: dict[str, float] = {}   # token → expiry timestamp
TOKEN_TTL = 3600 * 8                   # 8 saat

app = FastAPI(title="Pera Kafe API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")
app = FastAPI(title="Pera Kafe API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

app.get("/")
# EKLENECEK KISIM BURASI
async def ana_sayfa():
    # Sadece ana domaine girildiğinde doğrudan login sayfasını döndür
    return FileResponse("static/perakafe_login.html")

security = HTTPBearer()

# ── MODELLER ────────────────────────────────────────────────
class LoginRequest(BaseModel):
    phone: str

class RegisterRequest(BaseModel):
    phone: str; first_name: str; last_name: str

class Message(BaseModel):
    role: str; content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    user_name: str = ""
    lang:      str = "tr"

# ── Admin modeller
class AdminLoginReq(BaseModel):
    username: str; password: str

class ProductUpdateReq(BaseModel):
    name:     Optional[str]   = None
    price:    Optional[float] = None
    stock:    Optional[int]   = None
    is_active:Optional[bool]  = None
    is_cold:  Optional[bool]  = None

class ProductCreateReq(BaseModel):
    category_id: int
    name:        str
    price:       float
    stock:       int   = 50
    is_cold:     bool  = False

class CategoryCreateReq(BaseModel):
    name: str

class OrderStatusReq(BaseModel):
    status: str   # pending | preparing | ready | completed | cancelled

class OrderCreateReq(BaseModel):
    table_no:     str = "Kiosk"
    member_phone: Optional[str] = None
    items:        List[dict]    = []   # [{name, qty, price}]
    notes:        Optional[str] = None

# ── VERİTABANI ──────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=DB_HOST, port=int(DB_PORT), user=DB_USER,
        password=DB_PASSWORD, database=DB_NAME, ssl_disabled=False)

def get_menu_data():
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.callproc('GetActiveMenu')
        rows = []
        for r in cur.stored_results(): rows.extend(r.fetchall())
        db.close()
        menu_dict = {}; ai_text = "GÜNCEL FİYAT LİSTESİ:\n"
        for row in rows:
            cat = row['CategoryName']; urun = row['ProductName']
            fiyat = float(row['BasePrice']); cold = row['IsCold']
            if cat not in menu_dict: menu_dict[cat] = []
            s = "🧊 Soğuk" if cold else "☕ Sıcak"
            menu_dict[cat].append({"urun": urun,
                                    "fiyat_gorunum": f"Fiyat: {fiyat}₺ | {s}",
                                    "taban_fiyat": fiyat})
            ai_text += f"- {urun} ({s}): {fiyat} TL\n"
        return menu_dict, ai_text
    except Exception as e:
        print(f"DB: {e}"); return {}, "DB hatası."

# ── AUTH ─────────────────────────────────────────────────────
def verify_token(cred: HTTPAuthorizationCredentials = Depends(security)):
    token = cred.credentials
    exp   = active_tokens.get(token)
    if not exp or time.time() > exp:
        active_tokens.pop(token, None)
        raise HTTPException(401, "Geçersiz veya süresi dolmuş token.")
    return token

# ── SİSTEM PROMPT ────────────────────────────────────────────
def build_prompt(lang, user_name, menu_text):
    n = {
        "tr": f'Müşterinin adı: "{user_name}". Ona ismiyle hitap et.' if user_name and user_name != "Misafir" else "Müşteri anonim.",
        "en": f'Customer name: "{user_name}".' if user_name not in ("Misafir","Guest","") else "Anonymous.",
        "ar": f'اسم العميل: "{user_name}".' if user_name not in ("Misafir","","Guest","ضيف") else "مجهول.",
    }.get(lang, "")
    return {
        "tr": f'Sen "Pera Kafe"nin garsonusun, adın Pera. Sadece TÜRKÇE. Kısa, samimi. {n}\nMENÜ: {menu_text}\nSipariş değişince: SIPARIS_JSON:[{{"ad":"..","fiyat":0}}]',
        "en": f'You are Pera, waiter at Pera Kafe. ENGLISH only. Short, friendly. {n}\nMENU: {menu_text}\nOrder change: SIPARIS_JSON:[{{"ad":"..","fiyat":0}}]',
        "ar": f'أنت بيرا، نادل في بيرا كافيه. العربية فقط. {n}\nالقائمة: {menu_text}\nSIPARIS_JSON:[{{"ad":"..","fiyat":0}}]',
    }.get(lang, "")

def make_audio_b64(text, lang="tr"):
    try:
        tts = gTTS(text=text, lang={"tr":"tr","en":"en","ar":"ar"}.get(lang,"tr"))
        buf = io.BytesIO(); tts.write_to_fp(buf); buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        print(f"TTS: {e}"); return None

# ══════════════════════════════════════════════════════════════
#  MÜŞTERİ ENDPOINTLERİ
# ══════════════════════════════════════════════════════════════

@app.post("/login")
async def login(req: LoginRequest):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT first_name FROM members WHERE phone=%s", (req.phone,))
        u = cur.fetchone(); db.close()
        return {"success": True, "name": u["first_name"]} if u else {"success": False}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/register")
async def register(req: RegisterRequest):
    try:
        db = get_db(); cur = db.cursor()
        cur.execute("INSERT INTO members (phone,first_name,last_name) VALUES(%s,%s,%s)",
                    (req.phone, req.first_name, req.last_name))
        db.commit(); db.close(); return {"success": True}
    except mysql.connector.Error as e:
        if "Duplicate" in str(e) or "zaten" in str(e):
            return {"success": False, "message": "Bu numara zaten kayıtlı."}
        raise HTTPException(500, str(e))
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/menu")
async def menu():
    m, _ = get_menu_data(); return {"menu": m}

@app.post("/chat")
async def chat(req: ChatRequest):
    _, menu_text = get_menu_data()
    lang = req.lang if req.lang in ("tr","en","ar") else "tr"
    try:
        genai.configure(api_key=MY_API_KEY)
        try:
            avail = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            mname = next((m for m in avail if "flash" in m), "models/gemini-1.5-flash-latest")
        except: mname = "gemini-1.5-flash"

        model = genai.GenerativeModel(model_name=mname, system_instruction=build_prompt(lang, req.user_name, menu_text))
        hist  = [{"role":"user" if m.role=="user" else "model","parts":[m.content]} for m in req.messages[:-1]]
        resp  = model.start_chat(history=hist).send_message(req.messages[-1].content)
        bot   = resp.text

        match = re.search(r"SIPARIS_JSON:(.*)", bot, re.DOTALL)
        cart  = None; clean = bot
        if match:
            clean = bot.replace(match.group(0), "").strip()
            try: cart = json.loads(match.group(1).strip())
            except: pass

        audio_b64 = make_audio_b64(clean, lang)
        return {"reply": clean, "cart": cart, "audio_base64": audio_b64}

    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

@app.post("/order")
async def create_order(req: OrderCreateReq):
    try:
        db = get_db(); cur = db.cursor()
        total = sum(i.get("qty",1) * i.get("price",0) for i in req.items)
        cur.execute(
            "INSERT INTO Orders (TableNo, MemberPhone, TotalAmount, Notes) VALUES (%s,%s,%s,%s)",
            (req.table_no, req.member_phone, total, req.notes)
        )
        order_id = cur.lastrowid
        for item in req.items:
            # Sadece OrderItems'a ekliyoruz, stok düşmeyi SQL Trigger'ı hallediyor
            cur.execute(
                "INSERT INTO OrderItems (OrderID, ProductName, Quantity, UnitPrice) VALUES (%s,%s,%s,%s)",
                (order_id, item["name"], item.get("qty",1), item["price"])
            )
        db.commit(); db.close()
        return {"success": True, "order_id": order_id}
    except Exception as e:
        raise HTTPException(500, str(e))
# ══════════════════════════════════════════════════════════════
#  ADMİN AUTH
# ══════════════════════════════════════════════════════════════

@app.post("/admin/login")
async def admin_login(req: AdminLoginReq):
    if req.username != ADMIN_USER or req.password != ADMIN_PASS:
        raise HTTPException(401, "Kullanıcı adı veya şifre hatalı.")
    token = secrets.token_hex(32)
    active_tokens[token] = time.time() + TOKEN_TTL
    return {"token": token, "expires_in": TOKEN_TTL}

@app.post("/admin/logout")
async def admin_logout(token: str = Depends(verify_token)):
    active_tokens.pop(token, None)
    return {"success": True}

# ══════════════════════════════════════════════════════════════
#  ADMİN — DASHBOARD
# ══════════════════════════════════════════════════════════════

@app.get("/admin/dashboard")
async def dashboard(_: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.callproc('GetDashboardStats')
        
        # Procedure'den dönen sonuçları sırayla alıyoruz
        results = list(cur.stored_results())
        
        # İlk tablo tek satırlık genel veriler
        stats = results[0].fetchone() 
        
        # İkinci tablo haftalık liste
        weekly = results[1].fetchall() 
        db.close()

        return {
            "today_orders":   stats["today_orders"],
            "today_revenue":  float(stats["today_revenue"]),
            "pending_orders": stats["pending_orders"],
            "low_stock_count":stats["low_stock_count"],
            "total_members":  stats["total_members"],
            "weekly_revenue": [{"day": str(r["day"]), "rev": float(r["rev"])} for r in weekly],
        }
    except Exception as e: raise HTTPException(500, str(e))

# ══════════════════════════════════════════════════════════════
#  ADMİN — SİPARİŞLER
# ══════════════════════════════════════════════════════════════

@app.get("/admin/orders")
async def get_orders(status: str = "all", limit: int = 50, _: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        if status == "all":
            cur.execute("SELECT * FROM Orders ORDER BY CreatedAt DESC LIMIT %s", (limit,))
        else:
            cur.execute("SELECT * FROM Orders WHERE Status=%s ORDER BY CreatedAt DESC LIMIT %s", (status, limit))
        orders = cur.fetchall()

        for o in orders:
            cur.execute("SELECT * FROM OrderItems WHERE OrderID=%s", (o["OrderID"],))
            o["items"] = cur.fetchall()
            o["CreatedAt"] = str(o["CreatedAt"])
            o["UpdatedAt"] = str(o.get("UpdatedAt",""))
        db.close()
        return orders
    except Exception as e: raise HTTPException(500, str(e))

@app.patch("/admin/orders/{order_id}/status")
async def update_order_status(order_id: int, req: OrderStatusReq, _: str = Depends(verify_token)):
    valid = ('pending','preparing','ready','completed','cancelled')
    if req.status not in valid:
        raise HTTPException(400, f"Geçersiz durum. Geçerli değerler: {valid}")
    try:
        db = get_db(); cur = db.cursor()
        cur.execute("UPDATE Orders SET Status=%s WHERE OrderID=%s", (req.status, order_id))
        db.commit(); db.close()
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))

@app.delete("/admin/orders/{order_id}")
async def delete_order(order_id: int, _: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor()
        # İki ayrı DELETE sorgusu yerine tek satırda procedure çağırıyoruz
        cur.callproc('DeleteOrder', (order_id,))
        db.commit(); db.close()
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))
# ══════════════════════════════════════════════════════════════
#  ADMİN — ÜRÜNLER
# ══════════════════════════════════════════════════════════════

@app.get("/admin/products")
async def get_products(_: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT p.ProductID, p.ProductName, p.BasePrice, p.IsCold,
                   COALESCE(p.StockQuantity, 50) AS StockQuantity,
                   COALESCE(p.IsActive, 1) AS IsActive,
                   c.CategoryID, c.CategoryName
            FROM products p
            JOIN categories c ON p.CategoryID = c.CategoryID
            ORDER BY c.CategoryName, p.ProductName
        """)
        rows = cur.fetchall()
        db.close()
        return rows
    except Exception as e: raise HTTPException(500, str(e))

@app.patch("/admin/products/{product_id}")
async def update_product(product_id: int, req: ProductUpdateReq, _: str = Depends(verify_token)):
    fields = []
    vals   = []
    if req.name      is not None: fields.append("ProductName=%s");     vals.append(req.name)
    if req.price     is not None: fields.append("BasePrice=%s");       vals.append(req.price)
    if req.stock     is not None: fields.append("StockQuantity=%s");   vals.append(req.stock)
    if req.is_active is not None: fields.append("IsActive=%s");        vals.append(req.is_active)
    if req.is_cold   is not None: fields.append("IsCold=%s");          vals.append(req.is_cold)
    if not fields: return {"success": True, "message": "Değişiklik yok."}
    vals.append(product_id)
    try:
        db = get_db(); cur = db.cursor()
        cur.execute(f"UPDATE products SET {', '.join(fields)} WHERE ProductID=%s", vals)
        db.commit(); db.close()
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/admin/products")
async def add_product(req: ProductCreateReq, _: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor()
        cur.execute(
            "INSERT INTO products (CategoryID, ProductName, BasePrice, StockQuantity, IsCold, IsActive) VALUES (%s,%s,%s,%s,%s,1)",
            (req.category_id, req.name, req.price, req.stock, req.is_cold)
        )
        db.commit()
        new_id = cur.lastrowid
        db.close()
        return {"success": True, "product_id": new_id}
    except Exception as e: raise HTTPException(500, str(e))

@app.delete("/admin/products/{product_id}")
async def delete_product(product_id: int, _: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor()
        # Silmek yerine pasif yap (sipariş geçmişi bozulmasın)
        cur.execute("UPDATE products SET IsActive=0 WHERE ProductID=%s", (product_id,))
        db.commit(); db.close()
        return {"success": True, "message": "Ürün pasife alındı."}
    except Exception as e: raise HTTPException(500, str(e))

# ══════════════════════════════════════════════════════════════
#  ADMİN — KATEGORİLER
# ══════════════════════════════════════════════════════════════

@app.get("/admin/categories")
async def get_categories(_: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM categories ORDER BY CategoryName")
        cats = cur.fetchall(); db.close()
        return cats
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/admin/categories")
async def add_category(req: CategoryCreateReq, _: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor()
        cur.execute("INSERT INTO categories (CategoryName) VALUES (%s)", (req.name,))
        db.commit(); new_id = cur.lastrowid; db.close()
        return {"success": True, "category_id": new_id}
    except Exception as e: raise HTTPException(500, str(e))

# ══════════════════════════════════════════════════════════════
#  ADMİN — STOK
# ══════════════════════════════════════════════════════════════

@app.get("/admin/stock")
async def get_stock(_: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT p.ProductID, p.ProductName, c.CategoryName,
                   COALESCE(p.StockQuantity,50) AS StockQuantity,
                   COALESCE(p.IsActive,1) AS IsActive
            FROM products p
            JOIN categories c ON p.CategoryID=c.CategoryID
            ORDER BY p.StockQuantity ASC, p.ProductName
        """)
        rows = cur.fetchall(); db.close()
        return rows
    except Exception as e: raise HTTPException(500, str(e))

@app.patch("/admin/stock/{product_id}")
async def update_stock(product_id: int, body: dict, _: str = Depends(verify_token)):
    qty = body.get("stock")
    if qty is None: raise HTTPException(400, "stock alanı gerekli.")
    try:
        db = get_db(); cur = db.cursor()
        cur.execute("UPDATE products SET StockQuantity=%s WHERE ProductID=%s", (qty, product_id))
        db.commit(); db.close()
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))

# ══════════════════════════════════════════════════════════════
#  ADMİN — ÜYELER
# ══════════════════════════════════════════════════════════════

@app.get("/admin/members")
async def get_members(_: str = Depends(verify_token)):
    try:
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT m.id, m.phone, m.first_name, m.last_name, m.created_at,
                   COUNT(o.OrderID) AS order_count,
                   COALESCE(SUM(o.TotalAmount),0) AS total_spent
            FROM members m
            LEFT JOIN Orders o ON o.MemberPhone = m.phone
            GROUP BY m.id
            ORDER BY m.created_at DESC
        """)
        rows = cur.fetchall()
        for r in rows:
            r["created_at"]  = str(r["created_at"])
            r["total_spent"] = float(r["total_spent"])
        db.close(); return rows
    except Exception as e: raise HTTPException(500, str(e))
