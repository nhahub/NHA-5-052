-- Run after executing oltp.sql.
USE ecommerce_oltp;

-- 1. Confirm the eight expected tables exist.
SHOW TABLES;

-- 2. Confirm table row counts. Before data import, these should be zero.
SELECT 'category_translation' AS table_name, COUNT(*) AS row_count FROM category_translation
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'sellers', COUNT(*) FROM sellers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'order_payments', COUNT(*) FROM order_payments
UNION ALL SELECT 'order_reviews', COUNT(*) FROM order_reviews;

-- 3. Confirm the purchase-timestamp index exists.
SHOW INDEX FROM orders WHERE Key_name = 'idx_orders_purchase_timestamp';

-- 4. Inspect foreign-key relationships defined in this database.
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'ecommerce_oltp'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, COLUMN_NAME;

-- 5. Check for orders that have no order items after loading.
-- Run after imports; the result should be recorded for reconciliation.
SELECT COUNT(*) AS orders_without_items
FROM orders AS o
LEFT JOIN order_items AS i ON i.order_id = o.order_id
WHERE i.order_id IS NULL;
