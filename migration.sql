-- ================================================================
-- Pera Kafe — Admin Panel için DB Migrasyonu
-- Aiven MySQL konsolunda veya herhangi bir MySQL istemcisinde çalıştırın
-- ================================================================

USE peracafe;

-- 1. Products tablosuna stok sütunu ekle
ALTER TABLE products
  ADD COLUMN IF NOT EXISTS StockQuantity INT DEFAULT 50,
  ADD COLUMN IF NOT EXISTS IsActive      BOOLEAN DEFAULT TRUE;

-- 2. Siparişler tablosu
CREATE TABLE IF NOT EXISTS Orders (
  OrderID      INT PRIMARY KEY AUTO_INCREMENT,
  TableNo      VARCHAR(20)  DEFAULT 'Kiosk',
  MemberPhone  VARCHAR(15)  DEFAULT NULL,
  Status       ENUM('pending','preparing','ready','completed','cancelled') DEFAULT 'pending',
  TotalAmount  DECIMAL(10,2) DEFAULT 0,
  CreatedAt    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UpdatedAt    TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  Notes        TEXT DEFAULT NULL
);

-- 3. Sipariş kalemleri
CREATE TABLE IF NOT EXISTS OrderItems (
  ItemID      INT PRIMARY KEY AUTO_INCREMENT,
  OrderID     INT NOT NULL,
  ProductName VARCHAR(150) NOT NULL,
  Quantity    INT DEFAULT 1,
  UnitPrice   DECIMAL(8,2) NOT NULL,
  FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
);

-- 4. Stok başlangıç değeri
UPDATE Products SET StockQuantity = 50 WHERE StockQuantity IS NULL;
