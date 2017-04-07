# -*- coding: utf-8 -*-
import logging
import werkzeug
from datetime import datetime

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

PPG = 40 # Products Per Page (20 by default)
PPR = 4  # Products Per Row

class membership_visibility(website_sale):

    @http.route([
        '/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>',
# Ajout de la route Enroll pour acheter un membership
        '/enroll',
        '/prefered'
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
        want_prefered = ("prefered" in request.httprequest.path) and not membership
        
        context['want_membership'] = want_membership
        context['want_prefered'] = want_prefered

        order = request.website.sale_get_order()

        domain = self._get_search_domain(search, category, attrib_values)
              
        cart_member = None
        if order:
            for line in order.order_line:
                if line.product_id.membership == True:
                    cart_member = line.product_id.membership_category_id.id

        if uid != 1:
            # pas admin
            if membership :
                # si membre, récupère l'usager correspondant
                membership_user = pool['res.users'].browse(cr, SUPERUSER_ID, membership, context=context)
                membership_days = abs((datetime.strptime(membership_user.member_lines[0].create_date, '%Y-%m-%d %H:%M:%S') - datetime.now()).days)
                # vérifie si adhésion associé sans kit de démarrage à 49.95 (pour avoir droit au start kit) [80=id de la variante]
                if int(membership_user.member_lines[0].membership_id) == 80 and membership_user.reiva_HasStartKit == False:
                    # Cacul du nombre de jours depuis le début du membership

                    membership_days = abs((datetime.strptime(membership_user.member_lines[0].create_date, '%Y-%m-%d %H:%M:%S') - datetime.now()).days)
                    # Le filtre est = Produit pas membership et 
                    # (pas startkit ou nbr jours startkit < nbr jours membership 
                    domain += [('membership', '=', False),              #produits qui ne sont pas de type membership
                               '|',                                     #ou
                               ('startKit', '=', 0),                    #produits sans délai startkit
                               ('startKit', '>', membership_days)       #produits dont le délai startkit alloué n'est pas expiré 
                               ]
#                    domain += []
                elif int(membership_user.member_lines[0].membership_id) == 93:
                    # Membership autre que celui a 49.95, pas droit au startkit [client privilégié, 93=id de la variante]]
#                     domain += ['&',
#                                ('startKit', '=', 0),
#                                ('|',
#                                     ('membership', '=', False),          #ou
#                                     ('&',
#                                         ('id','=',90),
#                                         ('startKit', '>', membership_days)
#                                     )
#                                 )       #produit membership associé offert aux clients privilégiés exclusivement
#                                ]
                    dont_show = [61,62,63,64,88]   #ajouter 88 - 62 et 64: kits de démarrage 75:adhésion ass ind, 88:adhésion client privilégié
                    if membership_days < 60:
                        dont_show.append(75)
                    else:
                        dont_show.append(90)        #adhésion associé escomptée pour client privilégié
                    domain += [('id','not in',dont_show)]
        
                else:
                    domain += [('membership', '=', False)]
                
            else:
                # pas member
                if not cart_member:
                    # pas produit mbr dans cart
                    if want_membership:
                        # Provient de enroll afficher juste membership cat 1 
                        domain += [('membership_category_id', '=', 1)]
                        domain += [('id', '!=',90)]
                    elif want_prefered:
                        # Provient de preferred n'afficher que member cat 2
                        domain += [('membership_category_id', '=', 2)]
                    else:
                        # provient de shop publique.
                        # pas de membership, ni starttkit
                        domain += [('membership', '=', False)]
                        domain += [('startKit', '=', 0)]
                else:
                    if cart_member == 1:
                        # Si membership dans cart
                        domain += [('startKit', '=', 0)]                  
                        domain += ['|',
                                   ('membership_category_id', '=', 1),
                                   ('membership', '=', False)]
                    else:
                        domain += [('startKit', '=', 0)]                  
                        domain += [('membership', '=', False)]
                        
                        
                        
                    # on fixe manuellement la liste de prix
                        
#                        domain += [('|',('membership', '=', True),[('startKit', '=', True)]
                   
        keep = QueryURL('/shop', category=category and int(category), search=search, attrib=attrib_list)

        if not context.get('pricelist'):
            pricelist = self.get_pricelist()
            context['pricelist'] = int(pricelist)
        else:
            pricelist = pool.get('product.pricelist').browse(cr, uid, context['pricelist'], context)

        product_obj = pool.get('product.template')

        url = "/shop"
        _logger.info("Domain of product is === " + str(domain) )
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
            'want_prefered': want_prefered,
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
        product_startKit = pool.get('product.product').search(cr, uid, ([('startKit', '>', 0), ('id', '=', product_id)]), context=context)

        if product_membership or product_startKit:
            add_qty = 0
        
        request.website.sale_get_order(force_create=1)._cart_update(product_id=int(product_id), add_qty=float(add_qty), set_qty=float(set_qty))

        return request.redirect("/shop/cart")

    
    @http.route(['/shop/confirmation'], type='http', auth="public", website=True)
    def payment_confirmation(self, **post):        
        """ End of checkout process controller. Confirmation is basically seing
        the status of a sale.order. State at this point :

         - should not have any context / session info: clean them
         - take a sale.order id, because we request a sale.order and are not
           session dependant anymore
        """
        cr, uid, context = request.cr, request.uid, request.context

        sale_order_id = request.session.get('sale_last_order_id')

        if sale_order_id:
            order = request.registry['sale.order'].browse(cr, SUPERUSER_ID, sale_order_id, context=context)
            
            for line in order.order_line:
                if line.product_id.startKit > 0:
                    currentPartner = order.partner_id
                    partner_values= { 'reiva_HasStartKit': True}                                        
                    currentPartner.write(partner_values)
                    cart_member = line.product_id.membership_category_id.id
        else:
            return request.redirect('/shop')

        return request.website.render("website_sale.confirmation", {'order': order})



def get_reiva_pricelist():
    cr, uid, context, pool = request.cr, request.uid, request.context, request.registry

    # devrait pouvoir être transféré en paramètre dans l'interface
    # de configuration odoo (2 champs many2one vers pricelist à ajouter dans
    # res_compagnie et ajouter les vues pour les modifier dans l'admin
    pubPriceList = 1
    mbrPriceList = 5
    
    pricelist = pubPriceList
    membership = pool.get('res.users').search(cr, uid, ([('partner_id.membership_state', '=', 'paid'), ('id', '=', uid)]), context=context)
    
    currentPartner = pool.get('res.users').browse(cr, SUPERUSER_ID, uid, context).partner_id
    
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
            if want_membership or cart_member :
                # pas produit membership dans le cart = liste prix public
                pricelist = mbrPriceList
            else:
                # Si membership dans le cart = liste prix membre
                pricelist = pubPriceList
    else:
        # admin 
        pricelist = mbrPriceList
                    
    pricelist_obj = pool['product.pricelist'].browse(cr, SUPERUSER_ID, pricelist, context=context)
    if currentPartner.id != 4 and currentPartner.property_product_pricelist.id != pricelist_obj.id :
        partner_values= { 'property_product_pricelist': pricelist_obj.id}                    
        currentPartner.write (partner_values)
    
    # injection dans cart ???
    if order :  
        order.pricelist_id = pricelist_obj.id

    return pricelist_obj

main.get_pricelist = get_reiva_pricelist