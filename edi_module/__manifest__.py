{
    'name': 'EDI Integration Base',
    'category': 'sale',
    'summary': 'Edi integration base module',
    'version': '1.0',
    'description': """
EDI Integration
=============


This Module provides the basic configuration.

        """,
    'author': 'Confianz Global',
    'depends': ['sale'],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'data/edi_order_cron.xml',
        'views/edi_configuration_view.xml',
        'views/partner_view.xml',
        'views/product_view.xml',
        'views/sale_view.xml',
        'views/account_view.xml',
        'views/dealer_pricelist.xml',
    ],
    'qweb': [],
    'installable': True,
}
