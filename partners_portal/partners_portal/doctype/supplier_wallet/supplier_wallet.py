# Copyright (c) 2024, Mwanika Hudson and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from datetime import datetime
from frappe import _, throw
from frappe.utils import getdate, nowdate
from datetime import datetime
from frappe.desk.form.assign_to import clear, close_all_assignments
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, cstr, date_diff, flt, get_link_to_form, getdate, today
from frappe.utils.nestedset import NestedSet

# import frappe
from frappe.model.document import Document

class SupplierWallet(Document):
	pass


@frappe.whitelist()
def approve_withdrawal_request(request_id):
    """
    Approve the withdrawal request and add the amount to the supplier's wallet balance.
    """
    # Fetch the withdrawal request document
    withdrawal_request = frappe.get_doc('Withdrawal Request', request_id)

    # Ensure the withdrawal request is still in a pending state
    if withdrawal_request.status != "Pending":
        frappe.throw(_("Withdrawal Request is not in a pending state."))

    # Fetch the associated Supplier Wallet
    wallet = frappe.get_doc('Supplier Wallet', {'supplier': withdrawal_request.supplier})

    # Check if sufficient balance is available in pending withdrawals
    if wallet.pending_withdrawal < withdrawal_request.withdrawal_amount:
        frappe.throw(_("Insufficient funds in pending withdrawals for this withdrawal."))

    # Add the withdrawal amount to the wallet's available balance
    wallet.balance += withdrawal_request.withdrawal_amount

    # Deduct the amount from the pending withdrawal amount
    wallet.pending_withdrawal -= withdrawal_request.withdrawal_amount

    # Log the transaction in the wallet's transaction history
    wallet.append("transaction_history", {
        "transaction_type": "Withdrawal Approval",
        "amount": withdrawal_request.withdrawal_amount,
        "transaction_date": frappe.utils.nowdate(),
        "reference": withdrawal_request.name
    })

    # Save the updated wallet with the new balance and transaction history
    wallet.save()

    # Commit the changes to the database
    frappe.db.commit()

    # Update the withdrawal request status to "Approved"
    withdrawal_request.status = "Approved"
    withdrawal_request.save()

    # Notify the user of the successful approval
    frappe.msgprint(_("Withdrawal Request {0} has been approved and the amount has been added to the wallet balance.").format(request_id))

@frappe.whitelist()
def create_withdrawal_request(wallet_name, amount):
    # Fetch the Supplier Wallet document
    try:
        wallet = frappe.get_doc('Supplier Wallet', wallet_name)
    except Exception as e:
        frappe.throw(_("Could not find Supplier Wallet with name: {0}. Error: {1}").format(wallet_name, str(e)))

    # Ensure that amount is provided, but allow zero or null values
    if amount is None or amount == "":
        return _("No withdrawal amount provided. Withdrawal request not created.")

    # Convert amount and wallet balance to float to ensure proper comparison
    try:
        amount = float(amount)
        wallet_balance = float(wallet.balance)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid withdrawal amount or wallet balance. Please enter valid numbers."))

    # Prevent negative withdrawal amounts, but allow zero amounts
    if amount < 0:
        frappe.throw(_("Withdrawal amount cannot be negative."))

    # Check for transactions without a release date
    for transaction in wallet.transaction_history:
        if not transaction.release_date:
            frappe.throw(_("Cannot proceed with withdrawal: There are transactions pending release."))

    # Validate that the most recent transaction is at least 30 days old
    if wallet.transaction_history:
        try:
            latest_transaction = max(wallet.transaction_history, key=lambda t: getdate(t.transaction_date))
            latest_transaction_date = getdate(latest_transaction.transaction_date)
            current_date = getdate(frappe.utils.nowdate())

            # Check if the latest transaction is less than 30 days old
            if (current_date - latest_transaction_date).days < 30:
                frappe.throw(_("Withdrawal can only be created if the last transaction is more than 30 days old."))
        except (TypeError, ValueError) as e:
            frappe.throw(_("Error processing transaction history. Please ensure all transactions have valid dates."))

    # Validate the requested withdrawal amount
    if amount > wallet_balance:
        frappe.throw(_("Withdrawal amount cannot exceed the available balance of the supplier wallet."))

    # Proceed with creating a Withdrawal Request only if amount is greater than zero
    if amount > 0:
        try:
            withdrawal_request = frappe.new_doc('Withdrawal Request')
            withdrawal_request.supplier_wallet = wallet.name
            withdrawal_request.supplier = wallet.supplier
            withdrawal_request.withdrawal_amount = amount
            withdrawal_request.transaction_date = frappe.utils.now()  # Use Frappe's `now` method

            # Insert the document into the database
            withdrawal_request.insert()
            frappe.db.commit()

            return _("Withdrawal Request created successfully.")
        except Exception as e:
            frappe.db.rollback()
            frappe.throw(_("Failed to create withdrawal request: {0}").format(str(e)))
    
    return _("No withdrawal request created because the amount is zero.")
