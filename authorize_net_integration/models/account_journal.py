# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PaymentAcquirerAuthorize(models.Model):
    _inherit = 'payment.acquirer'

    authorize_login = fields.Char(string='API Login Id', required=False, groups='base.group_user')
    authorize_transaction_key = fields.Char(string='API Transaction Key', required=False, groups='base.group_user')
    authorize_signature_key = fields.Char(string='API Signature Key', required=False, groups='base.group_user')


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_authorizenet = fields.Boolean('Authorize.Net Journal',
                                     help="Check this box to determine this is an authorize.net payment Journal")
    surcharge_customer = fields.Float('CreditCard Processing Fee (Customer)')
    surcharge_user = fields.Float('CreditCard Processing Fee (User)')
    surcharge_account_id = fields.Many2one('account.account', string='CreditCard Processing Fee Account',
                                           domain=[('deprecated', '=', False)],
                                           help="It acts as a default account for credit amount")


AccountJournal()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
