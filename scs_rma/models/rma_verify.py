# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RMARetVerify(models.Model):
    _name = 'rma.ret.verify'

    name = fields.Char(string="Name")
    rma_id = fields.Many2one('rma.ret.mer.auth', string='RMA', copy=False)
    return_date = fields.Date('Date', default=fields.Date.context_today, help='Date', copy=False)
    return_picking = fields.Char(string="Order")
    return_product = fields.Char(string="Product")
    need_credit_memo = fields.Boolean('Need Refund Invoice?', default=True)
    state = fields.Selection([('draft', 'Draft'), ('accepted', 'Accepted')], string="State", default="draft", copy=False)
    customer_po_number = fields.Char(string="PO number")
    tracking_number = fields.Char(string="Tracking Number")
    reason_id = fields.Many2one("rma.reasons", string="Reason")
    
    @api.model
    def create(self, vals):
        sequence_val = self.env['ir.sequence'].next_by_code('rma.return') or '/'
        vals.update({'name': sequence_val,})
        return super(RMARetVerify, self).create(vals)
    
    def action_verify_accept(self):
#        sequence_val = self.env['ir.sequence'].next_by_code('rma.rma') or '/'
#        self.write({'name': sequence_val})
        picking = self.env['stock.picking']
        if self.return_picking:
            picking = self.env['stock.picking'].search([('name', '=', self.return_picking)])
        elif self.customer_po_number:
            sale_order = self.env['sale.order'].search([('client_order_ref', '=', self.customer_po_number)], limit=1)
            if sale_order:
                picking = self.env['stock.picking'].search([('origin', '=', sale_order.name), ('picking_type_id', '=', sale_order.warehouse_id.pack_type_id.id)], limit=1)
        else:
            pass
        product = self.env['product.product'].search([('barcode', '=', self.return_product)])
        
        if picking and product.id in picking.move_line_ids.mapped('product_id').ids:
            source_loc = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
            destination_loc = picking.picking_type_id.warehouse_id.lot_stock_id
            rma = self.create_rma(picking, product, source_loc, destination_loc)
            move_vals = {
                        'product_id': product and product.id or False,
                        'name': product and product.name or False,
                        'origin': rma.name,
                        'product_uom_qty': 1.0,
                        'location_id': source_loc and source_loc.id or False,
                        'location_dest_id': destination_loc and destination_loc.id or False,
                        'product_uom': product.uom_id and product.uom_id.id or False,
                        'rma_id': rma.id,
                        'group_id': picking.sale_id.procurement_group_id.id,
#                        'price_unit': rma_line.price_subtotal or 0,
                    }
            picking_type_id = self.env[
                            'stock.picking.type'].search([
                                ('code', '=', 'incoming'),
                                ('warehouse_id', '=', picking.picking_type_id.warehouse_id.id)],
                            limit=1).id
            picking_vals = {
                'move_type': 'one',
                'picking_type_id': picking_type_id or False,
                'partner_id': picking and picking.partner_id.id or False,
                'origin': rma.name,
                'move_lines': [(0, 0, move_vals)],
                'location_id': move_vals['location_id'],
                'location_dest_id': move_vals['location_dest_id'],
                'rma_id': rma.id,
            }
            picking_rec = self.env[
                'stock.picking'].create(picking_vals)
            picking_rec.action_confirm()
            picking_rec.action_assign()
            for move in picking_rec.move_lines.filtered(lambda m: m.state not in ['done', 'cancel']):
                for move_line in move.move_line_ids:
                    move_line.qty_done = move_line.product_uom_qty
            picking_rec.action_done()
            self.write({'state': 'accepted', 'rma_id': rma.id,})
        else:
            raise ValidationError("Sorry!!! Cannot accept this product.")
    
    def create_rma(self, picking, product, source_loc, destination_loc):
        if all([picking, product, source_loc, destination_loc]):
            invoice_line = self.env['account.move.line']
            rma_id = self.env['rma.ret.mer.auth']
            sequence_val = self.env['ir.sequence'].next_by_code('rma.rma') or '/'
            rma_vals = {
                        'name': sequence_val,
                        'rma_type': 'customer',
                        'partner_id': picking.sale_id.partner_id.id,
                        'rma_date': self.return_date,
                        'sale_order_id': picking.sale_id.id,
                        'state': 'approve',
                        'customer_po_number': self.customer_po_number,
                        'tracking_number': self.tracking_number,
                    }
            sale_line = picking.sale_id.order_line.filtered(lambda r: r.product_id.id == product.id)
            rma_line_vals = {
                            'product_id': product and product.id or False,
                            'total_qty': sale_line and sale_line.product_uom_qty or 0,
                            'delivered_quantity': sale_line and sale_line.qty_delivered,
                            'order_quantity': sale_line and sale_line.product_uom_qty or 0,
                            'refund_qty': 1.0,
                            'received_qty': 1.0,
                            'refund_price': sale_line.price_unit,
                            'price_unit': sale_line.price_unit or 0,
                            'price_subtotal': sale_line.price_subtotal or 0,
                            'source_location_id': source_loc and source_loc.id or False,
                            'destination_location_id': destination_loc and destination_loc.id or False,
                            'type': 'return',
                            'tax_id': sale_line.tax_id,
                            'reason_id': self.reason_id and self.reason_id.id or False,
                        }
            RMA = self.env['rma.ret.mer.auth'].search([(['sale_order_id', '=', picking.sale_id.id])])
            if RMA:
                total_refund_qty = sum(RMA.mapped('rma_sale_lines_ids').filtered(lambda r: r.product_id.id == product.id).mapped('refund_qty')) + 1.0
                if sale_line and total_refund_qty > sale_line.qty_delivered:
                    raise ValidationError("Sorry!!! Something went wrong. \n You are trying to verify an accepted product.")
            RMA_FOR_SALE = self.env['rma.ret.mer.auth'].search([('sale_order_id', '=', picking.sale_id.id), ('state', 'in', ['approve','verification']), ('rma_from_verify', '=', False)])
            for rma in RMA_FOR_SALE:
                rma_line = rma.rma_sale_lines_ids.filtered(lambda r: r.product_id.id == product.id)
                if rma_line and rma_line.received_qty + 1.0 <= rma_line.refund_qty:
                    rma_line.received_qty += 1.0
                    return rma
                else:
                    continue
                    
            if self.need_credit_memo:
                rma_for_sale = self.env['rma.ret.mer.auth'].search([('sale_order_id', '=', picking.sale_id.id), ('state', '=', 'approve'), ('need_credit_memo', '=', True)])
                for rma in rma_for_sale:
                    rma_line = rma.rma_sale_lines_ids.filtered(lambda r: r.product_id.id == product.id)
                    rma_line_return_qty = rma_line and rma_line.refund_qty or 0
                    new_return_qty = rma_line_return_qty + 1.0
                    if rma.invoice_ids:
                        invoice_line = rma.invoice_ids.mapped('invoice_line_ids').filtered(lambda r: r.product_id.id == product.id and r.quantity >= new_return_qty)
                    if invoice_line:
