import io
import base64
import os
import requests


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
            f'Sen "Pera Kafe"nin {persona["tr"]}. Sadece TÜRKÇE. Her zaman sıcak, tatlı dilli '
            f've nazik konuş; kısa tut (1-2 cümle), gereksiz uzatma. Menüde OLMAYAN bir ürün '
            f'ya da alakasız bir soru gelirse tatlı bir dille özür dileyip siparişe yönlendir, '
            f'örn: "Üzgünüm, o konuda maalesef yardımcı olamıyorum ama siparişinizle ilgili '
            f'memnuniyetle yardımcı olurum." {n}\n'
            f'MENÜ: {menu_text}\n'
            f'Sepet her değiştiğinde GÜNCEL sepeti TAMAMEN gönder: {fmt}\n'
            f'Ürün çıkarılınca o ürünü listeden SİL (qty:0 yazma). Her zaman tüm aktif sepeti gönder.'
        ),
        "en": (
            f'You are {persona["en"]} at Pera Kafe. ENGLISH only. Always warm, sweet and polite; '
            f'keep it short (1-2 sentences), no rambling. If an item is NOT on the menu or the '
            f'question is unrelated, apologize sweetly and gently steer back to the order, e.g. '
            f'"I\'m so sorry, I can\'t help with that, but I\'d be happy to help with your order." {n}\n'
            f'MENU: {menu_text}\n'
            f'When order changes send FULL updated cart: {fmt}\n'
            f'To remove item, OMIT it from list (do not send qty:0). Always send complete active cart.'
        ),
        "ar": (
            f'أنت {persona["ar"]} في بيرا كافيه. العربية فقط. كن دائماً ودوداً ولطيفاً ومهذباً؛ '
            f'اجعل ردك قصيراً (جملة أو جملتين) دون إطالة. إذا طُلب صنف غير موجود في القائمة أو كان '
            f'السؤال غير متعلق، فاعتذر بلطف ووجّه العميل إلى الطلب، مثلاً: '
            f'"عذراً، لا أستطيع المساعدة في ذلك، لكن يسعدني مساعدتك في طلبك." {n}\n'
            f'القائمة: {menu_text}\n'
            f'عند تغيير الطلب أرسل السلة كاملة: {fmt}\n'
            f'لإزالة منتج احذفه من القائمة. أرسل السلة الكاملة دائماً.'
        ),
    }.get(lang, "")


def make_audio_b64(text: str, lang: str = "tr", gender: str = "female") -> str | None:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return None

    # Dil + cinsiyet kombinasyonuna göre voice ID
    # ElevenLabs Voice Library'den beğendiğin sesleri buraya yaz
    VOICE_IDS = {
        "tr": {
            "female": "EXAVITQu4vr4xnSDxMaL",   # Bella — kadın
            "male":   "pNInz6obpgDQGcFmaJgB",   # Adam  — erkek
        },
        "en": {
            "female": "21m00Tcm4TlvDq8ikWAM",   # Rachel
            "male":   "onwK4e9ZLuTAKqWW03F9",   # Daniel
        },
        "ar": {
            "female": "XB0fDUnXU5powFXDhCwa",   # Charlotte (multilingual)
            "male":   "N2lVS1w4EtoT3dr4eOWO",   # Callum (multilingual)
        },
    }

    voice_id = VOICE_IDS.get(lang, VOICE_IDS["tr"]).get(gender, "female")

    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                # Düşük gecikmeli model: multilingual_v2'ye göre çok daha hızlı,
                # TR/EN/AR destekli. Daha da hızlısı için: "eleven_flash_v2_5".
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
            timeout=15,
        )
        response.raise_for_status()
        return base64.b64encode(response.content).decode()
    except Exception as e:
        print(f"ElevenLabs TTS hatası: {e}")
        return None
