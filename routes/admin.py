from fastapi import APIRouter, HTTPException, Depends

from auth import verify_token, create_admin_token, revoke_token, TOKEN_TTL
from database import get_db
from models import (
    AdminLoginReq, ProductUpdateReq, ProductCreateReq,
    CategoryCreateReq, OrderStatusReq,
)

router = APIRouter(prefix="/admin")


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
        db.close()
        return rows
    except Exception as e:
        raise HTTPException(500, str(e))
