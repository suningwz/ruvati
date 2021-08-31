# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OrderConfirmMulti(models.TransientModel):
    _name = "order.confirm.multi"

    def action_confirm_sale(self):
        active_ids = self._context.get('active_ids', [])
        sale_ids = self.env['sale.order'].browse(active_ids)
        sale_ids_to_confirm = sale_ids.filtered(lambda l: l.state in ['draft', 'sent'])
        if not sale_ids_to_confirm:
            raise UserError("Please select the quotations to confirm")
        sale_ids_to_confirm.action_confirm()
        return {'type': 'ir.actions.client', 'tag': 'reload'}




