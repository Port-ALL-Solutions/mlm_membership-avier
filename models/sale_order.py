# -*- coding: utf-8 -*-

import logging
from openerp import models, fields, api, _
from openerp import SUPERUSER_ID

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _membership_unset(self, cr, uid, ids, idss, context=None):
        sale_obj = self.pool['sale.order.line']
        line_ids = sale_obj.search(cr, uid, [('order_id', '=', ids), ('id', 'in', idss), ('product_id.membership', '=', True)], context=context)
        sale_obj.unlink(cr, uid, line_ids, context=context)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_membership = fields.Boolean(string='Membership')

    def create(self, cr, uid, values, context=None):
        created_prod = self.pool.get('product.product').browse(cr, uid, values.get('product_id'), context=context)
        #_logger.info('00000000000000000 %s', created_prod)
        if created_prod.membership:
            if values.get('is_delivery') != True:
                ids = values.get('order_id')
                idss = self.search(cr, uid, [('order_id', '=', ids), ('product_id.membership', '=', True)], context=context)
                delete_mem = self.pool.get('sale.order')._membership_unset(cr, uid, ids, idss, context=context)

                return super(SaleOrderLine, self).create(cr, uid, values, context)
        else:
            return super(SaleOrderLine, self).create(cr, uid, values, context)
