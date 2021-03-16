{
    'name': 'Process Bulk Operations',
    'category': 'Sales',
    'summary': 'To process bulk operations at once',
    'version': '1.0',
    'description': """
To process bulk operations at once

        """,
    'author': 'Confianz Global',
    'depends': ['stock','sale'],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'data/process_bulk_operations.xml',

    ],
    'qweb': [],
    'installable': True,
}
