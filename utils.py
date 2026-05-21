import io
import base64
from gtts import gTTS


def build_prompt(lang: str, user_name: str, menu_text: str) -> str:
    n = {
        "tr": f'Müşterinin adı: "{user_name}". Ona ismiyle hitap et.' if user_name and user_name != "Misafir" else "Müşteri anonim.",
        "en": f'Customer name: "{user_name}".' if user_name not in ("Misafir", "Guest", "") else "Anonymous.",
        "ar": f'اسم العميل: "{user_name}".' if user_name not in ("Misafir", "", "Guest", "ضيف") else "مجهول.",
    }.get(lang, "")

    return {
        "tr": f'Sen "Pera Kafe"nin garsonusun, adın Pera. Sadece TÜRKÇE. Kısa, samimi. {n}\nMENÜ: {menu_text}\nSipariş değişince: SIPARIS_JSON:[{{"ad":"..","fiyat":0}}]',
        "en": f'You are Pera, waiter at Pera Kafe. ENGLISH only. Short, friendly. {n}\nMENU: {menu_text}\nOrder change: SIPARIS_JSON:[{{"ad":"..","fiyat":0}}]',
        "ar": f'أنت بيرا، نادل في بيرا كافيه. العربية فقط. {n}\nالقائمة: {menu_text}\nSIPARIS_JSON:[{{"ad":"..","fiyat":0}}]',
    }.get(lang, "")


def make_audio_b64(text: str, lang: str = "tr") -> str | None:
    try:
        tts = gTTS(text=text, lang={"tr": "tr", "en": "en", "ar": "ar"}.get(lang, "tr"))
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception as e:
        print(f"TTS: {e}")
        return None
