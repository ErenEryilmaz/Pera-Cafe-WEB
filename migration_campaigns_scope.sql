-- ================================================================
-- Pera Kafe — Kampanya Kapsamı (Scope) sütunları
-- Kampanyanın HANGİ ürünlere uygulanacağını belirler:
--   scope_type = 'all'      -> tüm ürünler (varsayılan, eski davranış)
--   scope_type = 'category' -> scope_ids içindeki kategori ID'leri
--   scope_type = 'product'  -> scope_ids içindeki ürün ID'leri
-- MySQL istemcisinde çalıştırın (DigitalOcean üzerindeki MySQL sunucunuza).
--
-- NOT: Sunucu ANSI_QUOTES modunda olduğu için çift tırnaklı dinamik SQL
-- (PREPARE/EXECUTE) kullanılmadı; düz ALTER + tek tırnak her modda çalışır.
-- Bu komut bir kez çalıştırılır. Tekrar çalıştırırsanız "Duplicate column"
-- hatası alırsınız; bu, sütunların zaten eklendiği anlamına gelir (zararsız).
-- ================================================================

USE peracafe;

ALTER TABLE campaigns
  ADD COLUMN scope_type ENUM('all','category','product') NOT NULL DEFAULT 'all' AFTER config,
  ADD COLUMN scope_ids  JSON NULL AFTER scope_type;
