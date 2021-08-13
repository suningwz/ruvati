# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CheckReservedPicking(models.TransientModel):
    _name = "check.reserved.picking"

    def action_check_reserved_pick(self):
        waiting_picking_ids = self.env['stock.picking'].search([('state', '=', 'confirmed')])
        waiting_to_pick = waiting_picking_ids.filtered(lambda l: l.picking_type_id.warehouse_id.pick_type_id.id == l.picking_type_id.id)

        if not waiting_to_pick:
            raise UserError("Can't find any pickings on waiting availability")
        waiting_to_pick.action_assign()
        return {'type': 'ir.actions.client', 'tag': 'reload'}




