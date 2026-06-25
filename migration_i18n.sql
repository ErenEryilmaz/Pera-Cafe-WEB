-- ================================================================
-- Pera Kafe — Menü Çoklu Dil (i18n) Migrasyonu
-- Kategori ve ürün adlarına İngilizce (_en) ve Arapça (_ar) ekler.
-- MySQL istemcisinde çalıştırın (DigitalOcean üzerindeki MySQL sunucunuza bağlanarak).
-- ================================================================

USE peracafe;

-- ----------------------------------------------------------------
-- 1. Çeviri sütunlarını ekle (Arapça için utf8mb4 şart)
-- ----------------------------------------------------------------
-- NOT: MySQL "ADD COLUMN IF NOT EXISTS" desteklemez (sadece MariaDB).
-- Bu yüzden düz ALTER TABLE kullanıyoruz. Sütunlar zaten varsa
-- "Duplicate column name" hatası alırsanız bu adımı atlayabilirsiniz.
ALTER TABLE categories
  ADD COLUMN CategoryName_en VARCHAR(100) CHARACTER SET utf8mb4 NULL,
  ADD COLUMN CategoryName_ar VARCHAR(100) CHARACTER SET utf8mb4 NULL;

ALTER TABLE products
  ADD COLUMN ProductName_en VARCHAR(150) CHARACTER SET utf8mb4 NULL,
  ADD COLUMN ProductName_ar VARCHAR(150) CHARACTER SET utf8mb4 NULL;

-- ----------------------------------------------------------------
-- 2. Kategori çevirileri
-- ----------------------------------------------------------------
UPDATE categories SET CategoryName_en = 'Hot Coffees',          CategoryName_ar = 'قهوة ساخنة'              WHERE CategoryName = 'Sıcak Kahveler';
UPDATE categories SET CategoryName_en = 'Cold Coffees',         CategoryName_ar = 'قهوة باردة'              WHERE CategoryName = 'Soğuk Kahveler';
UPDATE categories SET CategoryName_en = 'Teas & Other Drinks',  CategoryName_ar = 'الشاي ومشروبات أخرى'     WHERE CategoryName = 'Çaylar ve Diğer İçecekler';
UPDATE categories SET CategoryName_en = 'Desserts',             CategoryName_ar = 'حلويات'                  WHERE CategoryName = 'Tatlılar';
UPDATE categories SET CategoryName_en = 'Savory & Snacks',      CategoryName_ar = 'مأكولات مالحة ووجبات خفيفة' WHERE CategoryName = 'Tuzlular ve Atıştırmalıklar';

-- ----------------------------------------------------------------
-- 3. Ürün çevirileri
-- ----------------------------------------------------------------
-- Sıcak Kahveler
UPDATE products SET ProductName_en = 'Espresso (Single)', ProductName_ar = 'إسبريسو (مفرد)'   WHERE ProductName = 'Espresso (Single)';
UPDATE products SET ProductName_en = 'Espresso (Double)', ProductName_ar = 'إسبريسو (مزدوج)'  WHERE ProductName = 'Espresso (Double)';
UPDATE products SET ProductName_en = 'Americano',         ProductName_ar = 'أمريكانو'         WHERE ProductName = 'Americano';
UPDATE products SET ProductName_en = 'Filter Coffee',     ProductName_ar = 'قهوة مفلترة'       WHERE ProductName = 'Filtre Kahve';
UPDATE products SET ProductName_en = 'Caffe Latte',       ProductName_ar = 'كافيه لاتيه'       WHERE ProductName = 'Caffe Latte';
UPDATE products SET ProductName_en = 'Cappuccino',        ProductName_ar = 'كابتشينو'          WHERE ProductName = 'Cappuccino';
UPDATE products SET ProductName_en = 'Caffe Mocha',       ProductName_ar = 'كافيه موكا'        WHERE ProductName = 'Caffe Mocha';

