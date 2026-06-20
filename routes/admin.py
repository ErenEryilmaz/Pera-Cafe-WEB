import json

from fastapi import APIRouter, HTTPException, Depends

from auth import verify_token, create_admin_token, revoke_token, TOKEN_TTL
from database import get_db
from models import (
    AdminLoginReq, ProductUpdateReq, ProductCreateReq,
    CategoryCreateReq, OrderStatusReq,
    CampaignCreateReq, CampaignUpdateReq,
)

router = APIRouter(prefix="/admin")


def _format_campaign(row: dict) -> dict:
    """DB satırını frontend'in beklediği biçime çevir:
    config -> dict, tarihler -> 'YYYY-MM-DD' string/None, is_active -> bool."""
    cfg = row.get("config")
    if isinstance(cfg, (bytes, bytearray)):
        cfg = cfg.decode("utf-8")
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    return {
        "id":          row["id"],
        "title":       row["title"],
        "description": row.get("description"),
        "type":        row["type"],
        "config":      cfg or {},
        "badge_color": row.get("badge_color") or "#E67E22",
        "is_active":   bool(row.get("is_active")),
        "start_date":  str(row["start_date"]) if row.get("start_date") else None,
        "end_date":    str(row["end_date"]) if row.get("end_date") else None,
    }


# ── Auth ─────────────────────────────────────────────────────

@router.post("/login")
async def admin_login(req: AdminLoginReq):
    token = create_admin_token(req.username, req.password)
    return {"token": token, "expires_in": TOKEN_TTL}


@router.post("/logout")
async def admin_logout(token: str = Depends(verify_token)):
    revoke_token(token)
    return {"success": True}


# ── Debug ─────────────────────────────────────────────────────

@router.get("/db-ping")
async def db_ping():
    import traceback
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT VERSION(), NOW(), DATABASE()")
        row = cur.fetchone()
        db.close()
        return {"status": "ok", "mysql_version": row[0], "server_time": str(row[1]), "database": row[2]}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


