# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

#    warehouse_id = fields.Many2one('stock.warehouse', string="Pick From", required=True)
    picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type", required=True)
#    , domain="[('sequence_code', '=', 'PICK')]"
    picking_ids = fields.One2many(
        'stock.picking', 'batch_id', string='Transfers',
        domain="[('company_id', '=', company_id), ('state', 'not in', ('done', 'cancel')), ('picking_type_id', '=', picking_type_id)]",
        help='List of transfers associated to this batch')
    picking_type_id_code = fields.Char('Picking Type Code', related='picking_type_id.sequence_code', readonly=True)

    def print_picking(self):
        pickings = self.mapped('picking_ids')
        if not pickings:
            raise UserError(_('Please add atleast one picking.'))
        return self.env.ref('stock_pick_batch.action_report_pic_batch').report_action(self)

