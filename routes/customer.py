import json
import re
import os

import google.generativeai as genai
import mysql.connector
from fastapi import APIRouter, HTTPException

from database import get_db, get_menu_data
from models import LoginRequest, RegisterRequest, ChatRequest, OrderCreateReq
from utils import build_prompt, make_audio_b64

MY_API_KEY = os.getenv("GOOGLE_API_KEY")

router = APIRouter()


@router.post("/login")
async def login(req: LoginRequest):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT first_name FROM members WHERE phone=%s", (req.phone,))
        u = cur.fetchone()
        db.close()
        return {"success": True, "name": u["first_name"]} if u else {"success": False}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/register")
async def register(req: RegisterRequest):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO members (phone,first_name,last_name) VALUES(%s,%s,%s)",
            (req.phone, req.first_name, req.last_name),
        )
        db.commit()
        db.close()
        return {"success": True}
    except mysql.connector.Error as e:
        if "Duplicate" in str(e) or "zaten" in str(e):
            return {"success": False, "message": "Bu numara zaten kayıtlı."}
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/menu")
async def menu(lang: str = "tr"):
    m, _ = get_menu_data(lang)
    return {"menu": m}


def _parse_json(val):
    if isinstance(val, (bytes, bytearray)):
        val = val.decode("utf-8")
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return None
    return val


def _norm(s):
    """Ad eşleştirmesi için normalleştirme: kırp, küçült, boşlukları sadeleştir."""
    return re.sub(r"\s+", " ", str(s or "").strip().casefold())


def _product_index(cur):
    """Tüm dillerdeki normalleştirilmiş ürün adı -> ProductID haritası.
    AI sepetindeki adları kanonik ürün ID'sine bağlamak için kullanılır."""
    cur.execute("SELECT ProductID, ProductName, ProductName_en, ProductName_ar FROM products")
    idx = {}
    for r in cur.fetchall():
        for k in ("ProductName", "ProductName_en", "ProductName_ar"):
            v = r.get(k)
            if v:
                idx[_norm(v)] = r["ProductID"]
    return idx


def _resolve_scope(cur, scope_type, scope_ids, lang="tr"):
    """Kampanya kapsamını çözer. Üç şey döner:
      - ids:    kapsamdaki ürün ID listesi (BİRİNCİL eşleştirme anahtarı).
      - names:  üç dildeki tüm ürün adları (product_id yoksa yedek eşleştirme).
      - labels: gösterim için yalnızca istenen dildeki adlar.
    'all' / kapsamsız -> (None, None, None)."""
    if scope_type not in ("category", "product") or not scope_ids:
        return None, None, None
    col = "CategoryID" if scope_type == "category" else "ProductID"
    placeholders = ",".join(["%s"] * len(scope_ids))
    cur.execute(
        f"SELECT ProductID, ProductName, ProductName_en, ProductName_ar "
        f"FROM products WHERE {col} IN ({placeholders})",
        tuple(scope_ids),
    )
    rows = cur.fetchall()
    label_col = {"en": "ProductName_en", "ar": "ProductName_ar"}.get(lang, "ProductName")
    ids, names, labels = [], [], []
    for r in rows:
        ids.append(r["ProductID"])
        for k in ("ProductName", "ProductName_en", "ProductName_ar"):
            if r.get(k):
                names.append(r[k])
        labels.append(r.get(label_col) or r["ProductName"])
    # Sırayı koruyarak tekrarsızlaştır
    return list(dict.fromkeys(ids)), list(dict.fromkeys(names)), list(dict.fromkeys(labels))


def _fetch_active_campaigns(cur, lang="tr"):
    """Aktif ve tarihi geçerli kampanyaları kapsam çözülmüş biçimde döndürür.
    Dictionary cursor bekler. /campaigns ve /order ortak kullanır.
      - scope_product_ids: kapsamdaki ürün ID'leri — indirim BU ID'lerle eşleşir.
      - scope_products:    üç dildeki adlar — yedek (product_id yoksa) eşleştirme.
      - scope_labels:      gösterim için istenen dildeki adlar."""
    cur.execute(
        """SELECT * FROM campaigns
           WHERE is_active = TRUE
             AND (start_date IS NULL OR start_date <= CURDATE())
             AND (end_date   IS NULL OR end_date   >= CURDATE())
           ORDER BY created_at DESC"""
    )
    rows = cur.fetchall()
    result = []
    for row in rows:
        scope_type = row.get("scope_type") or "all"
        scope_ids = _parse_json(row.get("scope_ids")) or []
        ids, names, labels = _resolve_scope(cur, scope_type, scope_ids, lang)
        result.append({
            "id":               row["id"],
            "title":            row["title"],
            "description":      row.get("description"),
            "type":             row["type"],
            "config":           _parse_json(row.get("config")) or {},
            "badge_color":      row.get("badge_color") or "#E67E22",
            "start_date":       str(row["start_date"]) if row.get("start_date") else None,
            "end_date":         str(row["end_date"]) if row.get("end_date") else None,
            "scope_type":       scope_type,
            "scope_product_ids": ids,
            "scope_products":   names,
            "scope_labels":     labels,
        })
    return result


