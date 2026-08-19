# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    credit_approver_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_company_credit_approver_rel',
        column1='company_id',
        column2='user_id',
        string='Credit Approvers',
        help='Users allowed to approve or refuse sale orders placed on credit '
             'hold. Any one of them approving is sufficient to release an order.',
    )
