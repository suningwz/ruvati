# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import base64
import xlsxwriter
import io
import time
from datetime import datetime, date

class ShipmentReportWizard(models.TransientModel):
    _name = "po.shipment.report"
    _description="PO Shipment Report"

    report = fields.Selection([('shipment','PO Shipment Report'),('late_shipment','PO Late Shipment Report')], default="shipment", string="Report")
    file_type = fields.Selection([('excel','Excel'),('pdf','PDF')], default="excel", string="File Type")
    partner_id = fields.Many2one('res.partner', string="Factory")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")


    def generate_excel_report(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Shipment Report')
        worksheet.set_paper(1) #change paper size to letter
        header_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter', 'border': 1})

        line_style = workbook.add_format({'font_name': 'Arial', 'font_size': 9, 'bold':False})
        sub_head_style = workbook.add_format({'font_name': 'Arial', 'font_size': 10, 'bold': True, 'border': 1})
        date_style = workbook.add_format({'font_name': 'Arial', 'font_size': 9, 'bold': False ,'align': 'center',})
        row = 0
        col = 0
        worksheet.merge_range('A1:G2', "%s (%s through %s)" % (self.report=='shipment' and 'PO Shipment Report' or 'PO Late Shipment Report', self.from_date.strftime('%B %d,%Y'), self.to_date.strftime('%B %d,%Y')), header_style)

        row += 3
        data = {'from_date': self.from_date, 'to_date': self.to_date, 'partner_id' : self.partner_id and self.partner_id.id or False}
        if self.report == 'shipment':
            lines = self.env['shipment.report'].po_shipment_records(data)
        else:
            lines = self.env['shipment.report'].po_late_shipment_records(data)
        widths = [30,10,40,15,12,22,15]
        headers =["Product","PO Name","Factory Name","Total Order Qty","Shipped Qty","Expected Ship Date(ETD)", 'Actual Ship Date']
        for col in range(0, len(widths)):
            worksheet.set_column(col, col, widths[col])
            worksheet.write(row, col, headers[col], sub_head_style)
        row += 1
        col = 0
        for line in lines:
            purchase_line = line.get('po_line')
            shipped_qty = 0
            date_planned = purchase_line.date_planned.strftime('%m/%d/%Y')
            worksheet.write(row, col, purchase_line.product_id.display_name, line_style)
            worksheet.write(row, col+1, purchase_line.order_id.name, line_style)
            worksheet.write(row, col+2, purchase_line.partner_id.display_name, line_style)
            worksheet.write(row, col+3, purchase_line.product_qty, line_style)
            worksheet.write(row, col+5, date_planned, date_style)
            for mline in line.get('move_lines'):
                worksheet.write(row, col+5, date_planned, date_style)
                if mline.state!='done':
                    worksheet.write(row, col+3, mline.product_uom_qty, line_style)
                    date = "Not shipped Yet"
                    shipped_qty = 0
                else:
                    date = mline.date.strftime('%m/%d/%Y')
                    shipped_qty = mline.product_uom_qty
                worksheet.write(row, col+4, shipped_qty, line_style)
                worksheet.write(row, col+6, date, line_style)
                row+=1
        workbook.close()
        report_export_id = self.env['po.shipment.excel'].create({'data': base64.encodestring(output.getvalue()), 'name': 'po_shipment_report' + datetime.now().strftime("%Y_%m_%d") + '.xlsx'})
        return report_export_id


    def print_report(self):
        if self.file_type == 'excel':
            report_export_id = self.generate_excel_report()
            form_id = self.env.ref('container_management.view_shipment_report_excel').id

            return {
                'name':_("PO Shipment Report"),
                'views': [[form_id, 'form']],
                'res_model': 'po.shipment.excel',
                'res_id':report_export_id.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        else:
            data = {'from_date' : self.from_date,'to_date': self.to_date,'partner_id' : self.partner_id and self.partner_id.id or False,'report':self.report}
            return self.env.ref('container_management.po_shipment_report').report_action(self,data=data)


