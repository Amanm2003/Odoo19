from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    shopify_name = fields.Char(
        string="Shopify Name",
        copy=False,
        help="Product name used in Shopify.",
    )
    shopify_sale_price = fields.Float(string="Shopify Sale Price")