#                        rma.write({''})
                        if rma_line:
                            rma_line.refund_qty = new_return_qty
                            if rma_line.received_qty + 1.0 <= new_return_qty:
                                rma_line.received_qty += 1.0
                        else:
                            rma_line_vals.update({'rma_id': rma.id})
                            rma_sale_line = self.env['rma.sale.lines'].create(rma_line_vals)
                        return rma
                invoices = self.env['account.move'].search([('type', '=', 'out_refund'), ('invoice_origin', '=', picking.sale_id.name), ('rma_id', '=', False), ('is_rma_refund', '=', True)])
                for inv in invoices:
                    invoice_line = inv.invoice_line_ids.filtered(lambda r: r.product_id.id == product.id and r.quantity >= 1.0)
                    if invoice_line:
                        rma_vals.update({'need_credit_memo': True})
                        rma_id = self.env['rma.ret.mer.auth'].with_context(rma_from_verify=True).create(rma_vals)
                        rma_line_vals.update({'rma_id': rma_id.id})
                        rma_sale_line = self.env['rma.sale.lines'].create(rma_line_vals)
                        inv.rma_id = rma_id.id
                        return rma_id
                if rma_for_sale:
                    rma_without_invoice = rma_for_sale.filtered(lambda r: not r.invoice_ids)
                    if rma_without_invoice:
                        rma_line = rma_without_invoice[0].rma_sale_lines_ids.filtered(lambda r: r.product_id.id == product.id)
                        if rma_line:
                            rma_line.refund_qty += 1.0
                            if rma_line.received_qty + 1.0 <= rma_line.refund_qty:
                                rma_line.received_qty += 1.0
                        else:
                            rma_line_vals.update({'rma_id': rma_without_invoice[0].id})
                            rma_sale_line = self.env['rma.sale.lines'].create(rma_line_vals)
                        return rma_without_invoice[0]
                rma_vals.update({'need_credit_memo': True})
                rma_id = self.env['rma.ret.mer.auth'].with_context(rma_from_verify=True).create(rma_vals)
                rma_line_vals.update({'rma_id': rma_id.id})
                rma_sale_line = self.env['rma.sale.lines'].create(rma_line_vals)
                return rma_id
            else:
                rma_for_sale = self.env['rma.ret.mer.auth'].search([('sale_order_id', '=', picking.sale_id.id), ('state', '=', 'approve'), ('need_credit_memo', '=', False)], limit=1)
                if rma_for_sale:
                    rma_line = rma_for_sale.rma_sale_lines_ids.filtered(lambda r: r.product_id.id == product.id)
                    if rma_line:
                        rma_line.refund_qty += 1.0
                    else:
                        rma_line_vals.update({'rma_id': rma_for_sale.id})
                        rma_sale_line = self.env['rma.sale.lines'].create(rma_line_vals)
                    return rma_for_sale
                rma_vals.update({'need_credit_memo': False})
                rma_id = self.env['rma.ret.mer.auth'].with_context(rma_from_verify=True).create(rma_vals)
                rma_line_vals.update({'rma_id': rma_id.id})
                rma_sale_line = self.env['rma.sale.lines'].create(rma_line_vals)
                return rma_id
                
RMARetVerify()
