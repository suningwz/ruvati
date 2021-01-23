from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    writeoff_account_id = fields.Many2one('account.account', 'Discount Account',
                                          domain=[('deprecated', '=', False)])

ResCompany()