"""Stock effects run in the same PostgreSQL transaction as their parent edit."""
from decimal import Decimal, InvalidOperation


class InvalidWorkflow(ValueError):
    pass


def validate_price(values):
    if "unit_price" in values:
        try:
            price = Decimal(values["unit_price"])
            if not price.is_finite() or price <= 0 or price != price.quantize(Decimal("0.01")):
                raise InvalidWorkflow("Enter a positive price with at most two decimal places.")
        except (TypeError, InvalidOperation):
            raise InvalidWorkflow("Enter a valid unit price.") from None


def receive(db, old, values, form):
    previous = old.get("status")
    status = values["status"]
    if previous in ("Partially Received", "Received"):
        for field in ("product_id", "warehouse_id", "quantity"):
            if str(old[field]) != str(values[field]):
                raise InvalidWorkflow("Product, warehouse and order quantity are fixed after a receipt.")
        if status not in (("Received",) if previous == "Received" else ("Partially Received", "Received")):
            raise InvalidWorkflow("A received order cannot return to an earlier status.")
    if status not in ("Partially Received", "Received") or previous == "Received":
        return
    new_delivery = (form.get("delivery_units") or "").strip()
    earlier = (form.get("earlier_units") or "").strip()
    if previous == status and not new_delivery and not earlier:
        return  # An ordinary edit to an already partial order.
    try:
        total = int(values["quantity"])
        already = int(earlier) if previous == "Partially Received" else 0
        units = int(new_delivery) if new_delivery else total - already
    except (ValueError, TypeError):
        raise InvalidWorkflow("Enter whole delivery units and the verified earlier total for a partial order.") from None
    if already < 0 or (previous == "Partially Received" and already == 0) or units <= 0 or already + units > total:
        raise InvalidWorkflow("Check received units against the order quantity.")
    if (already + units == total) != (status == "Received"):
        raise InvalidWorkflow("Use Received when the cumulative delivery equals the order quantity.")
    if previous != "Partially Received" and earlier and earlier != "0":
        raise InvalidWorkflow("An initial receipt must start at zero earlier units.")
    db.execute("""
        INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES (%s, %s, %s)
        ON CONFLICT (warehouse_id, product_id)
        DO UPDATE SET quantity = inventory.quantity + excluded.quantity
    """, (values["warehouse_id"], values["product_id"], units))


def confirm(db, order_id):
    # Lock the parent before reading lines. Every app line mutation takes the same parent lock.
    items = db.execute("SELECT product_id, quantity FROM order_item WHERE order_id=%s ORDER BY product_id",
                       (order_id,)).fetchall()
    if not items:
        raise InvalidWorkflow("Add at least one order item before confirming this order.")
    for item in items:
        stock = db.execute("SELECT quantity FROM inventory WHERE product_id=%s ORDER BY warehouse_id FOR SHARE",
                           (item["product_id"],)).fetchall()
        available = sum(row["quantity"] for row in stock)
        if item["quantity"] > available:
            raise InvalidWorkflow(f"Product {item['product_id']} has {available} units available "
                                  f"for the {item['quantity']} requested.")


def lock_order(db, order_id):
    return db.execute("SELECT status FROM sales_order WHERE order_id=%s FOR UPDATE",
                      (order_id,)).fetchone()


def prepare(db, table, old, values, form):
    validate_price(values)
    if table == "purchase_order":
        receive(db, old, values, form)
    if table == "sales_order" and values["status"] != old.get("status"):
        if values["status"] != "Pending" and (not old or old["status"] == "Pending"):
            if not old or values["status"] != "Confirmed":
                raise InvalidWorkflow("Create a pending order, add its items, then confirm the order.")
        if values["status"] == "Confirmed":
            confirm(db, old["order_id"])