-- Soğuk Kahveler
UPDATE products SET ProductName_en = 'Iced Americano',    ProductName_ar = 'أمريكانو مثلج'     WHERE ProductName = 'Iced Americano';
UPDATE products SET ProductName_en = 'Iced Latte',        ProductName_ar = 'لاتيه مثلج'        WHERE ProductName = 'Iced Latte';
UPDATE products SET ProductName_en = 'Cold Brew',         ProductName_ar = 'كولد برو'          WHERE ProductName = 'Cold Brew';
UPDATE products SET ProductName_en = 'Iced Mocha',        ProductName_ar = 'موكا مثلج'         WHERE ProductName = 'Iced Mocha';
UPDATE products SET ProductName_en = 'Caramel Frappé',    ProductName_ar = 'فرابيه بالكراميل'  WHERE ProductName = 'Karamel Frappé';

-- Çaylar ve Diğer İçecekler
UPDATE products SET ProductName_en = 'Turkish Tea',       ProductName_ar = 'شاي تركي'          WHERE ProductName = 'Türk Çayı';
UPDATE products SET ProductName_en = 'Green Tea',         ProductName_ar = 'شاي أخضر'          WHERE ProductName = 'Yeşil Çay';
UPDATE products SET ProductName_en = 'Homemade Lemonade', ProductName_ar = 'ليموناضة منزلية'   WHERE ProductName = 'Ev Yapımı Limonata';
UPDATE products SET ProductName_en = 'Hot Chocolate',     ProductName_ar = 'شوكولاتة ساخنة'    WHERE ProductName = 'Sıcak Çikolata';

-- Tatlılar
UPDATE products SET ProductName_en = 'San Sebastian Cheesecake', ProductName_ar = 'تشيز كيك سان سيباستيان' WHERE ProductName = 'San Sebastian Cheesecake';
UPDATE products SET ProductName_en = 'Lemon Cheesecake',         ProductName_ar = 'تشيز كيك بالليمون'      WHERE ProductName = 'Limonlu Cheesecake';
UPDATE products SET ProductName_en = 'Tiramisu',                 ProductName_ar = 'تيراميسو'               WHERE ProductName = 'Tiramisu';
UPDATE products SET ProductName_en = 'Brownie',                  ProductName_ar = 'براوني'                 WHERE ProductName = 'Islak Kek (Brownie)';

-- Tuzlular ve Atıştırmalıklar
UPDATE products SET ProductName_en = 'Smoked Turkey & Cheese Sandwich', ProductName_ar = 'ساندويتش ديك رومي مدخن بالجبن' WHERE ProductName = 'Hindi Füme Kaşarlı Sandviç';
UPDATE products SET ProductName_en = 'Grilled Chicken Wrap',           ProductName_ar = 'راب دجاج مشوي'                 WHERE ProductName = 'Izgara Tavuklu Wrap';
UPDATE products SET ProductName_en = 'Ezine Cheese Toastie',           ProductName_ar = 'توست بجبن إزينه'               WHERE ProductName = 'Ezine Peynirli Tost';

-- ----------------------------------------------------------------
-- 4. GetActiveMenu prosedürünü çok dilli sürümle değiştir
--    (Çeviri yoksa Türkçeye düşer — COALESCE)
-- ----------------------------------------------------------------
DROP PROCEDURE IF EXISTS GetActiveMenu;

DELIMITER //
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
DELIMITER ;

-- ----------------------------------------------------------------
-- 5. Stok tetikleyicisini çok dilli ada göre eşleştir
--    Sipariş, ürün adını TR/EN/AR herhangi birinde kaydedebilir;
--    stok yine doğru üründen düşmeli.
-- ----------------------------------------------------------------
DROP TRIGGER IF EXISTS TRG_ReduceStock;

DELIMITER //
CREATE TRIGGER TRG_ReduceStock AFTER INSERT ON OrderItems
FOR EACH ROW
BEGIN
    UPDATE products
    SET StockQuantity = GREATEST(0, StockQuantity - NEW.Quantity)
    WHERE (ProductName    = NEW.ProductName
        OR ProductName_en = NEW.ProductName
        OR ProductName_ar = NEW.ProductName)
      AND StockQuantity > 0;
END; //
DELIMITER ;
