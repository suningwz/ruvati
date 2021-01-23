# See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    rma_id = fields.Many2one('rma.ret.mer.auth', string='RMA')


class StockMove(models.Model):
    _inherit = 'stock.move'

    rma_id = fields.Many2one('rma.ret.mer.auth', string='RMA')
