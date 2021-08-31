# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from itertools import groupby
from odoo import api, fields, models, exceptions, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_ship_collect = fields.Boolean(string="Ship Collect", copy=False)
#    carrier_id = fields.Many2one("delivery.carrier", string="Carrier", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    shipper_number = fields.Char(string="Shipper No.")
    products = fields.Char(string="Products", compute='_get_products_internal_code')
    is_back_order = fields.Boolean(string="Back Order")
    duplicate_order = fields.Boolean("Duplicate Order", copy=False)
    shipment_status = fields.Selection([('assigned', 'Ready Shipment'), ('confirmed', 'Waiting Availability'), ('done', 'Shipped')], string="Shipment Status", copy=False)

    def _get_products_internal_code(self):
        for rec in self:
            product_code = rec.order_line.filtered(lambda l:l.product_id.type != 'service' and l.product_id.default_code).mapped('product_id').mapped('default_code')
            rec.products = product_code and ','.join(product_code) or ''

    def message_notify(self, *,
                       partner_ids=False, parent_id=False, model=False, res_id=False,
                       author_id=None, email_from=None, body='', subject=False, **kwargs):
        """ Shortcut allowing to notify partners of messages that shouldn't be
        displayed on a document. It pushes notifications on inbox or by email depending
        on the user configuration, like other notifications. """
        return
    
    @api.onchange('partner_id')
    def ship_collect_onchange_partner(self):
        if self.partner_id and self.partner_id.is_ship_collect:
            self.is_ship_collect = self.partner_id.is_ship_collect
            self.carrier_id = self.partner_id.carrier_id
            self.shipper_number = self.partner_id.shipper_number
        else:
            self.carrier_id = self.partner_id.property_delivery_carrier_id.id
            self.is_ship_collect = False
            self.shipper_number = False

    @api.onchange('is_ship_collect')
    def onchange_ship_collect(self):
        if not self.is_ship_collect:
            self.shipper_number = False
        else:
            self.carrier_id = self.partner_id.carrier_id
            self.shipper_number = self.partner_id.shipper_number

    @api.model
    def create(self, vals):
        internal_ref = []
        if vals.get('client_order_ref', False):
            existing_order_ids = self.search([('client_order_ref', '=', vals.get('client_order_ref', False))])
            if len(existing_order_ids) >= 1:
                vals.update({'duplicate_order': True})

        # if vals.get('order_line', []):
        #     for line in vals.get('order_line', []):
        #         if line[2].get('product_id', False):
        #             product = self.env['product.product'].browse(line[2].get('product_id'))
        #             if product and product.default_code and product.type != 'service':
        #                 internal_ref.append(product.default_code)
        #     vals.update({'products': ','.join(internal_ref)})
        sec_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'sub_warehouse')], limit=1)
        if vals.get('amazon_channel', False) and vals.get('amazon_channel') == 'fba':
            return super(SaleOrder, self).create(vals)
        vals.update({'warehouse_id': sec_warehouse and sec_warehouse.id or vals.get('warehouse_id', False)})
        return super(SaleOrder, self).create(vals)
        
    def write(self, vals):
        internal_ref = []
        if vals.get('client_order_ref', False):
            existing_order_ids = self.search([('client_order_ref', '=', vals.get('client_order_ref', False))])
            if len(existing_order_ids) >= 1:
                vals.update({'duplicate_order': True})
            else:
                vals.update({'duplicate_order': False})
        # if vals.get('order_line', []):
        #     for line in vals.get('order_line', []):
        #         if line[2]:
        #             if line[2].get('product_id', False):
        #                 product = self.env['product.product'].browse(line[2].get('product_id'))
        #                 if product and product.default_code and product.type != 'service':
        #                     internal_ref.append(product.default_code)
        #             else:
        #                 order_line = self.env['sale.order.line'].browse(line[1])
        #                 if order_line and order_line.product_id.default_code and order_line.product_id.type != 'service':
        #                     internal_ref.append(order_line.product_id.default_code)
        #         else:
        #             order_line = self.env['sale.order.line'].browse(line[1])
        #             if order_line and order_line.product_id.default_code and order_line.product_id.type != 'service':
        #                 internal_ref.append(order_line.product_id.default_code)
        #     vals.update({'products': ','.join(internal_ref)})
#        sec_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'sub_warehouse')], limit=1)
#        if self.warehouse_id != sec_warehouse:
#            vals.update({'warehouse_id': sec_warehouse and sec_warehouse.id or self.warehouse_id.id})
        return super(SaleOrder, self).write(vals)

    @api.depends('order_line.customer_lead', 'date_order', 'order_line.state')
    def _compute_expected_date(self):
        """ For service and consumable, we only take the min dates. This method is extended in sale_stock to
			take the picking_policy of SO into account.
		"""
        for order in self:
            dates_list = []
            back_order_pickings = order.picking_ids.filtered(lambda r: r.picking_type_id == order.warehouse_id.pick_type_id and r.is_back_order and order.expected_date != r.scheduled_date)
            schedule_date_list = back_order_pickings and back_order_pickings.mapped('scheduled_date') or []
            if schedule_date_list:
                order.expected_date = schedule_date_list[0]
                continue
            for line in order.order_line.filtered(
                    lambda x: x.state != 'cancel' and not x._is_delivery() and not x.display_type):
                dt = line._expected_date()
                dates_list.append(dt)
            if dates_list:
                order.expected_date = fields.Datetime.to_string(min(dates_list))
            else:
                order.expected_date = False

SaleOrder()
