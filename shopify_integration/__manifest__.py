{
    "name": "Shopify Integration",
    "version": "1.0",
    "category": "Sales",
    "summary": "Sync Products and Customers from Shopify to Odoo",
    "description": "Basic Shopify integration module for Odoo 18 Community",
    "depends": ["base", "product", "sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/shopify_views.xml",
        "views/product_template_views.xml",
        "views/sale_order_view.xml",
        "data/shopify_cron.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
