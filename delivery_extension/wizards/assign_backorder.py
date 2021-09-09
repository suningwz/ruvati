# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class AssignBackOrder(models.TransientModel):
    _name = "assign.back.order"

    def action_assign_backorder(self):
        picking_ids = self.env['stock.picking'].browse(self._context.get('active_ids'))
        picking_ids.do_unreserve()
        picking_ids.write({'is_back_order': True})

        return {'success': True}


