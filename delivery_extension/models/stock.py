# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
from itertools import groupby
import logging
_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_create_label = fields.Boolean(string="Is Create Label")
    shipper_number = fields.Char(string="Shipper No.")
    is_ship_collect = fields.Boolean(string="Ship Collect")
    create_label_on_validate = fields.Boolean(string="Create Label-validate")
    transaction_id = fields.Char("Transaction ID")
    duplicate_order = fields.Boolean("Duplicate Order", related="sale_id.duplicate_order")
    customer_po_number = fields.Char(string="Customer PO", related="sale_id.client_order_ref")
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
            if rec.picking_type_id and rec.picking_type_id == rec.picking_type_id.warehouse_id.pick_type_id and not rec.is_back_order:
                rec.sale_id.shipment_status = rec.state

        return res
    
    def action_assign(self):
        for rec in self:
            if rec.duplicate_order or rec.is_back_order:
                res = False
                continue
            else:
                res = super(StockPicking, rec).action_assign()
        for rec in self:
            if rec.picking_type_id and rec.picking_type_id == rec.picking_type_id.warehouse_id.pick_type_id and not rec.is_back_order:
                rec.sale_id.shipment_status = rec.state
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
            try:
                if not pick.is_create_label:
                    raise ValidationError('Sorry!!! You cannot create a label for %s' % pick.name)
                if pick.is_create_label and not pick.carrier_id:
                    raise ValidationError('Please configure a Carrier to create a Label for %s' % pick.name)
                if not pick.has_packages:
                    pick.put_in_pack()
                if pick.carrier_id:
                    if pick.carrier_id.integration_level == 'rate_and_ship' and pick.picking_type_code != 'incoming':
                        pick.create_label_on_validate = True
                        pick.send_to_shipper()
                        pick.is_create_label = False
                        self.env.cr.commit()

            except Exception as e:
                _logger.info("%s PICKING:%s" % (e, pick.name))
                raise ValidationError("%s PICKING:%s" % (e, pick.name))

    def send_to_shipper(self):
        if self.create_label_on_validate and self.is_create_label:
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

    def _assign_picking(self):
        """ Try to assign the moves to an existing picking that has not been
        reserved yet and has the same procurement group, locations and picking
        type (moves should already have them identical). Otherwise, create a new
        picking to assign them to. """
        Picking = self.env['stock.picking']
        grouped_moves = groupby(sorted(self, key=lambda m: [f.id for f in m._key_assign_picking()]), key=lambda m: [m._key_assign_picking()])
        for group, moves in grouped_moves:
            moves = self.env['stock.move'].concat(*list(moves))
            new_picking = False
            # Could pass the arguments contained in group but they are the same
            # for each move that why moves[0] is acceptable
            picking = moves[0]._search_picking_for_assignation()
            if picking:
                if any(picking.partner_id.id != m.partner_id.id or
                        picking.origin != m.origin for m in moves):
                    # If a picking is found, we'll append `move` to its move list and thus its
                    # `partner_id` and `ref` field will refer to multiple records. In this
                    # case, we chose to  wipe them.
                    picking.write({
                        'partner_id': False,
                        'origin': False,
                    })
            else:
                new_picking = True
                picking = Picking.create(moves._get_new_picking_values())
            sale_id = moves.group_id.sale_id
            picking_type_id = sale_id.warehouse_id.pick_type_id
            if picking.picking_type_id.id == picking_type_id.id and len(moves) > 1:
                moves[0].picking_id = picking.id
                for m in moves.filtered(lambda l: not l.picking_id):
                    new_pick = Picking.create(m._get_new_picking_values())
                    m.write({'picking_id': new_pick.id})
            elif picking.picking_type_id.id == picking_type_id.id and len(moves) == 1 and len(sale_id.order_line) > 1:
                for m in moves.filtered(lambda l: not l.picking_id):
                    new_pick = Picking.create(m._get_new_picking_values())
                    m.write({'picking_id': new_pick.id})
            else:
                moves.write({'picking_id': picking.id})
            moves._assign_picking_post_process(new=new_picking)
        return True
        
#    def _get_new_picking_values(self):
#        vals = super(StockMove, self)._get_new_picking_values()
#        if vals.get('origin', False):
#            order = self.env['sale.order'].search([('name', '=', vals.get('origin'))])
#            if order and vals.get('location_dest_id', 0) == order.warehouse_id.wh_pack_stock_loc_id.id:
#                vals['carrier_id'] = order.carrier_id and order.carrier_id.id or vals['carrier_id'] 
#        return vals

    def _action_assign(self):
        res = False
        for rec in self:
            if rec.picking_type_id.id == rec.warehouse_id.pack_type_id.id:
                pick_ids = rec.picking_id.sale_id.picking_ids.filtered(lambda l:l.picking_type_id.id == rec.warehouse_id.pick_type_id.id)
                if all(p.state == 'done' for p in pick_ids):
                    res = super(StockMove, rec.picking_id.move_lines)._action_assign()
                else:
                    continue
            else:
                res = super(StockMove, self)._action_assign()
        return res
    
StockMove


class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'
    
    carrier_tracking_ref = fields.Char(string='Tracking Reference', copy=False)

StockQuantPackage()
