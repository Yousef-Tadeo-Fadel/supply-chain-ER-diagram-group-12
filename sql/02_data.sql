
-- CMPE341 Supply Chain Database
-- Sample Data for PostgreSQL
-- Designed for a NEW, EMPTY database.
-- Primary keys are generated automatically using SERIAL.

BEGIN;

-- 1. Suppliers
INSERT INTO supplier
(name, country, phone, email, lead_time_days)
VALUES
('Ankara Packaging Co.', 'Turkey',
 '+90 312 555 0101', 'sales@ankarapackaging.example', 7),
('Marmara Industrial Parts', 'Turkey',
 '+90 212 555 0102', 'info@marmaraparts.example', 10),
('European Safety Supplies', 'Germany',
 '+49 30 555 0103', 'orders@europeansafety.example', 14);


-- 2. Warehouses
INSERT INTO warehouse
(name, city, capacity)
VALUES
('Ankara Central Warehouse', 'Ankara', 5000),
('Istanbul Distribution Center', 'Istanbul', 8000),
('Istanbul Anatolian Warehouse', 'Istanbul', 4000);


-- 3. Customers
INSERT INTO customer
(name, address, phone, email)
VALUES
('Anadolu Manufacturing Ltd.',
 'Cankaya, Ankara', '+90 312 555 0201',
 'contact@anadolumfg.example'),
('Bosphorus Retail Ltd.',
 'Kadikoy, Istanbul', '+90 216 555 0202',
 'orders@bosphorusretail.example'),
('Marmara Logistics Ltd.',
 'Kartal, Istanbul', '+90 216 555 0203',
 'info@marmaralogistics.example'),
('Capital Industrial Trading',
 'Sincan, Ankara', '+90 312 555 0204',
 'sales@capitalindustrial.example');


-- 4. Products
-- Supplier IDs are generated as 1, 2, 3.
INSERT INTO product
(name, category, unit_price, reorder_level, supplier_id)
VALUES
('Corrugated Carton Boxes', 'Packaging',
 12.50, 100, 1),
('Stretch Wrap Rolls', 'Packaging',
 95.00, 50, 1),
('Industrial Safety Gloves', 'Safety Equipment',
 38.00, 60, 3),
('Steel Fasteners Pack', 'Industrial Supplies',
 160.00, 35, 2),
('Packing Tape Rolls', 'Packaging',
 22.00, 80, 1),
('Pallet Corner Protectors', 'Packaging',
 18.00, 40, 2);


-- 5. Employees
-- Warehouse IDs are generated as 1, 2, 3.
INSERT INTO employee
(name, role, phone, warehouse_id)
VALUES
('Ahmet Yilmaz', 'Purchasing Officer',
 '+90 532 555 0301', 1),
('Ayse Demir', 'Warehouse Supervisor',
 '+90 532 555 0302', 1),
('Mehmet Kaya', 'Logistics Coordinator',
 '+90 532 555 0303', 2),
('Elif Arslan', 'Sales Representative',
 '+90 532 555 0304', 3),
('Zeynep Celik', 'Operations Manager',
 '+90 532 555 0305', 3);


-- 6. Inventory
-- Composite primary key: warehouse_id + product_id.
-- Products 2 and 5 have low total inventory.
INSERT INTO inventory
(warehouse_id, product_id, quantity)
VALUES
(1, 1, 120),
(2, 1, 80),
(3, 1, 30),
(1, 2, 25),
(2, 2, 15),
(1, 3, 100),
(3, 3, 25),
(2, 4, 50),
(3, 4, 20),
(1, 5, 50),
(2, 5, 10),
(2, 6, 40),
(3, 6, 30);


-- 7. Purchase Orders
-- Includes Received, Partially Received,
-- In Transit and Ordered statuses.
INSERT INTO purchase_order
(product_id, warehouse_id, employee_id,
 quantity, order_date, expected_date, status)
VALUES
(1, 1, 1, 100,
 '2026-11-01', '2026-11-12', 'Received'),
(2, 2, 1, 70,
 '2026-11-07', '2026-11-27', 'Partially Received'),
(5, 1, 1, 120,
 '2026-11-10', '2026-12-02', 'In Transit'),
(6, 3, 1, 60,
 '2026-11-17', '2026-12-06', 'Ordered');


-- 8. Sales Orders
-- Customer 1 places two separate orders.
INSERT INTO sales_order
(customer_id, order_date, status)
VALUES
(1, '2026-11-06', 'Delivered'),
(2, '2026-11-11', 'Shipped'),
(3, '2026-11-16', 'Confirmed'),
(4, '2026-11-18', 'Pending'),
(1, '2026-11-20', 'Confirmed');


-- 9. Order Items
-- Every sales order has two products.
INSERT INTO order_item
(order_id, product_id, quantity)
VALUES
(1, 1, 10),
(1, 3, 5),
(2, 4, 3),
(2, 2, 4),
(3, 1, 15),
(3, 6, 10),
(4, 5, 8),
(4, 3, 4),
(5, 1, 5),
(5, 2, 3);


-- 10. Shipments
-- Demonstrates Delivered, In Transit and Preparing.
INSERT INTO shipment
(order_id, warehouse_id, employee_id,
 carrier_name, tracking_number,
 ship_date, delivery_date, status)
VALUES
(1, 1, 2,
 'Aras Kargo', 'TRK100001',
 '2026-11-07', '2026-11-09', 'Delivered'),
(2, 2, 3,
 'Yurtici Kargo', 'TRK100002',
 '2026-11-12', NULL, 'In Transit'),
(3, 2, 3,
 'MNG Kargo', 'TRK100003',
 NULL, NULL, 'Preparing');

COMMIT;
