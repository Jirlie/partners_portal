# Copyright (c) 2024, Mwanika Hudson and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TransactionHistory(Document):
    pass

class WalletManager:
    def __init__(self, wallet_name):
        self.wallet = frappe.get_doc('Supplier Wallet', wallet_name)

    def unlock_earnings(self):
        """Unlock the earnings for the wallet if the lock period has passed."""
        transactions = self.wallet.transaction_history
        
        for transaction in transactions:
            if transaction.is_locked and frappe.utils.nowdate() >= transaction.release_date:
                # Unlock the earnings
                self.wallet.available_balance += transaction.amount
                self.wallet.pending_release_amount -= transaction.amount
                transaction.is_locked = False  # Mark as unlocked

        self.save_wallet()

    def save_wallet(self):
        """Save wallet changes and handle potential errors."""
        try:
            self.wallet.save()
            frappe.db.commit()
            frappe.logger().info(f"Successfully unlocked earnings for wallet {self.wallet.name}")
        except Exception as e:
            frappe.db.rollback()
            frappe.log_error(f"Failed to unlock earnings for wallet {self.wallet.name}: {str(e)}", "Unlock Wallet Earnings Error")


@frappe.whitelist()
def unlock_wallet_earnings():
    """Fetch all wallets with locked transactions and unlock them if the lock period has passed."""
    wallets = frappe.get_all('Supplier Wallet', filters=[["transaction_history", "is_locked", "=", 1]])
    
    for wallet in wallets:
        try:
            wallet_manager = WalletManager(wallet.name)
            wallet_manager.unlock_earnings()
        except Exception as e:
            frappe.log_error(f"Error processing wallet {wallet.name}: {str(e)}", "Unlock Wallet Earnings Error")
