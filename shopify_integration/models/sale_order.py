from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_shopify_order = fields.Boolean(
        string="Is Shopify Order",
        default=False,
        copy=False,
        help="Indicates whether this sales order was imported from Shopify.",
    )
    
    shopify_id = fields.Char(string="Shopify Order No.")