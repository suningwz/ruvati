from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_payment_journal = fields.Boolean(string='Is Payment Journal')

AccountJournal()