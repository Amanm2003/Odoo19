# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Related (readonly=False) so the value is persisted on the company and
    # respected at runtime. company_id is provided by the base settings model.
    credit_approver_ids = fields.Many2many(
        comodel_name='res.users',
        related='company_id.credit_approver_ids',
        readonly=False,
        string='Credit Approvers',
        help='Users allowed to approve or refuse sale orders placed on credit '
             'hold. Any single approver is sufficient.',
    )
