-- ================================================================
-- PERA KAFE — Tam Veritabanı Kurulum Script'i (temiz, sıralı sürüm)
-- ----------------------------------------------------------------
-- Bu dosya SIFIRDAN kurulum içindir: şema + başlangıç verisi +
-- trigger/prosedürler. Baştan sona tek seferde çalışır.
--
-- ⚠️ DİKKAT: İlk satır veritabanını KOMPLE SİLER. Canlı/dolu bir
--    veritabanında ÇALIŞTIRMA — tüm siparişler, üyeler vb. gider.
--    Sadece temiz/yeni kurulum için.
--
-- Not: Ürünlerde IsAvailable YOK; aktif/pasif durumu IsActive ile
--      yönetilir (menü ve sipariş kontrolü bu sütuna bakar).
-- ================================================================

DROP DATABASE IF EXISTS peracafe;
CREATE DATABASE peracafe;
USE peracafe;


-- ================================================================
-- 1. TABLOLAR  (bağımlılık sırasına göre: önce ana tablo, sonra FK'lılar)
-- ================================================================

-- 1.1 Kategoriler
CREATE TABLE categories (
    CategoryID      INT AUTO_INCREMENT PRIMARY KEY,
    CategoryName    VARCHAR(100) NOT NULL,
    CategoryName_en VARCHAR(100) CHARACTER SET utf8mb4 NULL,
    CategoryName_ar VARCHAR(100) CHARACTER SET utf8mb4 NULL
);

-- 1.2 Ürünler  (categories'e bağlı)
CREATE TABLE products (
    ProductID      INT AUTO_INCREMENT PRIMARY KEY,
    CategoryID     INT,
    ProductName    VARCHAR(150) NOT NULL,
    ProductName_en VARCHAR(150) CHARACTER SET utf8mb4 NULL,
    ProductName_ar VARCHAR(150) CHARACTER SET utf8mb4 NULL,
    BasePrice      DECIMAL(10,2) NOT NULL,
    IsCold         BOOLEAN DEFAULT FALSE,
    StockQuantity  INT DEFAULT 50,
    IsActive       BOOLEAN DEFAULT TRUE,          -- aktif/pasif (menü + sipariş bunu kullanır)
    FOREIGN KEY (CategoryID) REFERENCES categories(CategoryID) ON DELETE CASCADE
);

-- 1.3 Üyeler
CREATE TABLE members (
    user_id    INT AUTO_INCREMENT PRIMARY KEY,
    phone      VARCHAR(20),
    first_name VARCHAR(100),
    last_name  VARCHAR(100)
);

-- 1.4 Oturumlar  (members'a bağlı)
CREATE TABLE sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NULL,
    is_guest   BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL 15 MINUTE),
    FOREIGN KEY (user_id) REFERENCES members(user_id) ON DELETE CASCADE
);

-- 1.5 Siparişler
CREATE TABLE Orders (
    OrderID     INT PRIMARY KEY AUTO_INCREMENT,
    TableNo     VARCHAR(20)  DEFAULT 'Kiosk',
    MemberPhone VARCHAR(15)  DEFAULT NULL,
    Status      ENUM('pending','preparing','ready','completed','cancelled') DEFAULT 'pending',
    TotalAmount DECIMAL(10,2) DEFAULT 0,
    CreatedAt   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    Notes       TEXT DEFAULT NULL
);

-- 1.6 Sipariş kalemleri  (Orders'a bağlı)
CREATE TABLE OrderItems (
    ItemID      INT PRIMARY KEY AUTO_INCREMENT,
    OrderID     INT NOT NULL,
    ProductName VARCHAR(150) NOT NULL,
    Quantity    INT DEFAULT 1,
    UnitPrice   DECIMAL(8,2) NOT NULL,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
);

-- 1.7 Kampanyalar
CREATE TABLE campaigns (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(150) CHARACTER SET utf8mb4 NOT NULL,
    description TEXT CHARACTER SET utf8mb4 NULL,
    -- Kampanya tipi: X alana Y bedava / yüzde indirim / sabit tutar indirim
    type        ENUM('buy_x_get_y','percentage','fixed') NOT NULL,
    -- Tipe göre ayarlar:  buy_x_get_y -> {"buy":2,"get":1}
    --                     percentage  -> {"percent":10}
    --                     fixed       -> {"amount":20}
    config      JSON NOT NULL,
    -- Kapsam: tüm menü / belirli kategori / belirli ürün(ler)
    scope_type  ENUM('all','category','product') NOT NULL DEFAULT 'all',
    scope_ids   JSON NULL,                 -- kategori ID'leri ya da ürün ID'leri
    badge_color VARCHAR(20) DEFAULT '#E67E22',
    is_active   BOOLEAN DEFAULT TRUE,
    start_date  DATE NULL,
    end_date    DATE NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ================================================================
-- 2. BAŞLANGIÇ VERİSİ
-- ================================================================

-- 2.1 Kategoriler (ID'ler sırasıyla 1..5 olur)
INSERT INTO categories (CategoryName) VALUES
('Sıcak Kahveler'),
('Soğuk Kahveler'),
('Çaylar ve Diğer İçecekler'),
('Tatlılar'),
('Tuzlular ve Atıştırmalıklar');

-- 2.2 Ürünler  (StockQuantity ve IsActive varsayılanları otomatik gelir)
-- Sıcak Kahveler (CategoryID = 1)
INSERT INTO products (CategoryID, ProductName, BasePrice, IsCold) VALUES
(1, 'Espresso (Single)', 60.00, FALSE),
(1, 'Espresso (Double)', 80.00, FALSE),
(1, 'Americano', 85.00, FALSE),
(1, 'Filtre Kahve', 75.00, FALSE),
(1, 'Caffe Latte', 95.00, FALSE),
(1, 'Cappuccino', 95.00, FALSE),
(1, 'Caffe Mocha', 110.00, FALSE);

-- Soğuk Kahveler (CategoryID = 2)
INSERT INTO products (CategoryID, ProductName, BasePrice, IsCold) VALUES
(2, 'Iced Americano', 90.00, TRUE),
(2, 'Iced Latte', 100.00, TRUE),
(2, 'Cold Brew', 120.00, TRUE),
(2, 'Iced Mocha', 115.00, TRUE),
(2, 'Karamel Frappé', 130.00, TRUE);

-- Çaylar ve Diğer İçecekler (CategoryID = 3)
INSERT INTO products (CategoryID, ProductName, BasePrice, IsCold) VALUES
(3, 'Türk Çayı', 30.00, FALSE),
(3, 'Yeşil Çay', 60.00, FALSE),
(3, 'Ev Yapımı Limonata', 80.00, TRUE),
(3, 'Sıcak Çikolata', 95.00, FALSE);

-- Tatlılar (CategoryID = 4)
INSERT INTO products (CategoryID, ProductName, BasePrice, IsCold) VALUES
(4, 'San Sebastian Cheesecake', 180.00, FALSE),
(4, 'Limonlu Cheesecake', 170.00, FALSE),
(4, 'Tiramisu', 160.00, FALSE),
(4, 'Islak Kek (Brownie)', 140.00, FALSE);

-- Tuzlular ve Atıştırmalıklar (CategoryID = 5)
INSERT INTO products (CategoryID, ProductName, BasePrice, IsCold) VALUES
(5, 'Hindi Füme Kaşarlı Sandviç', 150.00, FALSE),
(5, 'Izgara Tavuklu Wrap', 180.00, FALSE),
(5, 'Ezine Peynirli Tost', 120.00, FALSE);

-- 2.3 Test üyesi
INSERT INTO members (phone, first_name, last_name) VALUES ('5551115511', 'Eren', 'Eryılmaz');


-- ================================================================
-- 3. ÇOK DİLLİ ÇEVİRİLER (EN / AR)  — temel veri girildikten sonra
-- ================================================================

-- 3.1 Kategori çevirileri
UPDATE categories SET CategoryName_en = 'Hot Coffees',          CategoryName_ar = 'قهوة ساخنة'                 WHERE CategoryName = 'Sıcak Kahveler';
UPDATE categories SET CategoryName_en = 'Cold Coffees',         CategoryName_ar = 'قهوة باردة'                 WHERE CategoryName = 'Soğuk Kahveler';
UPDATE categories SET CategoryName_en = 'Teas & Other Drinks',  CategoryName_ar = 'الشاي ومشروبات أخرى'        WHERE CategoryName = 'Çaylar ve Diğer İçecekler';
UPDATE categories SET CategoryName_en = 'Desserts',             CategoryName_ar = 'حلويات'                     WHERE CategoryName = 'Tatlılar';
UPDATE categories SET CategoryName_en = 'Savory & Snacks',      CategoryName_ar = 'مأكولات مالحة ووجبات خفيفة' WHERE CategoryName = 'Tuzlular ve Atıştırmalıklar';

-- 3.2 Ürün çevirileri
-- Sıcak Kahveler
UPDATE products SET ProductName_en = 'Espresso (Single)', ProductName_ar = 'إسبريسو (مفرد)'   WHERE ProductName = 'Espresso (Single)';
UPDATE products SET ProductName_en = 'Espresso (Double)', ProductName_ar = 'إسبريسو (مزدوج)'  WHERE ProductName = 'Espresso (Double)';
UPDATE products SET ProductName_en = 'Americano',         ProductName_ar = 'أمريكانو'         WHERE ProductName = 'Americano';
UPDATE products SET ProductName_en = 'Filter Coffee',     ProductName_ar = 'قهوة مفلترة'      WHERE ProductName = 'Filtre Kahve';
UPDATE products SET ProductName_en = 'Caffe Latte',       ProductName_ar = 'كافيه لاتيه'      WHERE ProductName = 'Caffe Latte';
UPDATE products SET ProductName_en = 'Cappuccino',        ProductName_ar = 'كابتشينو'         WHERE ProductName = 'Cappuccino';
UPDATE products SET ProductName_en = 'Caffe Mocha',       ProductName_ar = 'كافيه موكا'       WHERE ProductName = 'Caffe Mocha';

-- Soğuk Kahveler
UPDATE products SET ProductName_en = 'Iced Americano',    ProductName_ar = 'أمريكانو مثلج'    WHERE ProductName = 'Iced Americano';
UPDATE products SET ProductName_en = 'Iced Latte',        ProductName_ar = 'لاتيه مثلج'       WHERE ProductName = 'Iced Latte';
UPDATE products SET ProductName_en = 'Cold Brew',         ProductName_ar = 'كولد برو'         WHERE ProductName = 'Cold Brew';
UPDATE products SET ProductName_en = 'Iced Mocha',        ProductName_ar = 'موكا مثلج'        WHERE ProductName = 'Iced Mocha';
UPDATE products SET ProductName_en = 'Caramel Frappé',    ProductName_ar = 'فرابيه بالكراميل' WHERE ProductName = 'Karamel Frappé';

-- Çaylar ve Diğer İçecekler
UPDATE products SET ProductName_en = 'Turkish Tea',       ProductName_ar = 'شاي تركي'         WHERE ProductName = 'Türk Çayı';
UPDATE products SET ProductName_en = 'Green Tea',         ProductName_ar = 'شاي أخضر'         WHERE ProductName = 'Yeşil Çay';
UPDATE products SET ProductName_en = 'Homemade Lemonade', ProductName_ar = 'ليموناضة منزلية'  WHERE ProductName = 'Ev Yapımı Limonata';
UPDATE products SET ProductName_en = 'Hot Chocolate',     ProductName_ar = 'شوكولاتة ساخنة'   WHERE ProductName = 'Sıcak Çikolata';

-- Tatlılar
UPDATE products SET ProductName_en = 'San Sebastian Cheesecake', ProductName_ar = 'تشيز كيك سان سيباستيان' WHERE ProductName = 'San Sebastian Cheesecake';
UPDATE products SET ProductName_en = 'Lemon Cheesecake',         ProductName_ar = 'تشيز كيك بالليمون'      WHERE ProductName = 'Limonlu Cheesecake';
UPDATE products SET ProductName_en = 'Tiramisu',                 ProductName_ar = 'تيراميسو'               WHERE ProductName = 'Tiramisu';
UPDATE products SET ProductName_en = 'Brownie',                  ProductName_ar = 'براوني'                 WHERE ProductName = 'Islak Kek (Brownie)';

-- Tuzlular ve Atıştırmalıklar
UPDATE products SET ProductName_en = 'Smoked Turkey & Cheese Sandwich', ProductName_ar = 'ساندويتش ديك رومي مدخن بالجبن' WHERE ProductName = 'Hindi Füme Kaşarlı Sandviç';
UPDATE products SET ProductName_en = 'Grilled Chicken Wrap',           ProductName_ar = 'راب دجاج مشوي'                  WHERE ProductName = 'Izgara Tavuklu Wrap';
UPDATE products SET ProductName_en = 'Ezine Cheese Toastie',           ProductName_ar = 'توست بجبن إزينه'                WHERE ProductName = 'Ezine Peynirli Tost';


-- ================================================================
-- 4. TRIGGER'LAR & PROSEDÜRLER
-- (Tablolar + veri hazır olduktan sonra; hepsi tek DELIMITER bloğunda)
-- ================================================================
DELIMITER //

-- 4.1 Aynı telefonla ikinci kayıt engeli
CREATE TRIGGER Check_Duplicate_After_Insert
AFTER INSERT ON members
FOR EACH ROW
BEGIN
    DECLARE v_count INT;
    SELECT COUNT(*) INTO v_count FROM members WHERE phone = NEW.phone;
    -- Sayı 1'den büyükse bu numara zaten vardı → hata fırlat (INSERT geri alınır)
    IF v_count > 1 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Bu numara zaten kayıtlı.';
    END IF;
END //

-- 4.2 Sipariş kalemi eklenince stok düş (ürün adı TR/EN/AR'dan biriyle eşleşir)
CREATE TRIGGER TRG_ReduceStock
AFTER INSERT ON OrderItems
FOR EACH ROW
BEGIN
    UPDATE products
    SET StockQuantity = GREATEST(0, StockQuantity - NEW.Quantity)
    WHERE (ProductName    = NEW.ProductName
        OR ProductName_en = NEW.ProductName
        OR ProductName_ar = NEW.ProductName)
      AND StockQuantity > 0;
END //

-- 4.3 AI/menü için aktif menü (yalnızca IsActive = TRUE olan ürünler)
CREATE PROCEDURE GetActiveMenu()
BEGIN
    SELECT
        c.CategoryName,
        COALESCE(c.CategoryName_en, c.CategoryName) AS CategoryName_en,
        COALESCE(c.CategoryName_ar, c.CategoryName) AS CategoryName_ar,
        p.ProductName,
        COALESCE(p.ProductName_en, p.ProductName)   AS ProductName_en,
        COALESCE(p.ProductName_ar, p.ProductName)   AS ProductName_ar,
        p.BasePrice,
        p.IsCold
    FROM products p
    JOIN categories c ON p.CategoryID = c.CategoryID
    WHERE COALESCE(p.IsActive, 1) = TRUE;
END //

-- 4.4 Admin paneli özet istatistikleri
CREATE PROCEDURE GetDashboardStats()
BEGIN
    -- 1. Sonuç: tekil istatistikler
    SELECT
        (SELECT COUNT(*) FROM Orders WHERE DATE(CreatedAt) = CURDATE())                                    AS today_orders,
        (SELECT COALESCE(SUM(TotalAmount),0) FROM Orders WHERE DATE(CreatedAt) = CURDATE())                AS today_revenue,
        (SELECT COUNT(*) FROM Orders WHERE Status IN ('pending','preparing'))                              AS pending_orders,
        (SELECT COUNT(*) FROM products WHERE StockQuantity BETWEEN 0 AND 10 AND StockQuantity != -1)       AS low_stock_count,
        (SELECT COUNT(*) FROM members)                                                                     AS total_members;

    -- 2. Sonuç: son 7 günün ciro grafiği
    SELECT DATE(CreatedAt) AS day, COALESCE(SUM(TotalAmount),0) AS rev
    FROM Orders
    WHERE CreatedAt >= CURDATE() - INTERVAL 6 DAY
    GROUP BY DATE(CreatedAt)
    ORDER BY day;
END //

-- 4.5 Siparişi kalemleriyle birlikte sil
CREATE PROCEDURE DeleteOrder(IN p_OrderID INT)
BEGIN
    DELETE FROM OrderItems WHERE OrderID = p_OrderID;
    DELETE FROM Orders     WHERE OrderID = p_OrderID;
END //

DELIMITER ;
