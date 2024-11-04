import frappe
from frappe import _
from frappe.utils import nowdate, add_days

@frappe.whitelist()
def on_update_task(doc, method):
    # Check task status and perform corresponding actions
    if doc.status == "In Progress":
        # Create Purchase Order if status is "In Progress"
        purchase_order_message = create_purchase_order(doc)
        if purchase_order_message:
            frappe.msgprint(purchase_order_message)

    elif doc.status == "Completed":
        # Create Purchase Receipt if status is "Completed"
        purchase_receipt_message = create_purchase_receipt(doc)
        if purchase_receipt_message:
            frappe.msgprint(purchase_receipt_message)
            # Send email notification to the supplier
            send_email_to_supplier(doc.assigned_to, purchase_receipt_message)

@frappe.whitelist()
def create_purchase_order(task):
    # Ensure task is in 'In Progress' status
    if task.get("status") != "In Progress":
        return "Task is not in 'In Progress' status."

    # Fetch necessary fields from the task
    expertise = task.get("expertise")
    quantity = task.get("expected_time") or 1
    required_by_date = task.get("expected_end_date") or nowdate()
    supplier_email = task.get("assigned_to")

    # Get user (supplier) full name from email
    user_full_name_query = frappe.db.sql(
        "SELECT full_name FROM `tabUser` WHERE email=%s", (supplier_email,)
    )
    user_full_name = user_full_name_query[0][0] if user_full_name_query else None

    if not user_full_name:
        raise ValueError(f"No user found for the supplier email: {supplier_email}. Ensure the supplier exists in the User doctype.")

    # Get item (expertise) name
    expertise_name_query = frappe.db.sql("SELECT name FROM `tabItem` WHERE name=%s", (expertise,))
    expertise_name = expertise_name_query[0][0] if expertise_name_query else None

    if not expertise_name:
        raise ValueError(f"No item found for the expertise code: {expertise}. Ensure the expertise exists in the Item doctype.")

    # Get item price
    item_price_query = frappe.db.sql(
        "SELECT price_list_rate FROM `tabItem Price` WHERE item_code=%s AND price_list=%s",
        (expertise_name, "Standard Buying"),
        as_list=True
    )
    item_price = item_price_query[0][0] if item_price_query else None

    if not item_price:
        raise ValueError(f"No price found for the expertise: {expertise_name}. Ensure it exists in the Item Price doctype.")

    total_cost = item_price * quantity

    # Create Purchase Order
    po_data = {
        "doctype": "Purchase Order",
        "schedule_date": required_by_date,
        "supplier": user_full_name,
        "items": [{
            "item_code": expertise_name,
            "qty": quantity,
            "rate": item_price,
            "uom": "Hour",
            "required_by": required_by_date
        }]
    }

    try:
        purchase_order = frappe.get_doc(po_data)
        purchase_order.insert()
        frappe.db.commit()
        return f"Purchase Order {purchase_order.name} created successfully with a total cost of {total_cost:.2f}."
    except Exception as e:
        frappe.db.rollback()
        raise Exception(f"Failed to create Purchase Order: {str(e)}")

@frappe.whitelist()
def create_purchase_receipt(task):
    if task.get("status") != "Completed":
        return "Task is not in 'Completed' status."

    expertise = task.get("expertise")
    quantity = task.get("expected_time") or 1
    supplier_email = task.get("assigned_to")

    # Get user (supplier) full name
    user_full_name_query = frappe.db.sql(
        "SELECT full_name FROM `tabUser` WHERE email=%s", (supplier_email,)
    )
    user_full_name = user_full_name_query[0][0] if user_full_name_query else None

    if not user_full_name:
        raise ValueError(f"No user found for the supplier email: {supplier_email}. Ensure the supplier exists in the User doctype.")

    # Get expertise item name
    expertise_name_query = frappe.db.sql("SELECT name FROM `tabItem` WHERE name=%s", (expertise,))
    expertise_name = expertise_name_query[0][0] if expertise_name_query else None

    if not expertise_name:
        raise ValueError(f"No item found for the expertise code: {expertise}. Ensure the expertise exists in the Item doctype.")

    # Create Purchase Receipt
    pr_data = {
        "doctype": "Purchase Receipt",
        "supplier": user_full_name,
        "items": [{
            "item_code": expertise_name,
            "qty": quantity,
            "uom": "Hour"
        }]
    }

    try:
        purchase_receipt = frappe.get_doc(pr_data)
        purchase_receipt.insert()
        frappe.db.commit()

        # Manage Supplier Wallet
        supplier_wallet = get_or_create_supplier_wallet(user_full_name)
        amount_to_release = purchase_receipt.items[0].amount  # Assuming amount is calculated correctly

        supplier_wallet.pending_release_amount += amount_to_release
        supplier_wallet.append("transaction_history", {
            "transaction_type": "Deposit",
            "amount": amount_to_release,
            "transaction_date": nowdate(),
            "reference": purchase_receipt.name,
            "is_locked": True,
            "release_date": add_days(nowdate(), 30),  # 30-day lock period
        })
        supplier_wallet.save()
        frappe.db.commit()

        return f"Purchase Receipt {purchase_receipt.name} created successfully and {amount_to_release:.2f} added to wallet pending release."

    except Exception as e:
        frappe.db.rollback()
        raise Exception(f"Failed to create Purchase Receipt: {str(e)}")

@frappe.whitelist()
def get_or_create_supplier_wallet(supplier_name):
    wallet = frappe.db.get_value("Supplier Wallet", {"supplier": supplier_name})
    if wallet:
        return frappe.get_doc("Supplier Wallet", wallet)
    else:
        new_wallet = frappe.get_doc({
            "doctype": "Supplier Wallet",
            "supplier": supplier_name,
            "balance": 0,
            "pending_release_amount": 0,
            "transaction_history": []
        })
        new_wallet.insert()
        frappe.db.commit()
        return new_wallet

@frappe.whitelist()
def send_email_to_supplier(supplier_email, purchase_receipt_message):
    subject = "Purchase Receipt Created"
    message = f"A Purchase Receipt has been created:\n\n{purchase_receipt_message}"

    try:
        frappe.sendmail(
            recipients=[supplier_email],
            subject=subject,
            message=message
        )
        frappe.msgprint(f"Email sent successfully to {supplier_email}.")
    except Exception as e:
        frappe.msgprint(f"Failed to send email: {str(e)}")

@frappe.whitelist()
def calculate_task_cost_based_on_expertise(doc, method):
    if doc.expected_time and doc.expertise:
        expertise_item = frappe.get_doc("Item", doc.expertise)
        
        if expertise_item:
            item_price = frappe.get_all(
                "Item Price",
                filters={"item_code": expertise_item.item_code},
                fields=["price_list_rate"],
                limit=1
            )
            if item_price:
                expertise_item_price = item_price[0].price_list_rate
                total_costing_amount = doc.expected_time * expertise_item_price
                
                frappe.db.set_value('Task', doc.name, 'total_costing_amount', total_costing_amount)
