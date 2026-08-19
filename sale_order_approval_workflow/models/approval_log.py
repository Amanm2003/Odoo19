from odoo import models, fields


class SaleApprovalLog(models.Model):
    _name = "sale.approval.log"
    _description = "Sales Approval Log"

    sale_id = fields.Many2one(
        "sale.order",
        ondelete="cascade"
    )

    user_id = fields.Many2one(
        "res.users"
    )

    action = fields.Selection([
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ])

    remarks = fields.Text()

    date = fields.Datetime(
        default=fields.Datetime.now
    )