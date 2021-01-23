# -*- coding: utf-8 -*-

from odoo import models, fields,api


class ContainerConfig(models.TransientModel):
    _name = 'container.config'
    _inherit ='res.config.settings'

    freight_account_id = fields.Many2one('account.account', string="Freight Account")
    customs_clearence_account_id = fields.Many2one('account.account', string="Customs Clearence Account")

##    @api.multi
#    def set_freight_account_id_defaults(self):
#        return self.env['ir.values'].sudo().set_default('container.config', 'freight_account_id', self.freight_account_id.id)

# #    @api.multi
#    def set_customs_clearence_account_id_defaults(self):
#        return self.env['ir.values'].sudo().set_default('container.config', 'customs_clearence_account_id', self.customs_clearence_account_id.id)

#    def get_default_params(self, fields):
#        res = {}
#        res['freight_account_id'] = self.env['ir.values'].get_default('container.config', 'freight_account_id')
#        res['customs_clearence_account_id'] = self.env['ir.values'].get_default('container.config', 'customs_clearence_account_id')
#        return res



#    @api.model
#    def get_values(self):
#        res = super(ContainerConfig, self).get_values()
#        freight_account = customs_clearence_account = self.env['account.account']
#        irconfigparam = self.env['ir.config_parameter'].sudo()
#        freight_account_id = irconfigparam.get_param('freight_account_id')
#        if freight_account_id:
#            freight_account = self.env['account.account'].browse(int(freight_account_id))
#            print ('xxxxxxx', freight_account)
#        print ('gggggggggggg', freight_account_id)
#        customs_clearence_account_id = irconfigparam.get_param('customs_clearence_account_id')
#        if customs_clearence_account_id:
#            customs_clearence_account = self.env['account.account'].browse(int(customs_clearence_account_id))
#        print ('eeeeeeeeeeee', customs_clearence_account_id)
#        res.update(freight_account_id=freight_account.id if freight_account else False,
#                   customs_clearence_account_id=customs_clearence_account.id if customs_clearence_account else False,
#                   )
#        return res

    @api.model
    def get_values(self):
        res = super(ContainerConfig, self).get_values()
        irconfigparam = self.env['ir.config_parameter'].sudo()
        freight_account_id = irconfigparam.get_param('freight_account_id')
        
        customs_clearence_account_id = irconfigparam.get_param('customs_clearence_account_id')
        
        res.update(freight_account_id=int(freight_account_id),
                   customs_clearence_account_id=int(customs_clearence_account_id),
                   )
        return res

#    @api.multi
    def set_values(self):
        super(ContainerConfig, self).set_values()
        irconfigparam = self.env['ir.config_parameter'].sudo()
        print ('hhhhhhhhhhhhhhh')
        
        irconfigparam.set_param("freight_account_id", self.freight_account_id and self.freight_account_id.id or '')
        irconfigparam.set_param("customs_clearence_account_id", self.customs_clearence_account_id and self.customs_clearence_account_id.id or '')

ContainerConfig()



