# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    @api.model
    def _get_default_admin(self):
        user_ids = self.env['res.users'].search([]).filtered(lambda l: self.env.ref('stock.group_stock_manager').id in l.groups_id.ids)
        user_list = user_ids.ids or []
        return user_list

    assigned_user_ids = fields.Many2many('res.users', string="Assigned Users", default=lambda self: self._get_default_admin())
