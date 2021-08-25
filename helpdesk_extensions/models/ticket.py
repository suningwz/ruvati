# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    @api.model
    def create(self, vals):
        res = super(HelpdeskTicket, self).create(vals)
        if res.sale_order_id:
            message = _(
            "Help Desk TICKET: <a href=# data-oe-model=helpdesk.ticket data-oe-id=%d>%s</a>") % (
                      res.id, res.name)
            res.sale_order_id.message_post(body=message)
        return res

    def write(self, vals):
        res = super(HelpdeskTicket, self).write(vals)
        for rec in self:
            if vals.get('sale_order_id', False):
                message = _(
                    "Help Desk TICKET: <a href=# data-oe-model=helpdesk.ticket data-oe-id=%d>%s</a>") % (
                              rec.id, rec.name)
                rec.sale_order_id.message_post(body=message)
        return res
