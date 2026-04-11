from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import mysql.connector
import json
import re
from gtts import gTTS
import io
import base64
import os
from dotenv import load_dotenv

load_dotenv()

MY_API_KEY   = os.getenv("GOOGLE_API_KEY")
DB_HOST      = os.getenv("MYSQL_HOST")
DB_PORT      = os.getenv("MYSQL_PORT")
DB_USER      = os.getenv("MYSQL_USER")
DB_PASSWORD  = os.getenv("MYSQL_PASSWORD")
DB_NAME      = os.getenv("MYSQL_DATABASE")

app = FastAPI(title="Pera Kafe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




# ── VERİ MODELLERİ ──────────────────────────────────────────
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
    lang: str = "tr"   # "tr" | "en" | "ar"

# ── VERİTABANI ──────────────────────────────────────────────
def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=int(DB_PORT),
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl_disabled=False
    )

def get_menu_data():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.callproc('GetActiveMenu')
        rows = []
        for result in cursor.stored_results():
            rows.extend(result.fetchall())
        db.close()

        menu_dict = {}
        ai_text   = "CURRENT PRICE LIST:\n"

        for row in rows:
            kategori = row['CategoryName']
            urun     = row['ProductName']
            fiyat    = float(row['BasePrice'])
            is_cold  = row['IsCold']

            if kategori not in menu_dict:
                menu_dict[kategori] = []

            sicaklik      = "🧊 Cold" if is_cold else "☕ Hot"
            fiyat_gorunum = f"Price: {fiyat}₺ | Type: {sicaklik}"
            ai_fiyat      = f"- {urun} ({sicaklik}): {fiyat} TL"

            menu_dict[kategori].append({
                "urun": urun,
                "fiyat_gorunum": fiyat_gorunum,
                "taban_fiyat": fiyat
            })
            ai_text += ai_fiyat + "\n"

        return menu_dict, ai_text

    except Exception as e:
        print(f"MySQL Hatası: {e}")
        return {}, "Database error."

# ── DİL BAZLI SİSTEM TALİMATLARI ────────────────────────────
def build_system_prompt(lang: str, user_name: str, menu_text: str) -> str:
    name_line = {
        "tr": f'Müşterinin adı: "{user_name}". Ona ismiyle, çok samimi bir şekilde hitap et.' if user_name and user_name != "Misafir" else "Müşteri anonim.",
        "en": f'The customer\'s name is "{user_name}". Address them warmly by name.' if user_name and user_name not in ("Misafir","Guest") else "The customer is anonymous.",
        "ar": f'اسم العميل: "{user_name}". خاطبه بحرارة باسمه.' if user_name and user_name not in ("Misafir","Guest","ضيف") else "العميل مجهول.",
    }.get(lang, "")

    prompts = {
        "tr": f"""Sen "Pera Kafe"nin sıcakkanlı garsonusun. Adın Pera.
KONUŞMA DİLİ: Sadece TÜRKÇE konuş. Asla başka dil kullanma.
KİŞİLİK: Kısa, samimi, arkadaşça. Zaman zaman öneri sun. Emoji kullanabilirsin (☕ 😊 🧁).
{name_line}
MENÜ: {menu_text}
SİPARİŞ KURALI: Sipariş değişikliği olursa sepetin SON HALİNİ JSON olarak cümlenin SONUNA ekle.
"3 tane Çay" → JSON'a 3 AYRI çay objesi ekle.
FORMAT: SIPARIS_JSON:[{{"ad": "Ürün Adı", "fiyat": 00}}]""",

        "en": f"""You are Pera, the friendly waiter at "Pera Kafe".
LANGUAGE: Speak ONLY in English. Never use another language.
PERSONALITY: Short, warm, friendly responses. Occasionally suggest items. You may use emojis (☕ 😊 🧁).
{name_line}
MENU: {menu_text}
ORDER RULE: When an order changes, append the FULL cart as JSON at the END of your reply.
"3 teas" → add 3 SEPARATE tea objects to JSON.
FORMAT: SIPARIS_JSON:[{{"ad": "Product Name", "fiyat": 00}}]""",

        "ar": f"""أنت "بيرا"، النادل الودود في "بيرا كافيه".
لغة المحادثة: تحدّث باللغة العربية فقط. لا تستخدم أي لغة أخرى.
الشخصية: ردود قصيرة وودودة. اقترح أحياناً بعض العناصر. يمكنك استخدام الرموز التعبيرية (☕ 😊 🧁).
{name_line}
القائمة: {menu_text}
قاعدة الطلب: عند أي تغيير في الطلب، أضف السلة الكاملة بصيغة JSON في نهاية ردك.
"3 شايات" → أضف 3 عناصر شاي منفصلة.
الصيغة: SIPARIS_JSON:[{{"ad": "اسم المنتج", "fiyat": 00}}]""",
    }

    return prompts.get(lang, prompts["tr"])

