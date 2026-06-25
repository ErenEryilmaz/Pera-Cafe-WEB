-- ================================================================
-- Pera Kafe — Menü filtresini IsActive'e hizala
-- ----------------------------------------------------------------
-- SORUN: GetActiveMenu prosedürü ürünleri `IsAvailable` sütununa
-- göre filtreliyordu. Ancak admin panelindeki "Pasife Al" düğmesi
-- `IsActive` sütununu değiştiriyor. İki ayrı sütun olduğu için bir
-- ürünü pasife aldığında menüden (ve AI'nın gördüğü listeden)
-- düşmüyordu — müşteri yine sipariş edebiliyordu.
--
-- ÇÖZÜM: Prosedürü admin panelinin kontrol ettiği IsActive sütununa
-- göre filtrele. COALESCE(IsActive,1): durumu NULL olan eski kayıtlar
-- aktif sayılır (admin paneliyle aynı mantık), böylece kaybolmazlar.
--
-- DigitalOcean MySQL konsolunda (doğru veritabanına bağlıyken) BİR KEZ
-- çalıştırın. Tekrar çalıştırmak güvenlidir (DROP ... IF EXISTS).
-- ================================================================

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

-- ================================================================
-- 2. Artık ölü olan IsAvailable sütununu sil.
-- ----------------------------------------------------------------
-- DİKKAT: Bu blok, YUKARIDAKİ prosedür yeniden tanımlandıktan SONRA
-- gelir. Dosyayı baştan sona çalıştırdığında GetActiveMenu artık
-- IsAvailable'a bakmıyor olur, dolayısıyla sütunu silmek güvenlidir.
-- (Sildiğimiz IsAvailable; IsActive kalıyor — admin panelinin kullandığı sütun.)
--
-- MySQL'de "DROP COLUMN IF EXISTS" yok; tekrar çalıştırılınca hata
-- vermesin diye information_schema ile kontrol edip öyle siliyoruz.
-- ================================================================
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'products'
      AND COLUMN_NAME  = 'IsAvailable'
);
SET @ddl := IF(@col_exists > 0,
               'ALTER TABLE products DROP COLUMN IsAvailable',
               'DO 0');  -- DO 0: kolon yoksa hiçbir şey yapma
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
