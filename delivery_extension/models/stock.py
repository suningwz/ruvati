# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_create_label = fields.Boolean(string="Create Label")
    shipper_number = fields.Char(string="Shipper No.")
    is_ship_collect = fields.Boolean(string="Ship Collect")
    create_label_on_validate = fields.Boolean(string="Create Label")
    
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
        return super(StockPicking, self).button_validate()

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