# ── TTS ─────────────────────────────────────────────────────
GTTS_LANG_MAP = {"tr": "tr", "en": "en", "ar": "ar"}

def generate_audio_base64(text: str, lang: str = "tr") -> str | None:
    try:
        gtts_lang = GTTS_LANG_MAP.get(lang, "tr")
        tts = gTTS(text=text, lang=gtts_lang)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        print(f"TTS Hatası: {e}")
        return None

# ── ENDPOINT'LER ─────────────────────────────────────────────
@app.post("/login")
async def login_endpoint(request: LoginRequest):
    try:
        db     = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT first_name FROM members WHERE phone = %s", (request.phone,))
        user = cursor.fetchone()
        db.close()
        if user:
            return {"success": True, "name": user["first_name"]}
        else:
            return {"success": False, "message": "Not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/register")
async def register_endpoint(request: RegisterRequest):
    try:
        db     = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "INSERT INTO members (phone, first_name, last_name) VALUES (%s, %s, %s)",
            (request.phone, request.first_name, request.last_name)
        )
        db.commit()
        db.close()
        return {"success": True}
    except mysql.connector.Error as err:
        if "zaten kayıtlı" in str(err) or "Duplicate entry" in str(err):
            return {"success": False, "message": "Bu numara zaten kayıtlı."}
        raise HTTPException(status_code=500, detail=f"DB Error: {err}")
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/menu")
async def fetch_menu():
    menu_db, _ = get_menu_data()
    return {"menu": menu_db}


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    _, menu_text = get_menu_data()
    lang         = request.lang if request.lang in ("tr", "en", "ar") else "tr"
    system_inst  = build_system_prompt(lang, request.user_name, menu_text)

    try:
        genai.configure(api_key=MY_API_KEY)
        try:
            available  = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            model_name = next((m for m in available if "flash" in m), "models/gemini-1.5-flash-latest")
        except:
            model_name = "gemini-1.5-flash"

        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_inst)

        history = []
        for msg in request.messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            history.append({"role": role, "parts": [msg.content]})

        chat     = model.start_chat(history=history)
        response = chat.send_message(request.messages[-1].content)
        bot_text = response.text

        siparis_match = re.search(r"SIPARIS_JSON:(.*)", bot_text, re.DOTALL)
        json_data  = None
        clean_text = bot_text

        if siparis_match:
            clean_text = bot_text.replace(siparis_match.group(0), "").strip()
            try:
                json_data = json.loads(siparis_match.group(1).strip())
            except:
                pass

        audio_b64 = generate_audio_base64(clean_text, lang)

        return {
            "reply":        clean_text,
            "cart":         json_data,
            "audio_base64": audio_b64
        }
    

    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    # Static dosyaları serve et
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ana sayfaya girince login'e yönlendir
@app.get("/")
async def root():
    return RedirectResponse(url="/static/perakafe_login.html")
