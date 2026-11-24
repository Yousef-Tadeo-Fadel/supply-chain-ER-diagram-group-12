
-- CMPE341 Supply Chain Database
-- Physical Design: PostgreSQL Schema
-- Aligned with the approved logical design

-- 1. Supplier
CREATE TABLE supplier (
    supplier_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100) NOT NULL UNIQUE,
    lead_time_days INTEGER NOT NULL
        CHECK (lead_time_days >= 0)
);

-- 2. Warehouse
CREATE TABLE warehouse (
    warehouse_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    capacity INTEGER NOT NULL
        CHECK (capacity > 0)
);

-- 3. Customer
CREATE TABLE customer (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(200),
    phone VARCHAR(20),
    email VARCHAR(100) UNIQUE
);

-- 4. Product
CREATE TABLE product (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL
        CHECK (unit_price > 0),
    reorder_level INTEGER NOT NULL
        CHECK (reorder_level >= 0),
    supplier_id INTEGER NOT NULL,
    FOREIGN KEY (supplier_id)
        REFERENCES supplier(supplier_id)
);

-- 5. Employee
CREATE TABLE employee (
    employee_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(30) NOT NULL
        CHECK (role IN (
            'Purchasing Officer',
            'Warehouse Supervisor',
            'Sales Representative',
            'Logistics Coordinator',
            'Operations Manager'
        )),
    phone VARCHAR(20),
    warehouse_id INTEGER NOT NULL,
    FOREIGN KEY (warehouse_id)
        REFERENCES warehouse(warehouse_id)
);

-- 6. Inventory
CREATE TABLE inventory (
    warehouse_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL
        CHECK (quantity >= 0),
    PRIMARY KEY (warehouse_id, product_id),
    FOREIGN KEY (warehouse_id)
        REFERENCES warehouse(warehouse_id),
    FOREIGN KEY (product_id)
        REFERENCES product(product_id)
);

-- 7. Purchase Order
CREATE TABLE purchase_order (
    po_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL
        CHECK (quantity > 0),
    order_date DATE NOT NULL,
    expected_date DATE,
    status VARCHAR(20) NOT NULL
        CHECK (status IN (
            'Ordered',
            'In Transit',
            'Partially Received',
            'Received'
        )),
    FOREIGN KEY (product_id)
        REFERENCES product(product_id),
    FOREIGN KEY (warehouse_id)
        REFERENCES warehouse(warehouse_id),
    FOREIGN KEY (employee_id)
        REFERENCES employee(employee_id),
    CHECK (expected_date >= order_date)
);

-- 8. Sales Order
CREATE TABLE sales_order (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL
        CHECK (status IN (
            'Pending',
            'Confirmed',
            'Shipped',
            'Delivered'
        )),
    FOREIGN KEY (customer_id)
        REFERENCES customer(customer_id)
);

-- 9. Order Item
CREATE TABLE order_item (
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL
        CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id)
        REFERENCES sales_order(order_id),
    FOREIGN KEY (product_id)
        REFERENCES product(product_id)
);

-- 10. Shipment
CREATE TABLE shipment (
    shipment_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    carrier_name VARCHAR(100) NOT NULL,
    tracking_number VARCHAR(50) UNIQUE,
    ship_date DATE,
    delivery_date DATE,
    status VARCHAR(20) NOT NULL
        CHECK (status IN (
            'Preparing',
            'Shipped',
            'In Transit',
            'Delivered'
        )),
    FOREIGN KEY (order_id)
        REFERENCES sales_order(order_id),
    FOREIGN KEY (warehouse_id)
        REFERENCES warehouse(warehouse_id),
    FOREIGN KEY (employee_id)
        REFERENCES employee(employee_id),
    CHECK (delivery_date >= ship_date)
);
