
from odoo import models, _, fields


class BulkProcess(models.Model):
    _name = 'bulk.process'
    
    def _cron_process_bulk_operations(self):
        self.set_package_dimensions()
        
    def set_package_dimensions(self):
        pickings = self.env['stock.picking']
        pick_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'sub_warehouse')], limit=1)
        if pick_warehouse:
            pickings = self.env['stock.picking'].search([('picking_type_id', '=', pick_warehouse.pick_type_id.id)])
        if pickings:
            move_lines = pickings.mapped('move_line_ids')
            for line in move_lines:
                if line.result_package_id:
                    line.result_package_id.write({
                        'shipping_weight': line.product_id.weight,
                        'length': line.product_id.length,
                        'width': line.product_id.width,
                        'height': line.product_id.height,
                    })
                    product_package = self.env['product.packaging'].search([('name', '=', line.result_package_id.name)], limit=1)
                    if product_package:
                        product_package.write({
                            'length': line.product_id.length,
                            'width': line.product_id.width,
                            'height': line.product_id.height,
                        })
                    else:
                        packaging_id = self.env['product.packaging'].create({
                            'name': line.result_package_id.name,
                            'height': line.product_id.height,
                            'width': line.product_id.width,
                            'length': line.product_id.length
                        })
                        line.result_package_id.packaging_id = packaging_id.id

BulkProcess()
