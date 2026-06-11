"""
Pera Kafe — Ana Giriş Noktası

KURULUM:
  pip install fastapi uvicorn google-generativeai mysql-connector-python gtts python-dotenv bcrypt
  uvicorn main:app --reload --port 8000

.env:
  GOOGLE_API_KEY=...
  MYSQL_HOST=...  MYSQL_PORT=...  MYSQL_USER=...  MYSQL_PASSWORD=...  MYSQL_DATABASE=...
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=admin123   ← İlk çalıştırmada değiştirin!
"""

import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from routes.customer import router as customer_router
from routes.admin import router as admin_router

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pera_debug.log"),
    ],
)
log = logging.getLogger("pera")

app = FastAPI(title="Pera Kafe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CachedStaticFiles(StaticFiles):
    """3D modeller büyük (60MB+) — tarayıcının kesin cache'lemesi için
    explicit Cache-Control ver. HTML/JS ise hep taze kalsın ki
    güncellemeler kullanıcıya anında ulaşsın."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.endswith((".glb", ".gltf", ".png", ".jpg", ".woff2")):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path.endswith((".html", ".js", ".css")):
            response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", CachedStaticFiles(directory="static"), name="static")

app.include_router(customer_router)
app.include_router(admin_router)


@app.get("/")
async def ana_sayfa():
    return RedirectResponse(url="/static/perakafe_login.html")
