# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models,api,_
import odoo.addons.decimal_precision as dp


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def create(self, vals):
        res = super(PurchaseOrder, self).create(vals)
        if res and res.partner_id.picking_type_id:
            res.picking_type_id = res.partner_id.picking_type_id.id
        return res


PurchaseOrder()
