# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_create_label = fields.Boolean(string="Is Create Label")
    shipper_number = fields.Char(string="Shipper No.")
    is_ship_collect = fields.Boolean(string="Ship Collect")
    create_label_on_validate = fields.Boolean(string="Create Label-validate")
    transaction_id = fields.Char("Transaction ID")
    # string change to avoid custom filter confusions
    backorder_ids = fields.One2many('stock.picking', 'backorder_id', 'List of Back Orders')

    def send_data(self, data):
        configuration = self.env['edi.configuration'].search([], limit=1)
        exchange_token_url = configuration.exchange_token_url
        uid = configuration.uid
        password = configuration.password
        auth_token = configuration.auth_token
        client_id = configuration.client_id
        try:
            response = requests.get(exchange_token_url,
                                    headers={'UID': uid, 'PWORD': password,
                                             'AUTHTOKEN': auth_token,
                                             'CLIENTID': client_id})
            content = json.loads(response.content)
            access_token = content['ExchangeTokenResult']['access_token']
            #post data
            post_url = configuration.post_url
            response = requests.post(post_url, data=json.dumps(data), headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
            self.transaction_id = response.content and json.loads(response.content)
        except Exception as e:
            pass

    def _get_cartons(self):
        cartons = []
        tracking_ref = self.carrier_tracking_ref and self.carrier_tracking_ref.split(',')
        count = 0
        for package in self.package_ids:
            items = []
            weight = package.shipping_weight
            for quant in package.quant_ids:
                items.append({'pack_quantity': quant.quantity,
                              "line_item_data" : {
                                    "item_no" : quant.product_id.default_code,
                                    "qty_ordered": quant.quantity,
                                }
                              })
            cartons.append({
                "gross_weight": weight,
                "net_weight": weight,
                "tracking_number": tracking_ref and tracking_ref[count],
                "packaging_code": package.name,
                "items": items
            })
            count += 1
        return cartons

    def action_done(self):
        res = super(StockPicking, self).action_done()
        for rec in self:
            if not rec.sale_id.edi_order:
                break
            invoice_partner_id = rec.sale_id.partner_invoice_id
            shipment_data = {
                "BSISerObjects.bsishipments": {

                    "pro_number": rec.sale_id.pro_number,
                    "bill_of_lading_number": rec.sale_id.bill_of_lading_number,
                    "ship_via_description": rec.carrier_id.name,
                    "orders": [{
                        'order_info': {
                            'order_date': rec.sale_id.date_order.strftime('%Y-%m-%d'),
                            'customer_number': rec.sale_id.customer_id,
                            "ship_date": rec.scheduled_date.strftime('%Y-%m-%d'),
                            'ship_to_address': {
                                "name": rec.partner_id.name,
                                "address_1": rec.partner_id.street,
                                "address_2": rec.partner_id.street2,
                                "city": rec.partner_id.city,
                                "state": rec.partner_id.state_id.code,
                                "zip": rec.partner_id.zip,
                                "country": rec.partner_id.country_id.code,

                            },
                            'billing_address': {
                                "name": invoice_partner_id.name,
                                "address_1": invoice_partner_id.street,
                                "address_2": invoice_partner_id.street2,
                                "city": invoice_partner_id.city,
                                "state": invoice_partner_id.state_id.code,
                                "zip": invoice_partner_id.zip,
                                "country": invoice_partner_id.country_id.code,

                            },
                            'ship_from_address': {
                                "name": rec.company_id.name,
                                "address_1": rec.company_id.street,
                                "address_2": rec.company_id.street2,
                                "city": rec.company_id.city,
                                "state": rec.company_id.state_id.code,
                                "zip": rec.company_id.zip,
                                "country": rec.company_id.country_id.code,

                            },
                            'cartons': rec._get_cartons()
                        }

                    }]
                }
            }
            rec.send_data(shipment_data)

        return res

    
#    @api.depends('picking_type_id')
#    def _compute_to_create_label(self):
#        for rec in self:
#            if rec.picking_type_id and rec.picking_type_id == rec.picking_type_id.warehouse_id.pack_type_id:
#                rec.is_create_label = True
#            else:
#                rec.is_create_label = False
    
    @api.model
    def create(self, vals):
        res = super(StockPicking, self).create(vals)
        if res.picking_type_id.warehouse_id.delivery_steps == 'pick_pack_ship':
            if res.picking_type_id and res.picking_type_id == res.picking_type_id.warehouse_id.pick_type_id:
                res.is_create_label = True
            else:
                res.is_create_label = False
        elif res.picking_type_id.code == 'outgoing':
            res.is_create_label = True
        return res
        
    def button_validate(self):
        if self.picking_type_id == self.picking_type_id.warehouse_id.pick_type_id:
            if self.is_create_label and not self.carrier_id:
                raise ValidationError('Please configure a Carrier to create a Label for %s' % self.name)
        self.create_label_on_validate = False
       	res = super(StockPicking, self).button_validate()
        self.write({'is_back_order': False})
        return res
        
    def action_create_label(self):
        """ Invokes on click of Create Label button from picking, to create shipping label before validating by assigning the packages.
        """
        for pick in self:
#            if pick.state != 'done':
#                raise ValidationError('Sorry!!! Please validate %s before creating Label' % pick.name)
            if not pick.is_create_label:
                raise ValidationError('Sorry!!! You cannot create a label for %s' % pick.name)
            if pick.is_create_label and not pick.carrier_id:
                raise ValidationError('Please configure a Carrier to create a Label for %s' % pick.name)
#            pick.action_assign()
            if not pick.has_packages:
                pick.put_in_pack()
            if pick.carrier_id:
                if pick.carrier_id.integration_level == 'rate_and_ship' and pick.picking_type_code != 'incoming':
                    pick.create_label_on_validate = True
                    pick.send_to_shipper()
                    pick.is_create_label = False

    def send_to_shipper(self):
        if self.create_label_on_validate:
#            self.is_create_label = False
            return super(StockPicking, self).send_to_shipper()
#    
StockPicking()



class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def _get_new_picking_values(self):
        res = super(StockMove, self)._get_new_picking_values()
        order = self.env['sale.order']
        origin = res.get('origin', False)
        if origin:
            order = self.env['sale.order'].search([('name', '=', origin)], limit=1)
        if order and order.is_ship_collect:
            res.update({'carrier_id': order.carrier_id and order.carrier_id.id or False,
                        'shipper_number': order.shipper_number,
                        'is_ship_collect': order.is_ship_collect,
                })
        elif order and res.get('location_dest_id', 0) == order.warehouse_id.wh_pack_stock_loc_id.id:
            res['carrier_id'] = order.carrier_id and order.carrier_id.id or res['carrier_id']
        return res
        
#    def _get_new_picking_values(self):
#        vals = super(StockMove, self)._get_new_picking_values()
#        if vals.get('origin', False):
#            order = self.env['sale.order'].search([('name', '=', vals.get('origin'))])
#            if order and vals.get('location_dest_id', 0) == order.warehouse_id.wh_pack_stock_loc_id.id:
#                vals['carrier_id'] = order.carrier_id and order.carrier_id.id or vals['carrier_id'] 
#        return vals
    
StockMove


class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'
    
    carrier_tracking_ref = fields.Char(string='Tracking Reference', copy=False)

StockQuantPackage()
