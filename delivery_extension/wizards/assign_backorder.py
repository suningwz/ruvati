# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _


class AssignBackOrder(models.TransientModel):
    _name = "assign.back.order"

    def action_assign_backorder(self):
        if self._context.get('active_model', '') == 'stock.picking':
            picking_ids = self.env['stock.picking'].browse(self._context.get('active_ids'))
            picking_ids.do_unreserve()
            picking_ids.write({'is_back_order': True})
        elif self._context.get('active_model', '') == 'sale.order':
            sale_ids = self.env['sale.order'].browse(self._context.get('active_ids'))
            sale_ids.write({'is_back_order': True})
            sale_ids.mapped('picking_ids').do_unreserve()

        return {'success': True}

    def action_revert_backorder(self):
        if self._context.get('active_model', '') == 'stock.picking':
            picking_ids = self.env['stock.picking'].browse(self._context.get('active_ids'))
            picking_ids.write({'is_back_order': False})
            picking_ids.action_assign()
        elif self._context.get('active_model', '') == 'sale.order':
            sale_ids = self.env['sale.order'].browse(self._context.get('active_ids'))
            sale_ids.write({'is_back_order': False})
            sale_ids.mapped('picking_ids').action_assign()

        return {'success': True}