# ── Dashboard ────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(_: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.callproc("GetDashboardStats")
        results = list(cur.stored_results())
        stats = results[0].fetchone()
        weekly = results[1].fetchall()
        db.close()
        return {
            "today_orders":   stats["today_orders"],
            "today_revenue":  float(stats["today_revenue"]),
            "pending_orders": stats["pending_orders"],
            "low_stock_count": stats["low_stock_count"],
            "total_members":  stats["total_members"],
            "weekly_revenue": [{"day": str(r["day"]), "rev": float(r["rev"])} for r in weekly],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Siparişler ───────────────────────────────────────────────

@router.get("/orders")
async def get_orders(status: str = "all", limit: int = 50, _: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        if status == "all":
            cur.execute("SELECT * FROM Orders ORDER BY CreatedAt DESC LIMIT %s", (limit,))
        else:
            cur.execute("SELECT * FROM Orders WHERE Status=%s ORDER BY CreatedAt DESC LIMIT %s", (status, limit))
        orders = cur.fetchall()
        for o in orders:
            cur.execute("SELECT * FROM OrderItems WHERE OrderID=%s", (o["OrderID"],))
            o["items"] = cur.fetchall()
            o["CreatedAt"] = str(o["CreatedAt"])
            o["UpdatedAt"] = str(o.get("UpdatedAt", ""))
        db.close()
        return orders
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/orders/{order_id}/status")
async def update_order_status(order_id: int, req: OrderStatusReq, _: str = Depends(verify_token)):
    valid = ("pending", "preparing", "ready", "completed", "cancelled")
    if req.status not in valid:
        raise HTTPException(400, f"Geçersiz durum. Geçerli değerler: {valid}")
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE Orders SET Status=%s WHERE OrderID=%s", (req.status, order_id))
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/orders/{order_id}")
async def delete_order(order_id: int, _: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor()
        cur.callproc("DeleteOrder", (order_id,))
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Ürünler ──────────────────────────────────────────────────

@router.get("/products")
async def get_products(_: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
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
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/products/{product_id}")
async def update_product(product_id: int, req: ProductUpdateReq, _: str = Depends(verify_token)):
    fields, vals = [], []
    if req.name      is not None: fields.append("ProductName=%s");   vals.append(req.name)
    if req.price     is not None: fields.append("BasePrice=%s");     vals.append(req.price)
    if req.stock     is not None: fields.append("StockQuantity=%s"); vals.append(req.stock)
    if req.is_active is not None: fields.append("IsActive=%s");      vals.append(req.is_active)
    if req.is_cold   is not None: fields.append("IsCold=%s");        vals.append(req.is_cold)
    if not fields:
        return {"success": True, "message": "Değişiklik yok."}
    vals.append(product_id)
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(f"UPDATE products SET {', '.join(fields)} WHERE ProductID=%s", vals)
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/products")
async def add_product(req: ProductCreateReq, _: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO products (CategoryID, ProductName, BasePrice, StockQuantity, IsCold, IsActive) VALUES (%s,%s,%s,%s,%s,1)",
            (req.category_id, req.name, req.price, req.stock, req.is_cold),
        )
        db.commit()
        new_id = cur.lastrowid
        db.close()
        return {"success": True, "product_id": new_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/products/{product_id}")
async def delete_product(product_id: int, _: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE products SET IsActive=0 WHERE ProductID=%s", (product_id,))
        db.commit()
        db.close()
        return {"success": True, "message": "Ürün pasife alındı."}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Kategoriler ──────────────────────────────────────────────

@router.get("/categories")
async def get_categories(_: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM categories ORDER BY CategoryName")
        cats = cur.fetchall()
        db.close()
        return cats
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/categories")
async def add_category(req: CategoryCreateReq, _: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO categories (CategoryName) VALUES (%s)", (req.name,))
        db.commit()
        new_id = cur.lastrowid
        db.close()
        return {"success": True, "category_id": new_id}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Stok ─────────────────────────────────────────────────────

@router.get("/stock")
async def get_stock(_: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT p.ProductID, p.ProductName, c.CategoryName,
                   COALESCE(p.StockQuantity,50) AS StockQuantity,
                   COALESCE(p.IsActive,1) AS IsActive
            FROM products p
            JOIN categories c ON p.CategoryID=c.CategoryID
            ORDER BY p.StockQuantity ASC, p.ProductName
        """)
        rows = cur.fetchall()
        db.close()
        return rows
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/stock/{product_id}")
async def update_stock(product_id: int, body: dict, _: str = Depends(verify_token)):
    qty = body.get("stock")
    if qty is None:
        raise HTTPException(400, "stock alanı gerekli.")
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE products SET StockQuantity=%s WHERE ProductID=%s", (qty, product_id))
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Üyeler ───────────────────────────────────────────────────

@router.get("/members")
async def get_members(_: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        # GROUP BY kullanmıyoruz: ONLY_FULL_GROUP_BY modunda (DigitalOcean MySQL'de
        # varsayılan açık) gruplanmamış sütunlar hata veriyordu. Korelasyonlu alt
        # sorgular hem bundan kaçınır hem de iptal edilen siparişleri hariç tutar.
        # SELECT m.* sayesinde tablo şemasındaki (id/created_at) farklılıklara dayanıklı.
        cur.execute("""
            SELECT m.*,
                   (SELECT COUNT(*) FROM Orders o
                      WHERE o.MemberPhone = m.phone AND o.Status <> 'cancelled') AS order_count,
                   (SELECT COALESCE(SUM(o.TotalAmount), 0) FROM Orders o
                      WHERE o.MemberPhone = m.phone AND o.Status <> 'cancelled') AS total_spent
            FROM members m
        """)
        rows = cur.fetchall()
        for r in rows:
            # created_at sütunu eski tablolarda olmayabilir → güvenli dönüştür
            r["created_at"]  = str(r["created_at"]) if r.get("created_at") else None
            r["total_spent"] = float(r["total_spent"]) if r.get("total_spent") is not None else 0.0
            r["order_count"] = int(r.get("order_count") or 0)
            r.setdefault("first_name", "")
            r.setdefault("last_name", "")
        db.close()
        # En yeni üye üstte (created_at varsa); yoksa mevcut sırayı korur
        rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return rows
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Raporlar ─────────────────────────────────────────────────
# Not: İptal edilen siparişler tüm raporların dışında tutulur (Status <> 'cancelled'),
# bu da üyeler endpoint'indeki ciro mantığıyla tutarlı.

@router.get("/reports/top-products")
async def report_top_products(limit: int = 8, _: str = Depends(verify_token)):
    """En çok satan ürünler — satılan adet ve ciroya göre."""
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT oi.ProductName,
                   SUM(oi.Quantity)                AS total_qty,
                   SUM(oi.Quantity * oi.UnitPrice) AS total_revenue
            FROM OrderItems oi
            JOIN Orders o ON oi.OrderID = o.OrderID
            WHERE o.Status <> 'cancelled'
            GROUP BY oi.ProductName
            ORDER BY total_qty DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        db.close()
        for r in rows:
            r["total_qty"]     = int(r["total_qty"] or 0)
            r["total_revenue"] = float(r["total_revenue"] or 0)
        return rows
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/reports/categories")
async def report_categories(_: str = Depends(verify_token)):
    """Kategori bazlı ciro. OrderItems şemada ProductID tutmadığı için
    ürün adıyla products'a bağlanır; adı eşleşmeyen kalemler kapsam dışı kalır."""
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT c.CategoryName,
                   SUM(oi.Quantity * oi.UnitPrice) AS total_revenue
            FROM OrderItems oi
            JOIN Orders     o ON oi.OrderID = o.OrderID
            JOIN products   p ON oi.ProductName = p.ProductName
            JOIN categories c ON p.CategoryID = c.CategoryID
            WHERE o.Status <> 'cancelled'
            GROUP BY c.CategoryID, c.CategoryName
            ORDER BY total_revenue DESC
        """)
        rows = cur.fetchall()
        db.close()
        for r in rows:
            r["total_revenue"] = float(r["total_revenue"] or 0)
        return rows
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/reports/hourly")
async def report_hourly(_: str = Depends(verify_token)):
    """Son 30 günde saat bazlı sipariş yoğunluğu. Sipariş olmayan saatler de
    0 ile döner ki frontend'deki 24 saatlik grafikte boşluk kalmasın."""
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT HOUR(o.CreatedAt) AS hour, COUNT(*) AS order_count
            FROM Orders o
            WHERE o.Status <> 'cancelled'
              AND o.CreatedAt >= NOW() - INTERVAL 30 DAY
            GROUP BY HOUR(o.CreatedAt)
        """)
        rows = cur.fetchall()
        db.close()
        counts = {int(r["hour"]): int(r["order_count"]) for r in rows}
        return [{"hour": h, "order_count": counts.get(h, 0)} for h in range(24)]
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Kampanyalar ──────────────────────────────────────────────

VALID_CAMP_TYPES = ("buy_x_get_y", "percentage", "fixed")


@router.get("/campaigns")
async def get_campaigns(_: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        rows = cur.fetchall()
        db.close()
        return [_format_campaign(r) for r in rows]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/campaigns")
async def add_campaign(req: CampaignCreateReq, _: str = Depends(verify_token)):
    if req.type not in VALID_CAMP_TYPES:
        raise HTTPException(400, f"Geçersiz tip. Geçerli değerler: {VALID_CAMP_TYPES}")
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """INSERT INTO campaigns
               (title, description, type, config, badge_color, is_active, start_date, end_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                req.title, req.description, req.type, json.dumps(req.config),
                req.badge_color, req.is_active,
                req.start_date or None, req.end_date or None,
            ),
        )
        db.commit()
        new_id = cur.lastrowid
        db.close()
        return {"success": True, "campaign_id": new_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, req: CampaignUpdateReq, _: str = Depends(verify_token)):
    if req.type is not None and req.type not in VALID_CAMP_TYPES:
        raise HTTPException(400, f"Geçersiz tip. Geçerli değerler: {VALID_CAMP_TYPES}")
    fields, vals = [], []
    if req.title       is not None: fields.append("title=%s");       vals.append(req.title)
    if req.description is not None: fields.append("description=%s"); vals.append(req.description)
    if req.type        is not None: fields.append("type=%s");        vals.append(req.type)
    if req.config      is not None: fields.append("config=%s");      vals.append(json.dumps(req.config))
    if req.badge_color is not None: fields.append("badge_color=%s"); vals.append(req.badge_color)
    if req.is_active   is not None: fields.append("is_active=%s");   vals.append(req.is_active)
    if req.start_date  is not None: fields.append("start_date=%s");  vals.append(req.start_date or None)
    if req.end_date    is not None: fields.append("end_date=%s");    vals.append(req.end_date or None)
    if not fields:
        return {"success": True, "message": "Değişiklik yok."}
    vals.append(campaign_id)
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(f"UPDATE campaigns SET {', '.join(fields)} WHERE id=%s", vals)
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: int, _: str = Depends(verify_token)):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("DELETE FROM campaigns WHERE id=%s", (campaign_id,))
        db.commit()
        db.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
