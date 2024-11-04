import frappe
from frappe import _

@frappe.whitelist()
def enable_user_on_approval(doc, method):
    # Check if the supplier status is "Approved"
    if doc.status == 'Approved':  
        # Search for an existing user based on the supplier's email
        user = frappe.get_all('User', filters={'email': doc.email_id}, fields=['name', 'enabled'])
        
        if user:  # If the user exists
            user_name = user[0]['name']
            if not user[0]['enabled']:  # Only enable if currently disabled
                frappe.db.set_value('User', user_name, 'enabled', 1)  # Enable the user
                frappe.db.commit()
                frappe.msgprint(_("Existing user enabled for {0}".format(doc.email_id)), alert=True)
            else:
                frappe.msgprint(_("User {0} is already enabled.".format(doc.email_id)), alert=True)
            
            # Send a notification email to the supplier
            send_email_notification(doc.email_id, doc.supplier_name)
        
        else:  # If no user exists, create a new user
            try:
                new_user = frappe.get_doc({
                    'doctype': 'User',
                    'email': doc.email_id,
                    'first_name': doc.supplier_name,
                    'enabled': 1,  # Enable the new user
                    'send_welcome_email': 1,  # Optionally send a welcome email
                    'user_type': 'Website User',  # Create as a portal user
                    'role_profile_name': 'Supplier'  # Assign "Supplier" role profile
                })
                new_user.insert()
                frappe.db.commit()

                frappe.msgprint(_("New user created and enabled for {0}".format(doc.email_id)), alert=True)
                
                # Send an approval email notification
                send_email_notification(doc.email_id, doc.supplier_name)

            except frappe.DuplicateEntryError:
                frappe.log_error(f"User with email {doc.email_id} already exists but was not found in initial check.")
                frappe.throw(_("An error occurred while creating the user. Please check for duplicates."))

# Helper function to send email notifications
def send_email_notification(email, supplier_name):
    message = f"""
        Dear {supplier_name},

        Congratulations! Your supplier registration has been approved. 
        You can now log in to the supplier portal using your email.

        Regards,
        The Team
    """
    try:
        frappe.sendmail(
            recipients=[email],
            subject="Supplier Registration Approved",
            message=message
        )
        frappe.msgprint(_("Notification email sent to {0}".format(email)), alert=True)
    except frappe.OutgoingEmailError:
        frappe.log_error(f"Failed to send approval email to {email}")
        frappe.msgprint(_("Could not send email notification. Please check email settings."), alert=True)
