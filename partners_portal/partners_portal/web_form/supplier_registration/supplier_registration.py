import frappe
from frappe import _

def get_context(context):
    # Add logic for the page's context if needed
    context.custom_message = "Welcome to the Supplier Registration Form"
    return context


@frappe.whitelist()
def after_insert_supplier(doc, method):
    try:
        # Log the incoming document for debugging
        frappe.logger().info(f"Processing new supplier: {doc.name} with email {doc.email_id}")

        # Ensure email exists on the supplier record
        if not doc.email_id:
            frappe.throw(_("Supplier must have a valid email address."))

        # Check if a User already exists with the given email ID
        if frappe.db.exists('User', doc.email_id):
            frappe.msgprint(_("A User with this email already exists."), alert=True)
            return  # Exit if user already exists

        # Create a new User for the supplier
        user = frappe.get_doc({
            'doctype': 'User',
            'email': doc.email_id,
            'first_name': doc.supplier_name,
            'enabled': 0,  # Initially inactive
            'role_profile_name': "Supplier",  # Assign the role of 'Supplier'
            'new_password': frappe.generate_hash(length=12),  # Generate secure temporary password
        })

        user.insert(ignore_permissions=True)
        frappe.logger().info(f"User {user.name} created for supplier {doc.supplier_name}")

        # Optionally, link the newly created User to the Supplier document
        doc.user_id = user.name
        doc.save()

        # Notify the admin or other concerned users (optional)
        # Uncomment the following code to enable notification
        # notify_admin_of_new_supplier(doc)

    except frappe.DuplicateEntryError:
        # Specific error for duplicate user creation
        frappe.throw(_("A User with this email already exists."))
        
    except Exception as e:
        # Enhanced logging for better debugging
        frappe.logger().error(f"Error while creating user for supplier {doc.name}: {str(e)}")
        frappe.throw(_("There was an issue while processing the supplier registration. Please try again."))

def notify_admin_of_new_supplier(doc):
    """Notify admin when a new supplier is registered."""
    try:
        # Retrieve admin user(s)
        admin_users = frappe.get_all('UserRole', filters={'role': 'System Manager'}, fields=['parent'])

        if not admin_users:
            frappe.logger().warning("No System Manager users found for notification.")
            return

        # Loop over system managers and send notification
        for admin in admin_users:
            notification = frappe.get_doc({
                'doctype': 'Notification Log',
                'for_user': admin.parent,
                'subject': _('New Supplier Registration'),
                'email_content': _("A new supplier has registered:\n\n"
                                   f"Supplier Name: {doc.supplier_name}\n"
                                   f"Supplier Email: {doc.email_id}\n"
                                   "Please review and approve the registration.")
            })
            notification.insert(ignore_permissions=True)
            frappe.logger().info(f"Notification sent to admin: {admin['parent']}")

    except Exception as e:
        frappe.logger().error(f"Error while sending admin notification for supplier {doc.name}: {str(e)}")