# ── İndirim hesabı (cart.js applyDiscounts ile birebir aynı mantık) ───
# Sipariş toplamı sunucuda yeniden hesaplanır; client gönderdiği tutara güvenilmez.

def _scope_items(items, camp):
    """Kampanya kapsamına giren sipariş kalemleri. items: [{name, qty, price, product_id}].
    Önce ürün ID'siyle eşleşir; kalemde ID yoksa ada düşer (yedek)."""
    if not camp.get("scope_type") or camp["scope_type"] == "all":
        return items
    idset = set(camp.get("scope_product_ids") or [])
    nameset = set(camp.get("scope_products") or [])
    out = []
    for i in items:
        pid = i.get("product_id")
        if pid is not None:
            if pid in idset:
                out.append(i)
        elif i.get("name") in nameset:
            out.append(i)
    return out


def _compute_discount(items, campaigns):
    """Aktif kampanyaların toplam indirim tutarını hesaplar."""
    total = 0.0
    for camp in campaigns:
        if not camp:
            continue
        scoped = _scope_items(items, camp)
        if not scoped:
            continue
        ctype = camp.get("type")
        cfg = camp.get("config") or {}
        if ctype == "buy_x_get_y":
            buy = cfg.get("buy") or 2
            get = cfg.get("get") or 1
            for it in scoped:
                qty = int(it.get("qty") or 0)
                price = float(it.get("price") or 0)
                sets = qty // (buy + get)
                remainder = qty % (buy + get)
                free_count = sets * get + (remainder - buy if remainder > buy else 0)
                if free_count > 0:
                    total += free_count * price
        elif ctype == "percentage":
            raw = sum(float(i.get("price") or 0) * int(i.get("qty") or 0) for i in scoped)
            total += raw * ((cfg.get("percent") or 0) / 100)
        elif ctype == "fixed":
            amount = float(cfg.get("amount") or 0)
            for it in scoped:
                qty = int(it.get("qty") or 0)
                price = float(it.get("price") or 0)
                total += min(amount, price) * qty
    return total


@router.get("/campaigns")
async def campaigns(lang: str = "tr"):
    """Müşteriye yalnızca aktif ve tarihi geçerli kampanyaları döndürür.
    Kapsamlı kampanyalarda eşleştirme seti (scope_products, tüm diller) ve
    gösterim adları (scope_labels, istenen dil) döner."""
    lang = lang if lang in ("tr", "en", "ar") else "tr"
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        result = _fetch_active_campaigns(cur, lang)
        db.close()
        return result
    except Exception:
        return []


