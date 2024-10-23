// Copyright (c) 2024, Mwanika Hudson and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier Wallet', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Withdraw'), function() {
                frappe.prompt([
                    {
                        fieldname: 'withdrawal_amount',
                        label: 'Withdrawal Amount',
                        fieldtype: 'Currency',
                        reqd: 0,
                        description: 'Enter the amount you want to withdraw'
                    }
                ], function(values) {
                    frappe.call({
                        method: 'partners_portal.partners_portal.doctype.supplier_wallet.supplier_wallet.create_withdrawal_request',
                        args: {
                            wallet_name: frm.doc.name,
                            amount: values.withdrawal_amount
                        },
                        callback: function(response) {
                            if (response.message) {
                                frappe.msgprint(__('Withdrawal Request created successfully.'));
                            }
                        }
                    });
                }, __('Enter Withdrawal Amount'), __('Request Withdrawal'));
            }, __('Actions'));
        }
    }
});
