# -*- coding: utf-8 -*-
import logging
import werkzeug

from openerp import SUPERUSER_ID
from openerp import http
from openerp import tools
from openerp.http import request
from openerp.tools.translate import _
from openerp.addons.website.models.website import slug
from openerp.addons.web.controllers.main import login_redirect
from openerp.addons.website_sale.controllers import main
from openerp.addons.website_sale.controllers.main import website_sale
from openerp.addons.website_sale.controllers.main import QueryURL
from openerp.addons.website_sale.controllers.main import table_compute

_logger = logging.getLogger(__name__)

PPG = 20 # Products Per Page
PPR = 4  # Products Per Row

class membership_visibility(website_sale):

    @http.route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
# Ajout de la route Enroll pour acheter un membership
        '/enroll',
        
    ], type='http', auth="public", website=True)

    def membership_product(self, page=0, category=None, search='', website=True, **post):
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [map(int, v.split("-")) for v in attrib_list if v]
        attrib_set = set([v[1] for v in attrib_values])
# Vérification de la présence de enroll dans l'url (devrais aussi vérifier le 
# contenu d'une autre varaible du post (want_membership)        
        membership = pool.get('res.users').search(cr, uid, ([('partner_id.membership_state', '=', 'paid'), ('id', '=', uid)]), context=context)
        want_membership = ("enroll" in request.httprequest.path) and not membership
        context['want_membership'] = want_membership
        order = request.website.sale_get_order()

        domain = self._get_search_domain(search, category, attrib_values)

        cart_member = None
        if order:
            for line in order.order_line:
                if line.product_id.membership == True:
                    cart_member = True

        if uid != 1:
            # pas admin
            if membership :
                # si membre, affiche pas membership
                domain += [('membership', '=', False)]
                # vérfier si affichage startkit
            else:
                # pas member
                if not cart_member:
                    # pas produit mbr dans cart
                    if want_membership:
                        # Provient de enroll afficher juste membership 
                        domain += [('membership', '=', True)]
                    else:
                        # provient de shop publique.
                        # pas de membership, ni starttkit
                        domain += [('membership', '=', False)]
                        domain += [('startKit', '=', False)]
                else:
                    # Si membership dans cart
                    domain += [('startKit', '=', False)]
                    # on fixe manuellement la liste de prix
#                    context['pricelist'] = 5 
                        
#                        domain += [('|',('membership', '=', True),[('startKit', '=', True)]
                   
        #Membre
#        if uid != 1 and (membership or not want_membership):
#            domain += [('membership', '=', False)]

        keep = QueryURL('/shop', category=category and int(category), search=search, attrib=attrib_list)

        if not context.get('pricelist'):
            pricelist = self.get_pricelist()
            context['pricelist'] = int(pricelist)
        else:
            pricelist = pool.get('product.pricelist').browse(cr, uid, context['pricelist'], context)

        product_obj = pool.get('product.template')

        url = "/shop"
        product_count = product_obj.search_count(cr, uid, domain, context=context)
        if search:
            post["search"] = search
        if category:
            category = pool['product.public.category'].browse(cr, uid, int(category), context=context)
            url = "/shop/category/%s" % slug(category)
        if attrib_list:
            post['attrib'] = attrib_list
        pager = request.website.pager(url=url, total=product_count, page=page, step=PPG, scope=7, url_args=post)
        product_ids = product_obj.search(cr, uid, domain, limit=PPG, offset=pager['offset'], order=self._get_search_order(post), context=context)
        products = product_obj.browse(cr, uid, product_ids, context=context)

        style_obj = pool['product.style']
        style_ids = style_obj.search(cr, uid, [], context=context)
        styles = style_obj.browse(cr, uid, style_ids, context=context)

        category_obj = pool['product.public.category']
        category_ids = category_obj.search(cr, uid, [('parent_id', '=', False)], context=context)
        categs = category_obj.browse(cr, uid, category_ids, context=context)

        attributes_obj = request.registry['product.attribute']
        attributes_ids = attributes_obj.search(cr, uid, [], context=context)
        attributes = attributes_obj.browse(cr, uid, attributes_ids, context=context)

        from_currency = pool.get('product.price.type')._get_field_currency(cr, uid, 'list_price', context)
        to_currency = pricelist.currency_id
        compute_currency = lambda price: pool['res.currency']._compute(cr, uid, from_currency, to_currency, price, context=context)

        values = {
            'want_membership': want_membership,
            'search': search,
            'category': category,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'pager': pager,
            'pricelist': pricelist,
            'products': products,
            'bins': table_compute().process(products),
            'rows': PPR,
            'styles': styles,
            'categories': categs,
            'attributes': attributes,
            'compute_currency': compute_currency,
            'keep': keep,
            'style_in_product': lambda style, product: style.id in [s.id for s in product.website_style_ids],
            'attrib_encode': lambda attribs: werkzeug.url_encode([('attrib',i) for i in attribs]),
        }

        return request.website.render("website_sale.products", values)

    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry
        product_membership = pool.get('product.product').search(cr, uid, ([('membership', '=', True), ('id', '=', product_id)]), context=context)

        if product_membership:
            add_qty = 0

        request.website.sale_get_order(force_create=1)._cart_update(product_id=int(product_id), add_qty=float(add_qty), set_qty=float(set_qty))
        return request.redirect("/shop/cart")


def get_reiva_pricelist():
    cr, uid, context, pool = request.cr, request.uid, request.context, request.registry

    # devrait pouvoir être transféré en paramètre dans l'interface
    # de configuration odoo (2 champs many2one vers pricelist à ajouter dans
    # res_compagnie et ajouter les vues pour les modifier dans l'admin
    pubPriceList = 1
    mbrPriceList = 5
    
    membership = pool.get('res.users').search(cr, uid, ([('partner_id.membership_state', '=', 'paid'), ('id', '=', uid)]), context=context)

    want_membership = context.get('want_membership')

    
    order = request.website.sale_get_order()

    cart_member = False

    if order:
        for line in order.order_line:
            if line.product_id.membership == True:
                cart_member = True

    if uid != 1:
        # pas admin
        if membership :
            # Membre, liste de prix membre = liste prix membre

            pricelist = mbrPriceList

            # Mais on devrait utiliser la liste prix assigné aux partenaires
            # en commentant la ligne du haut et dé-commentant le bloc ci-bas
            
            #partner = pool['res.users'].browse(cr, SUPERUSER_ID, uid, context=context).partner_id
            #pricelist = partner.property_product_pricelist
            #if not pricelist:
            #    _logger.error('Fail to find pricelist for partner "%s" (id %s)', partner.name, partner.id)        else:
        
        else:    
            # pas membre
            if want_membership or cart_member:
                # pas produit membership dans le cart = liste prix public
                pricelist = mbrPriceList
            else:
                # Si membership dans le cart = liste prix membre
                pricelist = pubPriceList
                
    pricelist_obj = pool['product.pricelist'].browse(cr, SUPERUSER_ID, pricelist, context=context)
    # injection dans cart ???
    if order :  
        order.pricelist_id = pricelist_obj.id

    return pricelist_obj

main.get_pricelist = get_reiva_pricelist