@router.post("/chat")
async def chat(req: ChatRequest):
    lang = req.lang if req.lang in ("tr", "en", "ar") else "tr"
    _, menu_text = get_menu_data(lang)
    try:
        genai.configure(api_key=MY_API_KEY)
        try:
            avail = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            mname = next((m for m in avail if "flash" in m), "models/gemini-1.5-flash-latest")
        except:
            mname = "gemini-1.5-flash"

        model = genai.GenerativeModel(
            model_name=mname,
            system_instruction=build_prompt(lang, req.user_name, menu_text, req.gender),
        )
        # Giriş karşılaması — AI yerine hazır metni TTS ile seslendir
        last_msg = req.messages[-1].content
        if last_msg == "__greeting__":
            greeting_text = {
                "tr": f"Hoş geldin {req.user_name}! Pera Kafede seni bekliyorduk, ne alırdın?" if req.user_name and req.user_name != "Misafir" else "Pera Kafede hoş geldiniz!",
                "en": f"Welcome back, {req.user_name}! What can I get you today?" if req.user_name not in ("Misafir","Guest","") else "Welcome to Pera Cafe!",
                "ar": f"مرحباً {req.user_name}! يسعدنا عودتك." if req.user_name not in ("Misafir","","Guest","ضيف") else "مرحباً بكم في بيرا كافيه!",
            }.get(lang, "")
            return {"reply": greeting_text, "cart": None, "audio_base64": make_audio_b64(greeting_text, lang, req.gender)}
        hist = [
            {"role": "user" if m.role == "user" else "model", "parts": [m.content]}
            for m in req.messages[:-1]
        ]
        resp = model.start_chat(history=hist).send_message(last_msg)
        # resp.text, yanıt güvenlik filtresine takılır / boş dönerse ValueError fırlatır.
        # Bu durumda 500 vermek yerine kibarca devam et.
        try:
            bot = resp.text
        except Exception:
            bot = {
                "tr": "Pardon, onu tam anlayamadım. Tekrar söyler misin?",
                "en": "Sorry, I didn't quite catch that. Could you say it again?",
                "ar": "عذراً، لم أفهم ذلك تماماً. هل يمكنك إعادة القول؟",
            }.get(lang, "Pardon, tekrar söyler misin?")

        match = re.search(r"SIPARIS_JSON:(.*)", bot, re.DOTALL)
        cart = None
        clean = bot
        if match:
            clean = bot.replace(match.group(0), "").strip()
            try:
                cart = json.loads(match.group(1).strip())
            except:
                pass

        # AI sepetindeki her ürünü kanonik ProductID'ye bağla. Böylece kampanya
        # kapsamı isimle değil ID ile eşleşir (dil/yazım farklarından etkilenmez).
        if isinstance(cart, list) and cart:
            try:
                db = get_db()
                cur = db.cursor(dictionary=True)
                index = _product_index(cur)
                db.close()
                for it in cart:
                    if isinstance(it, dict):
                        it["product_id"] = index.get(_norm(it.get("ad", "")))
            except Exception:
                pass

        audio_b64 = make_audio_b64(clean, lang, req.gender)
        return {"reply": clean, "cart": cart, "audio_base64": audio_b64}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))


@router.post("/order")
async def create_order(req: OrderCreateReq):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        raw_total = sum(i.get("qty", 1) * i.get("price", 0) for i in req.items)
        # Kampanya indirimi sunucuda hesaplanır (client'ın gönderdiği tutara güvenilmez).
        # Hesap herhangi bir nedenle hata verirse indirimsiz tutara güvenli düşülür.
        try:
            discount = _compute_discount(req.items, _fetch_active_campaigns(cur))
        except Exception:
            discount = 0.0
        total = max(0, raw_total - discount)
        cur.execute(
            "INSERT INTO Orders (TableNo, MemberPhone, TotalAmount, Notes) VALUES (%s,%s,%s,%s)",
            (req.table_no, req.member_phone, total, req.notes),
        )
        order_id = cur.lastrowid
        for item in req.items:
            cur.execute(
                "INSERT INTO OrderItems (OrderID, ProductName, Quantity, UnitPrice) VALUES (%s,%s,%s,%s)",
                (order_id, item["name"], item.get("qty", 1), item["price"]),
            )
        db.commit()
        db.close()
        return {"success": True, "order_id": order_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/order/{order_id}/status")
async def get_order_status(order_id: int):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT Status FROM Orders WHERE OrderID=%s", (order_id,))
        row = cur.fetchone()
        db.close()
        if not row:
            raise HTTPException(404, "Sipariş bulunamadı.")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/orders/by-phone/{phone}")
async def get_orders_by_phone(phone: str, limit: int = 10):
    """Bir üyenin son siparişlerini (en yeni üstte) kalemleriyle birlikte döndürür.
    'Geçmiş siparişler' sayfası bunu kullanır. Üyesiz/misafir siparişler MemberPhone
    NULL kaydedildiği için burada listelenmez."""
    limit = max(1, min(limit, 50))  # mantıklı bir tavan
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            """SELECT OrderID, Status, TotalAmount, CreatedAt, Notes
               FROM Orders WHERE MemberPhone=%s
               ORDER BY CreatedAt DESC LIMIT %s""",
            (phone, limit),
        )
        orders = cur.fetchall()
        for o in orders:
            cur.execute(
                "SELECT ProductName, Quantity, UnitPrice FROM OrderItems WHERE OrderID=%s",
                (o["OrderID"],),
            )
            o["items"] = cur.fetchall()
            o["CreatedAt"] = str(o["CreatedAt"])
            o["TotalAmount"] = float(o["TotalAmount"]) if o["TotalAmount"] is not None else 0.0
            for it in o["items"]:
                it["UnitPrice"] = float(it["UnitPrice"]) if it["UnitPrice"] is not None else 0.0
        db.close()
        return orders
    except Exception as e:
        raise HTTPException(500, str(e))
