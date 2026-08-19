from odoo import models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def action_done(self, feedback=False, attachment_ids=None):
        res = super().action_done(
            feedback=feedback,
            attachment_ids=attachment_ids
        )

        for activity in self:

            if (
                activity.res_model == 'sale.order'
                and activity.user_id == self.env.user
            ):

                sale = self.env['sale.order'].browse(
                    activity.res_id
                )

                if (
                    sale.exists()
                    and sale.approval_state == 'waiting_approval'
                    and self.env.user in sale.approval_config_id.approver_ids
                ):
                    sale.action_approve()

        return res