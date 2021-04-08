# -*- coding: utf-8 -*-

from odoo import models, fields,api
from datetime import datetime, date
import pytz


class ShipmentReport(models.Model):
    _name = 'shipment.report'
    _description = "PO Shipment"


    def po_shipment_records(self, data):
        from_date = data.get('from_date')
        to_date = str(data.get('to_date')) + " 23:59:59"
        move_line_ids_list = []
        domain = [('date_planned','>=',from_date),('date_planned','<=',to_date),('state','in',['purchase','transit','done'])]
        if data.get('partner_id',False):
            domain.extend([('partner_id','=',data.get('partner_id'))])
        po_lines = self.env['purchase.order.line'].search(domain)
        po_lines = po_lines.sorted(key=lambda line:(line.partner_id.display_name,line.order_id.name,line.date_planned))
        for line in po_lines:
            move_line_ids = line.move_ids and line.move_ids.filtered(lambda rec:rec.state not in ['cancel'] and rec.picking_type_id.code!='outgoing') or []
            if move_line_ids:
                move_line_ids_list.append({'po_line' : line,'move_lines' : move_line_ids})
        return move_line_ids_list


    def po_late_shipment_records(self, data):
        move_line_ids_list = []
        from_date = data.get('from_date')
        to_date = str(data.get('to_date')) + " 23:59:59"
        domain = [('date_planned','>=',from_date),('date_planned','<=',to_date),('state','in',['purchase','transit','done'])]
        if data.get('partner_id',False):
            domain.extend([('partner_id','=',data.get('partner_id'))])
        po_line_ids = self.env['purchase.order.line'].search(domain)
        po_line_ids = po_line_ids.sorted(key=lambda line:(line.partner_id.display_name,line.order_id.name,line.date_planned))
        for line in po_line_ids:
            move_line_ids = line.move_ids and line.move_ids.filtered(lambda rec:rec.state not in ['cancel'] and rec.picking_type_id.code!='outgoing' and (rec.date.strftime('%Y-%m-%d') > line.date_planned.strftime('%Y-%m-%d') or rec.state=='assigned') ) or []
            
            if move_line_ids:
                move_line_ids_list.append({'po_line' : line,'move_lines' : move_line_ids})
        return move_line_ids_list


class PoShipment(models.AbstractModel):
    _name = 'report.container_management.print_po_shipment_report'
    _description = "PO Shipment Report"

    @api.model
    def _get_report_values(self, docids, data):
        report_lines = []
        if data.get('report') == 'shipment':
            report_lines = self.env['shipment.report'].po_shipment_records(data)
            data.update({'heading' : 'PO Shipment Report'})
        else:
            report_lines = self.env['shipment.report'].po_late_shipment_records(data)
            data.update({'heading':'PO Late Shipment Report'})
        docargs = {
            'doc_ids': self._ids,
            'data': data,
            'company_id' : self.env.user.company_id,
            'report_lines' : report_lines
        }
        return docargs


