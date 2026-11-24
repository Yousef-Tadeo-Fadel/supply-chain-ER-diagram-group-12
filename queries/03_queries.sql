
-- CMPE341 Supply Chain Database
-- Chapter 5: SQL Queries

-- QUERY 1: JOIN
-- Display customer orders and purchased products,
-- including quantities, prices and line totals.

SELECT
    so.order_id,
    c.name AS customer_name,
    p.name AS product_name,
    oi.quantity,
    p.unit_price,
    oi.quantity * p.unit_price AS total_price
FROM sales_order so
JOIN customer c
    ON so.customer_id = c.customer_id
JOIN order_item oi
    ON so.order_id = oi.order_id
JOIN product p
    ON oi.product_id = p.product_id
ORDER BY so.order_id, p.name;


-- QUERY 2: GROUP BY + ORDER BY
-- Calculate total sales value for each customer,
-- ordered from highest to lowest.

SELECT
    c.customer_id,
    c.name AS customer_name,
    SUM(oi.quantity * p.unit_price) AS total_sales_value
FROM customer c
JOIN sales_order so
    ON c.customer_id = so.customer_id
JOIN order_item oi
    ON so.order_id = oi.order_id
JOIN product p
    ON oi.product_id = p.product_id
GROUP BY c.customer_id, c.name
ORDER BY total_sales_value DESC, c.customer_id;


-- QUERY 3: SUBQUERY
-- Find products whose total inventory across all
-- warehouses is below their reorder level.

SELECT
    p.product_id,
    p.name AS product_name,
    p.reorder_level,
    COALESCE((
        SELECT SUM(i.quantity)
        FROM inventory i
        WHERE i.product_id = p.product_id
    ), 0) AS total_inventory
FROM product p
WHERE COALESCE((
    SELECT SUM(i.quantity)
    FROM inventory i
    WHERE i.product_id = p.product_id
), 0) < p.reorder_level
ORDER BY p.product_id;
