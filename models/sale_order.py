# -*- coding: utf-8 -*-

import logging
from openerp import models, fields, api, _
from openerp import SUPERUSER_ID
from dns.rdataclass import is_metaclass

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _membership_unset(self, cr, uid, ids, idss, context=None):
        sale_obj = self.pool['sale.order.line']
        line_ids = sale_obj.search(cr, uid, [('order_id', '=', ids), ('id', 'in', idss), ('product_id.membership', '=', True)], context=context)
        sale_obj.unlink(cr, uid, line_ids, context=context)

    def _startKit_unset(self, cr, uid, ids, idss, context=None):
        sale_obj = self.pool['sale.order.line']
        line_ids = sale_obj.search(cr, uid, [('order_id', '=', ids), ('id', 'in', idss), ('product_id.startKit', '>', 0)], context=context)
        sale_obj.unlink(cr, uid, line_ids, context=context)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_membership = fields.Boolean(string='Membership')
    is_startkit = fields.Boolean(string='Start kit')

    def create(self, cr, uid, values, context=None):

        created_prod = self.pool.get('product.product').browse(cr, uid, values.get('product_id'), context=context)
        
        if created_prod.membership:
            if values.get('is_delivery') != True:
                ids = values.get('order_id')
                idss = self.search(cr, uid, [('order_id', '=', ids), ('product_id.membership', '=', True)], context=context)
                delete_mem = self.pool.get('sale.order')._membership_unset(cr, uid, ids, idss, context=context)
        else:
            if created_prod.startKit > 0:
                ids = values.get('order_id')
                idss = self.search(cr, uid, [('order_id', '=', ids), ('product_id.startKit', '>', 0)], context=context)
                delete_kit = self.pool.get('sale.order')._startKit_unset(cr, uid, ids, idss, context=context)            
        return super(SaleOrderLine, self).create(cr, uid, values, context)
