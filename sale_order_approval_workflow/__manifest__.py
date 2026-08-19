{
    "name": "Sales Order Approval Workflow",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Multi Level Sales Approval Workflow",
    "author": "Custom",
    "depends": [
        "sale_management",
        "mail",
        "crm_sale_product_images",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",

        # "data/mail_template.xml",

        "views/approval_config_views.xml",
        "views/sale_order_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}