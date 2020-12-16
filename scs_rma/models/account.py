# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.move'

    rma_id = fields.Many2one('rma.ret.mer.auth', string='RMA')
    is_rma_refund = fields.Boolean(string="RMA Refund?")
    
    
class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'
    
    is_rma_refund = fields.Boolean(string="RMA Refund?")
    
    def _prepare_default_reversal(self, move):
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)
        res.update({'is_rma_refund': self.is_rma_refund})
        return res
