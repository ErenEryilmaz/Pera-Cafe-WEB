import io
import base64
from gtts import gTTS


def build_prompt(lang: str, user_name: str, menu_text: str, gender: str = "female") -> str:
    n = {
        "tr": f'Müşterinin adı: "{user_name}". Ona ismiyle hitap et.' if user_name and user_name != "Misafir" else "Müşteri anonim.",
        "en": f'Customer name: "{user_name}".' if user_name not in ("Misafir", "Guest", "") else "Anonymous.",
        "ar": f'اسم العميل: "{user_name}".' if user_name not in ("Misafir", "", "Guest", "ضيف") else "مجهول.",
    }.get(lang, "")

    # Cinsiyete göre garson kimliği
    if gender == "male":
        persona = {"tr": "garson, adın Kaan", "en": "waiter named Kaan", "ar": "نادل اسمه كان"}
    else:
        persona = {"tr": "garson, adın Pera", "en": "waitress named Pera", "ar": "نادلة اسمها بيرا"}

    fmt = 'SIPARIS_JSON:[{"ad":"Ürün Adı","fiyat":10,"qty":2}]'
    return {
        "tr": (
            f'Sen "Pera Kafe"nin {persona["tr"]}. Sadece TÜRKÇE. Kısa, samimi. {n}\n'
            f'MENÜ: {menu_text}\n'
            f'Sepet her değiştiğinde GÜNCEL sepeti TAMAMEN gönder: {fmt}\n'
            f'Ürün çıkarılınca o ürünü listeden SİL (qty:0 yazma). Her zaman tüm aktif sepeti gönder.'
        ),
        "en": (
            f'You are {persona["en"]} at Pera Kafe. ENGLISH only. Short, friendly. {n}\n'
            f'MENU: {menu_text}\n'
            f'When order changes send FULL updated cart: {fmt}\n'
            f'To remove item, OMIT it from list (do not send qty:0). Always send complete active cart.'
        ),
        "ar": (
            f'أنت {persona["ar"]} في بيرا كافيه. العربية فقط. {n}\n'
            f'القائمة: {menu_text}\n'
            f'عند تغيير الطلب أرسل السلة كاملة: {fmt}\n'
            f'لإزالة منتج احذفه من القائمة. أرسل السلة الكاملة دائماً.'
        ),
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
