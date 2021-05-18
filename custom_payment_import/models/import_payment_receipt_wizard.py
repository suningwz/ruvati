import base64
import binascii
import csv
import io
import tempfile

import xlrd

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round

_FILE_TYPE = [
    ('xlsx', 'Excel'),
    ('csv', 'CSV')]


class ImportPaymentReceiptWizard(models.TransientModel):
    _name = 'import.payment.receipt.wizard'
    _description = 'Import Payment Receipt Wizard'

    import_option = fields.Selection(_FILE_TYPE, 'File Type')
    file_content = fields.Binary(string='File Content')
    file_name = fields.Char()
    check_number = fields.Char(string="Check Number")
    partner_id = fields.Many2one('res.partner', string="Customer")

    def create_payment(self, vals):
        """ General payment vals creation

        :param vals: file data
        :return: list of general payment vals
        :rtype: list of dict
        """

        payment_list_vals=[]
        journal_id = self.env['account.journal'].search([('is_payment_journal', '=', True)], limit=1)
        invoices = self.env['account.move']
        if not journal_id:
            raise UserError("Choose appropriate payment journal!")
        payment_method_id = journal_id.inbound_payment_method_ids.filtered(lambda x: x.code == 'check_printing')
        if not payment_method_id:
            raise UserError("Choose appropriate payment method!")
        for i_data in vals:
            data = dict(i_data)
            order = self.env['sale.order'].search([('client_order_ref', '=', data['PO Number/Text'].split('.')[0]), ('partner_id', '=', self.partner_id.id)], limit=1)
            if not order:
                raise UserError("No sale order for the corresponding Customer PO Number: %s" % data['PO Number/Text'].split('.')[0])
            if len(order.invoice_ids) > 1:
                invoices = order.invoice_ids.filtered(lambda r: r.name == data['Invoice Number'])
            else:
                invoices = order.invoice_ids
            if invoices:
                if invoices.type == 'out_invoice':
                    payment_vals = {
                        'journal_id': journal_id.id,
                        'payment_method_id': payment_method_id.id,
                        'communication': self.check_number,
                        'invoice_ids': [(6, 0, invoices.ids)],
                        'payment_type': 'inbound',
                        'amount': float(data['Net Amount']),
                        'partner_id': invoices.partner_id.id,
                        'partner_type': 'customer',
                    }
                if invoices.type == 'out_refund':
                    payment_vals.update({'payment_type': 'outbound'})

                payment_dif = float_round(
                                float(data['GrossAmount']) - float(data['Adjmt Amount']),
                                precision_digits=2)
                write_of_account = self.env.user.company_id.writeoff_account_id
                if not write_of_account:
                    raise UserError("Missing required account, is to be set inside the company.")
                payment_vals['amount'] = payment_dif
                if data['Adjmt Amount']:
                    payment_vals['payment_difference'] = float(data['GrossAmount']) - payment_dif
                    payment_vals['writeoff_account_id'] = write_of_account.id
                    payment_vals['payment_difference_handling'] = 'reconcile'
                payment_list_vals.append(payment_vals)

        return payment_list_vals

    def payment_receipt_wizard_save(self):

        if self.import_option == 'csv':
            try:
                csv_data = base64.b64decode(self.file_content)
                data_file = io.StringIO(csv_data.decode("utf-8"))
                data_file.seek(0)
                file_reader = []
                csv_reader = csv.DictReader(data_file, delimiter=',')
                file_reader.extend(csv_reader)
            except:
                raise UserError("Invalid file!")
            create_payment_vals = self.create_payment(file_reader)
            if create_payment_vals:
                for vals in create_payment_vals:
                    payment = self.env['account.payment'].create(vals)
                    payment.post()

        elif self.import_option == 'xlsx':
            try:
                fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                fp.write(binascii.a2b_base64(self.file_content))
                fp.seek(0)
                workbook = xlrd.open_workbook(fp.name)
                sheet = workbook.sheet_by_index(0)
            except:
                raise UserError("Invalid file!")

            keys = ['Invoice Number', 'Inv Date', 'PO Number/Text', 'GrossAmount', 'Adjmt Amount', 'Net Amount']
            lines = []
            for row_no in range(1, sheet.nrows):
                lines.append(zip(keys, list(
                    map(lambda row: isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value),
                        sheet.row(row_no)))))
            create_payment_vals = self.create_payment(lines)
            if create_payment_vals:
                for vals in create_payment_vals:
                    payment = self.env['account.payment'].create(vals)
                    payment.post()


ImportPaymentReceiptWizard()
