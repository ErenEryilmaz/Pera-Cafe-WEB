import os
import mysql.connector

DB_HOST     = os.getenv("MYSQL_HOST")
DB_PORT     = os.getenv("MYSQL_PORT")
DB_USER     = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DB_NAME     = os.getenv("MYSQL_DATABASE")

CA_CERT = os.path.join(os.path.dirname(__file__), "ca-certificate.crt")


def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        port=int(DB_PORT),
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl_ca=CA_CERT,
        ssl_verify_identity=False,
        connection_timeout=10,
    )


def get_menu_data():
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.callproc("GetActiveMenu")
        rows = []
        for r in cur.stored_results():
            rows.extend(r.fetchall())
        db.close()

        menu_dict = {}
        ai_text = "GÜNCEL FİYAT LİSTESİ:\n"
        for row in rows:
            cat = row["CategoryName"]
            urun = row["ProductName"]
            fiyat = float(row["BasePrice"])
            cold = row["IsCold"]
            if cat not in menu_dict:
                menu_dict[cat] = []
            s = "🧊 Soğuk" if cold else "☕ Sıcak"
            menu_dict[cat].append({
                "urun": urun,
                "fiyat_gorunum": f"Fiyat: {fiyat}₺ | {s}",
                "taban_fiyat": fiyat,
            })
            ai_text += f"- {urun} ({s}): {fiyat} TL\n"
        return menu_dict, ai_text
    except Exception as e:
        print(f"DB: {e}")
        return {}, "DB hatası."
