from odoo import models, fields, api
import requests
import json


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_id = fields.Char("Customer ID")
    state = fields.Selection(selection_add=[('to_review', 'To Review')])
    edi_sale_id = fields.Char('Edi ID')
    edi_order = fields.Boolean("Edi Order", default=False, copy=False)
    pro_number = fields.Char("PRO Number")
    doc_date = fields.Date("Doc Date")
    doc_due_date = fields.Date("Doc Due Date")
    bill_of_lading_number = fields.Char("Bill Of Lading")
    transportation_method_code = fields.Char("Transportation Code")
    ship_via_description = fields.Selection([('UPS', 'UPS'), ('Fedex', 'Fedex')], string="Ship Via")
    order_shipment_status = fields.Selection([('P', 'P')], string="Shipment Status")

    def order_to_review(self):
        if all(line.price_unit == line.sale_approved_price for line in self.order_line) and self.state == 'to_review':
            self.write({'state': 'draft'})
        elif any(line.price_unit != line.sale_approved_price for line in self.order_line) and self.state == 'draft':
            self.write({'state': 'to_review'})

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if self.edi_order:
            self.order_to_review()
        return res

    def process_order_data(self, order_data):
        data = order_data.get('PullSalesOrdersOutResult', {})
        if data:
            ship_to_code = data.get('CardCode', False)
            doc_date = data.get('DocDate', False)
            doc_due_date = data.get('DocDueDate', False)
            item_lines = data.get('DocumentLines', False)
            partner_id = self.env['res.partner'].search([('customer_id', '=', ship_to_code)], limit=1)
            if not partner_id:
                return False
            line_list = []
            for line in item_lines:
                name = line.get('ItemDescription', False)
                item_code = line.get('ItemCode', False)
                price = line.get('Price', False)
                quantity = line.get('Quantity', False)
                ship_date = line.get('ShipDate', False)
                unit_price = 0
                if price and quantity:
                    unit_price = float(price)
                edi_record = self.env['edi.customer'].search([('sku_product_id', '=', item_code),
                                                              ('customer_id', '=', ship_to_code)], limit=1)
                if not edi_record:
                    return False

                line_list.append((0, 0, {
                    'name': name,
                    'product_id': edi_record.product_id.id,
                    'sale_approved_price': edi_record.sale_approved_price,
                    'ship_date': ship_date,
                    'price_unit': unit_price,
                    'product_uom_qty': quantity

                }))
            order_id = self.env['sale.order'].create({
                'partner_id': partner_id.id,
                'customer_id': ship_to_code,
                'doc_date': doc_date,
                'doc_due_date': doc_due_date,
                'edi_order': True,
                'order_line': line_list
            })

            return order_id

        return False

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        return res

    def _cron_pull_edi_orders(self):
        configuration = self.env['edi.configuration'].search([], limit=1)
        exchange_token_url = configuration.exchange_token_url
        uid = configuration.uid
        password = configuration.password
        auth_token = configuration.auth_token
        client_id = configuration.client_id
        response = requests.get(exchange_token_url,
                                headers={'UID': uid, 'PWORD': password,
                                         'AUTHTOKEN': auth_token,
                                         'CLIENTID': client_id})
        content = json.loads(response.content)
        access_token = content['ExchangeTokenResult']['access_token']
        if configuration.mode == 'production':
            production_list_url = configuration.order_list_url
            order_url = configuration.order_url
            order_list_response = requests.get(production_list_url,
                                    headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
            if order_list_response.content:
                list_data = json.loads(order_list_response.content)
                order_list = list_data.get('PullSalesOrdersOutListResult', [])
                for order_id in order_list:
                    order_id_url = order_url + str(order_id)
                    order_response = requests.get(order_id_url, headers={"ACCESSTOKEN": access_token, "CLIENTID": "39FC0B24-4544-475F-A5EE-B1DDB8CDA6DD"})
                    order_data = json.loads(order_response.content)
                    order_id = self.process_order_data(order_data)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sale_approved_price = fields.Float("Approved Price")
    ship_date = fields.Date("Ship Date")

    @api.onchange('product_id')
    def _onchange_product_id_edi(self):
        for rec in self:
            edi_customer = rec.product_id.edi_customer_ids.filtered(lambda l:l.customer_id == rec.order_id.customer_id)
            rec.sale_approved_price = edi_customer and edi_customer[0].sale_approved_price

    @api.model
    def create(self, vals):
        res = super(SaleOrderLine, self).create(vals)
        if res.order_id.edi_order:
            res.order_id.order_to_review()

        return res
