# -*- coding: utf-8 -*-

from odoo import api, models

class BatchPickingReport(models.AbstractModel):

    _name = 'report.stock_pick_batch.batch_picking_report'
    _description = 'Batch Picking Report'

    def get_picking_list(self, batch_pick):
        """ Returns list of picking in an order of products in consecutive locations.
        """
        result = {}
        batch_pick_list = []
        search_warehouse = self.env['stock.warehouse'].search([('warehouse_type', '=', 'sub_warehouse')])
        loc = self.env['stock.location']
        for warehouse in search_warehouse:
            loc |= self.env['stock.location'].search([('id', 'child_of', warehouse.lot_stock_id.id)])
        sorted_pick_ids = batch_pick.picking_ids.sorted(key=lambda pick: pick.product_sku)
        for move in sorted_pick_ids.mapped('move_lines'):
            # quants = []
            stock_quants = move.product_id.stock_quant_ids.filtered(lambda q: q.location_id.usage == 'internal' and q.location_id in loc).sorted(key=lambda l: l.quantity, reverse=True)
            stock_quants = stock_quants[:3].sorted(key=lambda l: l.location_id.display_name)
            # for quant in stock_quants:
            #     if quant.location_id.usage == 'internal' and quant.location_id in loc:
            #         quants.append(quant)
            result.setdefault(move.location_id.id, {}).setdefault(move.product_id, []).append({
                'scheduled_date': move.picking_id.scheduled_date,
                'SKU': move.product_id.default_code,
                'sale_id': move.picking_id.sale_id.name,
                'pick_qty': int(move.product_uom_qty),
                'name': move.picking_id.name,
                'location_qty': [(i.location_id.name, int(i.quantity)) for i in stock_quants][:3],
            })
        for r in [list(data.values()) for data in result.values()]:
            batch_pick_list.extend(r)
        batch_pick_list = sum(batch_pick_list, [])
        # batch_pick_list.sort(key=lambda r: r['location_qty'] and r['location_qty'][0][0] or '')
        return batch_pick_list

    def get_intern_picking_list(self, batch_pick):
        loc = self.env['stock.location'].search([('id', 'child_of', batch_pick.picking_type_id.warehouse_id.lot_stock_id.id)])
        batch_pick_dict = {}
        for pick in batch_pick.picking_ids:
            for move in pick.mapped('move_lines'):
                batch_pick_dict.setdefault(pick, []).append({
                                        'SKU': move.product_id.default_code,
                                        'pick_qty': int(move.product_uom_qty),
                                         'name': move.picking_id.name,
                                        'location_qty': [(i.location_id.display_name, int(i.quantity)) for i in
                                 move.product_id.stock_quant_ids if i.location_id.usage == 'internal' and  i.location_id in loc]})
        return batch_pick_dict

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking.batch'].browse(docids)
        return {'doc_ids': docs.ids,
                'doc_model': 'stock.picking.batch',
                'docs': docs,
                'data': data,
                'get_picking_list': self.get_picking_list,
                'get_intern_picking_list': self.get_intern_picking_list,
                }

