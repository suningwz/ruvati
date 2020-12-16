# See LICENSE file for full copyright and licensing details.

{
    "name": "RMA - Return Merchandise Authorization Return Exchange "
            "Management",
    "version": "13.0.1.0.0",
    "author": "Serpent Consulting Services Pvt. Ltd.",
    "summary": '''Return merchandise authorization
    RMA Return goods
    Exchange goods
    Credit notes
    Replace item
    Goods Return Refund, 
    Exchange, 
    Payback
    ''',
    "website": "http://www.serpentcs.com",
    "description": '''Return merchandise authorization module helps
    you to manage with product returns and exchanges.
    RMA Return goods
    Exchange goods
    Credit notes
    Replace item
    Goods Return Refund, 
    Exchange, 
    Payback''',
    "license": 'LGPL-3',
    "depends": ['sale_management', 'stock', 'purchase'],
    "category": "Warehouse",
    "sequence": 1,
    'data': [
            'security/security.xml',
            'security/ir.model.access.csv',
            'views/res_company.xml',
            'views/sequence.xml',
            'views/rma_view.xml',
            'views/rma_verification_view.xml',
            'views/account_move_view.xml',
            'views/sale_view.xml',
            'report/report_mer_auth_rma.xml',
            'report/rma_report_mer_auth_reg.xml',
            'data/rma_demo.xml',
    ],
    'images': ['static/description/rma.png'],
    'installable': True,
    'price': 53,
    'currency': 'EUR',
    'pre_init_hook': 'pre_init_hook',
}
