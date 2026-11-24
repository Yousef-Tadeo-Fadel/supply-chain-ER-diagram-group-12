"""The ten Chapter 5 relations. Column order also determines the form layout."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Relation:
    title: str
    keys: tuple
    fields: tuple

    @property
    def columns(self):
        return tuple(dict.fromkeys(self.keys + self.fields))


TABLES = {
    "supplier": Relation("Suppliers", ("supplier_id",),
                         ("name", "country", "phone", "email", "lead_time_days")),
    "warehouse": Relation("Warehouses", ("warehouse_id",), ("name", "city", "capacity")),
    "customer": Relation("Customers", ("customer_id",), ("name", "address", "phone", "email")),
    "product": Relation("Products", ("product_id",),
                        ("name", "category", "unit_price", "reorder_level", "supplier_id")),
    "employee": Relation("Employees", ("employee_id",), ("name", "role", "phone", "warehouse_id")),
    "inventory": Relation("Inventory", ("warehouse_id", "product_id"),
                          ("warehouse_id", "product_id", "quantity")),
    "purchase_order": Relation("Purchase orders", ("po_id",),
                               ("product_id", "warehouse_id", "employee_id", "quantity",
                                "order_date", "expected_date", "status")),
    "sales_order": Relation("Sales orders", ("order_id",), ("customer_id", "order_date", "status")),
    "order_item": Relation("Order items", ("order_id", "product_id"),
                           ("order_id", "product_id", "quantity")),
    "shipment": Relation("Shipments", ("shipment_id",),
                         ("order_id", "warehouse_id", "employee_id", "carrier_name",
                          "tracking_number", "ship_date", "delivery_date", "status")),
}

OPTIONS = {
    ("employee", "role"): ("Purchasing Officer", "Warehouse Supervisor", "Sales Representative",
                           "Logistics Coordinator", "Operations Manager"),
    ("purchase_order", "status"): ("Ordered", "In Transit", "Partially Received", "Received"),
    ("sales_order", "status"): ("Pending", "Confirmed", "Shipped", "Delivered"),
    ("shipment", "status"): ("Preparing", "Shipped", "In Transit", "Delivered"),
}

REFERENCES = {
    "warehouse_id": ("warehouse", "name"),
    "product_id": ("product", "name"),
    "supplier_id": ("supplier", "name"),
    "employee_id": ("employee", "name"),
    "customer_id": ("customer", "name"),
    "order_id": ("sales_order", "order_date"),
}

OPTIONAL = {"phone", "address", "expected_date", "tracking_number", "ship_date", "delivery_date"}
LIMITS = {"name": 100, "country": 50, "city": 50, "category": 50, "phone": 20, "email": 100,
          "address": 200, "carrier_name": 100, "tracking_number": 50}
NUMBERS = {"quantity", "capacity", "lead_time_days", "reorder_level", *REFERENCES}


def required(table, field):
    return field not in OPTIONAL and (table, field) != ("customer", "email")


def field_type(field):
    if field in NUMBERS or field == "unit_price":
        return "number"
    if field.endswith("_date"):
        return "date"
    return {"email": "email", "phone": "tel"}.get(field, "text")

