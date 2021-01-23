from odoo import models, fields, api


class EdiConfiguration(models.Model):
    _name = 'edi.configuration'

    name = fields.Char("Name")
    order_list_url = fields.Char("Order List URL")
    order_url = fields.Char("Order URL")
    mode = fields.Selection([('test', 'Testing'), ('production', 'Production')], string="Mode")
    exchange_token_url = fields.Char("Exchange Token URL")
    post_url = fields.Char("Post URL")
    uid = fields.Char("UID")
    password = fields.Char("Password")
    auth_token = fields.Char("Auth Token")
    client_id = fields.Char("Client ID")
