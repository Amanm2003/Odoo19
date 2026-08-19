from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SaleApprovalConfig(models.Model):
    _name = "sale.approval.config"
    _description = "Sales Approval Configuration"
    _order = "sequence"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True,)

    sequence = fields.Integer(default=10, tracking=True,)

    min_amount = fields.Float(tracking=True,)

    max_amount = fields.Float(tracking=True,)

    risk_category = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ])

    credit_limit_breach = fields.Boolean(string="Risk & Breach")

    approver_ids = fields.Many2many(
        'res.users',
        string='Approvers', tracking=True,
    )

    active = fields.Boolean(default=True, tracking=True,)
    
    @api.constrains('min_amount', 'max_amount', 'active')
    def _check_amount_range_overlap(self):
        for rec in self:
            if rec.min_amount > rec.max_amount:
                raise ValidationError("Minimum Amount cannot be greater than Maximum Amount.")

            overlap = self.search([
                ('id', '!=', rec.id),
                ('active', '=', True),
                ('min_amount', '<=', rec.max_amount),
                ('max_amount', '>=', rec.min_amount),
            ], limit=1)

            if overlap:
                raise ValidationError(
                    "The amount range overlaps with the existing rule" 
                ) 