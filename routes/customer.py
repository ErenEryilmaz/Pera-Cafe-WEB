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


@router.get("/campaigns")
async def campaigns():
    """Müşteriye yalnızca aktif ve tarihi geçerli kampanyaları döndürür."""
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute(
            """SELECT * FROM campaigns
               WHERE is_active = TRUE
                 AND (start_date IS NULL OR start_date <= CURDATE())
                 AND (end_date   IS NULL OR end_date   >= CURDATE())
               ORDER BY created_at DESC"""
        )
        rows = cur.fetchall()
        db.close()
    except Exception:
        return []

    result = []
    for row in rows:
        cfg = row.get("config")
        if isinstance(cfg, (bytes, bytearray)):
            cfg = cfg.decode("utf-8")
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                cfg = {}
        result.append({
            "id":          row["id"],
            "title":       row["title"],
            "description": row.get("description"),
            "type":        row["type"],
            "config":      cfg or {},
            "badge_color": row.get("badge_color") or "#E67E22",
            "start_date":  str(row["start_date"]) if row.get("start_date") else None,
            "end_date":    str(row["end_date"]) if row.get("end_date") else None,
        })
    return result


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
        bot = resp.text

        match = re.search(r"SIPARIS_JSON:(.*)", bot, re.DOTALL)
        cart = None
        clean = bot
        if match:
            clean = bot.replace(match.group(0), "").strip()
            try:
                cart = json.loads(match.group(1).strip())
            except:
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
        cur = db.cursor()
        total = sum(i.get("qty", 1) * i.get("price", 0) for i in req.items)
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
