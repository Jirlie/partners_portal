# Copyright (c) 2024, Mwanika Hudson and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class WithdrawalRequest(Document):
    pass

@frappe.whitelist()
def approve_withdrawal_request(request_id):
    # Fetch the withdrawal request document
    withdrawal_request = frappe.get_doc('Withdrawal Request', request_id)
    
    # Check if the request is in Pending Approval state
    if withdrawal_request.status != "Pending Approval":
        frappe.throw("Withdrawal Request is not in a pending state.")
    
    # Get the associated Supplier Wallet
    wallet = frappe.get_doc('Supplier Wallet', {'supplier': withdrawal_request.supplier})
    
    # Check if there are sufficient funds in the wallet
    if wallet.available_balance < withdrawal_request.withdrawal_amount:
        frappe.throw("Insufficient available balance for this withdrawal.")
    
    # Deduct the withdrawal amount from the wallet balance
    wallet.available_balance -= withdrawal_request.withdrawal_amount
    wallet.append("transaction_history", {
        "transaction_type": "Withdrawal",
        "amount": withdrawal_request.withdrawal_amount,
        "transaction_date": frappe.utils.nowdate(),
        "reference": withdrawal_request.name
    })

    # Save the updated wallet
    wallet.save()
    frappe.db.commit()  # Commit the changes to the database
    
    # Update withdrawal request status to Approved
    withdrawal_request.status = "Approved"
    withdrawal_request.save()
    frappe.msgprint(f"Withdrawal Request {request_id} has been approved successfully.")
