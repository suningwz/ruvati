# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class CheckReservedPicking(models.TransientModel):
    _name = "check.reserved.picking"

    def action_check_reserved_pick(self):
        waiting_picking_ids = self.env['stock.picking'].search([('state', '=', 'confirmed')])
        waiting_picking_ids.action_assign()
        return {'type': 'ir.actions.client', 'tag': 'reload'}




