-- ================================================================
-- Pera Kafe — Kampanyalar (Campaigns) Tablosu
-- MySQL istemcisinde çalıştırın (DigitalOcean üzerindeki MySQL sunucunuza).
-- ================================================================

USE peracafe;

CREATE TABLE IF NOT EXISTS campaigns (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(150) CHARACTER SET utf8mb4 NOT NULL,
  description TEXT CHARACTER SET utf8mb4 NULL,
  -- Kampanya tipi: X alana Y bedava / yüzde indirim / sabit tutar indirim
  type        ENUM('buy_x_get_y','percentage','fixed') NOT NULL,
  -- Tipe göre değişen ayarlar:
  --   buy_x_get_y -> {"buy":2,"get":1}
  --   percentage  -> {"percent":10}
  --   fixed       -> {"amount":20}
  config      JSON NOT NULL,
  -- Kapsam: kampanya hangi ürünlere uygulanacak
  --   scope_type='all'      -> tüm ürünler
  --   scope_type='category' -> scope_ids içindeki kategori ID'leri
  --   scope_type='product'  -> scope_ids içindeki ürün ID'leri
  scope_type  ENUM('all','category','product') NOT NULL DEFAULT 'all',
  scope_ids   JSON NULL,
  badge_color VARCHAR(20) DEFAULT '#E67E22',
  is_active   BOOLEAN DEFAULT TRUE,
  start_date  DATE NULL,
  end_date    DATE NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
