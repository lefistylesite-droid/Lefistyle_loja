from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from .photo_forms import ProductPhotoForm
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from decimal import Decimal
from .models import Category, Product, ProductVariant

class StoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category=Category.objects.get(slug='jaquetas')
        cls.product=Product.objects.create(category=category,name='Jaqueta Teste',slug='jaqueta-teste',price=Decimal('149.90'),image_url='')
        cls.variant=ProductVariant.objects.create(product=cls.product,sku='TEST-M',size='M',color='Mocha',stock=5)

    def test_home_and_detail(self):
        self.assertContains(self.client.get(reverse('home')),'Jaqueta Teste')
        self.assertContains(self.client.get(reverse('product_detail',args=['jaqueta-teste'])),'Jaqueta Teste')

    def test_cart_has_real_price_and_persists_through_login(self):
        result=self.client.post(reverse('cart_add'),{'variant_id':self.variant.pk,'quantity':2})
        self.assertEqual(result.status_code,302)
        self.assertContains(self.client.get(reverse('cart')),'299,80')
        user=User.objects.create_user(username='teste',password='SuaSenhaBemLonga!82')
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('cart')),'Jaqueta Teste')

    def test_out_of_stock_rejected(self):
        self.client.post(reverse('cart_add'),{'variant_id':self.variant.pk,'quantity':6})
        self.assertContains(self.client.get(reverse('cart')),'pronto para receber sua próxima escolha.')

    def test_invalid_cart_quantity_rejected(self):
        result=self.client.post(reverse('cart_add'),{'variant_id':self.variant.pk,'quantity':0})
        self.assertEqual(result.status_code,400)

    def test_checkout_requires_login(self):
        self.assertEqual(self.client.get(reverse('checkout')).status_code, 302)

    def test_dashboard_requires_staff(self):
        response=self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code,302)
        user=User.objects.create_user(username='admin',password='UmaSenhaBemForte!83',is_staff=True)
        from django.contrib.auth.models import Permission
        user.user_permissions.add(Permission.objects.get(codename='view_order'))
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('dashboard')),'Gestão da')

    def test_health(self):
        self.assertEqual(self.client.get(reverse('health')).content,b'ok')


from unittest.mock import patch
import json
from .models import Order
from .infinitepay import InfinitePayError, cents

class CheckoutInfinitePayTests(StoreTests):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.buyer=User.objects.create_user(username='clientelefi',email='cliente@example.com',password='SenhaSeguraZavia!23')

    def add_cart(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk,'quantity':'1'})

    def valid_form(self):
        self.client.get(reverse('checkout'))
        return {'nonce':self.client.session['lefi_checkout_nonce'],
                'full_name':'Cliente de Teste','email':'cliente@example.com',
                'phone':'11998887777','postal_code':'01001000','street':'Rua de Teste',
                'number':'12','neighborhood':'Centro','city':'São Paulo','state':'SP'}

    def create_order(self):
        self.add_cart()
        with patch('store.views.create_payment_link',return_value=('LEFI-1','https://checkout.infinitepay.com.br/fake')):
            self.client.post(reverse('checkout'), self.valid_form())
        return Order.objects.get(user=self.buyer)

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_pending_and_reservation(self):
        order=self.create_order()
        self.assertEqual(order.total,Decimal('161.90'))
        self.assertEqual(order.status,'pending_payment')
        self.assertEqual(order.gateway_preference_id,'LEFI-1')
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_return_requires_authenticated_confirmation(self):
        order=self.create_order()
        self.client.get(reverse('payment_return',args=[order.pk])+'?paid=true')
        order.refresh_from_db()
        self.assertEqual(order.status,'pending_payment')
        query=f'?order_nsu=LEFI-{order.pk}&slug=slug123&transaction_nsu=tx123'
        with patch('store.infinitepay.payment_check',return_value={'success':True,'paid':True,'amount':16190}):
            self.client.get(reverse('payment_return',args=[order.pk])+query)
        order.refresh_from_db()
        self.assertEqual(order.status,'paid')
        with patch('store.infinitepay.payment_check',return_value={'success':True,'paid':True,'amount':16190}):
            self.client.get(reverse('payment_return',args=[order.pk])+query)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_webhook_rechecks_amount(self):
        order=self.create_order()
        body={'order_nsu':f'LEFI-{order.pk}','invoice_slug':'slug123','transaction_nsu':'tx123'}
        with patch('store.infinitepay.payment_check',return_value={'success':True,'paid':True,'amount':100}):
            self.client.post(reverse('payment_webhook'),json.dumps(body),content_type='application/json')
        order.refresh_from_db()
        self.assertEqual(order.status,'pending_payment')
        with patch('store.infinitepay.payment_check',return_value={'success':True,'paid':True,'amount':16190}):
            self.client.post(reverse('payment_webhook'),json.dumps(body),content_type='application/json')
        order.refresh_from_db()
        self.assertEqual(order.status,'paid')

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_demo_cannot_checkout(self):
        self.add_cart()
        checkout_data=self.valid_form()
        self.product.is_demo=True
        self.product.save(update_fields=['is_demo'])
        self.client.post(reverse('checkout'),checkout_data)
        self.assertFalse(Order.objects.filter(user=self.buyer).exists())

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_uncertain_link_retains_stock_for_manual_review(self):
        self.add_cart()
        with patch('store.views.create_payment_link',side_effect=InfinitePayError('simulada')):
            self.client.post(reverse('checkout'),self.valid_form())
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)
        order = Order.objects.get(user=self.buyer)
        self.assertEqual(order.status,'pending_payment')
        self.assertEqual(order.payment_status,'link_creation_uncertain')

    def test_cents(self):
        self.assertEqual(cents(Decimal('149.90')),14990)


from datetime import timedelta
from django.utils import timezone
from .infinitepay import release_abandoned_after_manual_confirmation, create_payment_link

class ReservationReviewTests(CheckoutInfinitePayTests):
    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_expiring_link_sends_valid_until(self):
        self.add_cart()
        with patch('store.infinitepay._call', return_value={'url':'https://checkout.infinitepay.com.br/fake'}) as mocked:
            self.client.post(reverse('checkout'), self.valid_form())
        order = Order.objects.get(user=self.buyer)
        self.assertIsNotNone(order.payment_expires_at)
        args = mocked.call_args.args
        self.assertEqual(args[0],'/links')
        self.assertEqual(args[1]['options']['valid_until'],order.payment_expires_at.isoformat())

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_expired_does_not_release_automatically(self):
        order=self.create_order()
        Order.objects.filter(pk=order.pk).update(payment_expires_at=timezone.now()-timedelta(days=2))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)
        order.refresh_from_db()
        self.assertTrue(order.stock_reserved)

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_manual_release_requires_age_confirmation_and_is_idempotent(self):
        order=self.create_order()
        admin=User.objects.create_user(username='verificador',password='SenhaForte123!',is_staff=True)
        with self.assertRaises(ValueError):
            release_abandoned_after_manual_confirmation(order.pk,staff_user=admin,provider_checked=True)
        Order.objects.filter(pk=order.pk).update(payment_expires_at=timezone.now()-timedelta(days=2))
        with self.assertRaises(ValueError):
            release_abandoned_after_manual_confirmation(order.pk,staff_user=admin,provider_checked=False)
        self.assertTrue(release_abandoned_after_manual_confirmation(order.pk,staff_user=admin,provider_checked=True))
        self.assertFalse(release_abandoned_after_manual_confirmation(order.pk,staff_user=admin,provider_checked=True))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,5)
        order.refresh_from_db()
        self.assertEqual(order.status,'cancelled')

    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_no_manual_release_of_paid_order(self):
        order=self.create_order()
        Order.objects.filter(pk=order.pk).update(payment_expires_at=timezone.now()-timedelta(days=2))
        with patch('store.infinitepay.payment_check',return_value={'success':True,'paid':True,'amount':16190}):
            from .infinitepay import verify_and_apply
            self.assertTrue(verify_and_apply(order.pk,'tx-123','slug-123'))
        admin=User.objects.create_user(username='verificador',password='SenhaForte123!',is_staff=True)
        self.assertFalse(release_abandoned_after_manual_confirmation(order.pk,staff_user=admin,provider_checked=True))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)


class AdminProductManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.get(slug='camisetas')
        cls.admin_user = User.objects.create_superuser(username='gestor', email='gestor@example.com', password='SenhaBemSegura#2026')
        cls.staff_user = User.objects.create_user(username='auxiliar', password='SenhaBemSegura#2026', is_staff=True)
        cls.demo = Product.objects.create(category=cls.category, name='Produto fictício', slug='produto-ficticio', price=Decimal('80.00'), is_demo=True, active=True)
        cls.real = Product.objects.create(category=cls.category, name='Produto real', slug='produto-real', price=Decimal('90.00'), is_demo=False, active=True)
        cls.variant = ProductVariant.objects.create(product=cls.demo, sku='FICT-P', size='P', color='Nude', stock=3)

    def test_panel_archive_demos_keeps_real_product(self):
        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('dashboard'), {'action':'archive_demos'})
        self.assertEqual(resp.status_code, 302)
        self.demo.refresh_from_db()
        self.real.refresh_from_db()
        self.assertFalse(self.demo.active)
        self.assertTrue(self.real.active)
        self.assertFalse(self.demo.featured)
        self.assertNotContains(self.client.get(reverse('home')), 'Produto fictício')
        self.assertContains(self.client.get(reverse('home')), 'Produto real')

    def test_panel_blocked_without_permission(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse('dashboard'), {'action':'archive_demos'})
        self.assertEqual(response.status_code, 403)
        self.demo.refresh_from_db()
        self.assertTrue(self.demo.active)

    def test_delete_demo_without_orders(self):
        self.client.force_login(self.admin_user)
        url=reverse('admin:store_product_changelist')
        response=self.client.post(url,{'action':'remove_demos_safely','_selected_action':[str(self.demo.pk)]})
        self.assertContains(response,'EXCLUIR FICTICIOS')
        response=self.client.post(url,{'action':'remove_demos_safely','_selected_action':[str(self.demo.pk)],'delete_demos_confirm':'EXCLUIR FICTICIOS','post':'yes'})
        self.assertIn(response.status_code,(200,302))
        self.assertFalse(Product.objects.filter(pk=self.demo.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.real.pk).exists())

    def test_delete_demo_with_historical_order_keeps_order_not_product(self):
        self.client.force_login(self.admin_user)
        from .models import OrderItem
        from django.urls import reverse
        order = Order.objects.create(user=self.admin_user, customer_name='Comprador anterior',
                                     contact_email='cliente@example.com', address='SP')
        item = OrderItem.objects.create(order=order, variant=self.variant,
                                        description='Produto de teste', sku=self.variant.sku,
                                        quantity=1, unit_price=Decimal('80.00'))
        url=reverse('admin:store_product_changelist')
        response=self.client.post(url,{'action':'remove_demos_safely',
            '_selected_action':[str(self.demo.pk)],
            'delete_demos_confirm':'EXCLUIR FICTICIOS','post':'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.demo.pk).exists())
        item.refresh_from_db()
        self.assertIsNone(item.variant_id)
        self.assertEqual(item.sku, 'FICT-P')

    def setUp(self):
        self.category = self.__class__.category
        self.product = Product.objects.create(category=self.category,name='Jaqueta LEFI Real',slug='jaqueta-pet-real',price=Decimal('139.90'))

    def uploaded_photo(self, color):
        buff = BytesIO()
        Image.new('RGB', (250, 350), color).save(buff, format='JPEG')
        return SimpleUploadedFile('foto.jpg',buff.getvalue(),content_type='image/jpeg')

    def test_multiple_real_photos_display_and_persist_in_db(self):
        for i, color in enumerate(('pink', 'beige')):
            form = ProductPhotoForm(data={'position':i,'alt':f'Foto {i+1}'}, files={'upload':self.uploaded_photo(color)})
            self.assertTrue(form.is_valid(),form.errors)
            photo = form.save(commit=False)
            photo.product=self.product
            photo.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.gallery.count(), 2)
        response = self.client.get(reverse('product_detail',args=[self.product.slug]))
        self.assertContains(response, '/fotos/produto/', count=5)  # capa, 2 botões e 2 miniaturas
        image = self.product.gallery.first()
        self.assertTrue(image.has_upload)
        result = self.client.get(reverse('product_image', args=[image.pk]))
        self.assertEqual(result['Content-Type'], 'image/webp')
        self.assertTrue(result.content.startswith(b'RIFF'))

    def test_no_photo_upload_is_rejected_when_creating_gallery_row(self):
        form = ProductPhotoForm(data={'position': 1,'alt':'sem foto'})
        self.assertFalse(form.is_valid())

    def test_empty_catalog_has_no_fake_products_or_fake_model_photos(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response,'Jaqueta LEFI Real')
        Product.objects.all().delete()
        response = self.client.get(reverse('home'))
        self.assertContains(response,'A próxima história começa aqui.')
        self.assertNotContains(response,'Jaqueta LEFI Real')
        self.assertNotContains(response,'conjunto-mocha.webp')


class FreteEFaviconTests(StoreTests):
    @override_settings(LEFI_SHIPPING_FLAT='15.00', LEFI_CHECKOUT_ENABLED=False)
    def test_carrinho_mostra_frete_fixo_mesmo_com_checkout_desligado(self):
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk, 'quantity':1})
        response = self.client.get(reverse('cart'))
        self.assertContains(response, 'frete fixo')
        self.assertContains(response, '15,00')
        self.assertContains(response, '164,90')
        self.assertNotContains(response, 'Em configuração')

    @override_settings(LEFI_SHIPPING_FLAT='15.00', LEFI_CHECKOUT_ENABLED=False, LEFI_ACCEPT_MANUAL_ORDERS=False)
    def test_checkout_bloqueado_nao_confunde_frete_com_pagamento(self):
        user = User.objects.create_user(username='cliente-frete', password='SenhaSegura123!')
        self.client.force_login(user)
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk, 'quantity':1})
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Frete do pedido')
        self.assertContains(response, '15,00')
        self.assertContains(response, 'Pagamento temporariamente indisponível')
        self.assertNotContains(response, 'política de frete')

    @override_settings(LEFI_SHIPPING_FLAT='15,00', LEFI_CHECKOUT_ENABLED=False)
    def test_frete_aceita_virgula_decimal_brasileira(self):
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk, 'quantity':1})
        self.assertContains(self.client.get(reverse('cart')), '164,90')

    @override_settings(LEFI_SHIPPING_FLAT='0', LEFI_CHECKOUT_ENABLED=False)
    def test_frete_zero_aparece_gratis(self):
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk, 'quantity':1})
        self.assertContains(self.client.get(reverse('cart')), 'Grátis')

    @override_settings(LEFI_SHIPPING_FLAT='', LEFI_CHECKOUT_ENABLED=False)
    def test_frete_ausente_informa_realidade(self):
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk, 'quantity':1})
        self.assertContains(self.client.get(reverse('cart')), 'A calcular')

    def test_logomarca_em_favicon_da_aba(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'rel="icon"')
        self.assertContains(response, 'rel="apple-touch-icon"')


class CarrinhoSincronizadoTests(StoreTests):
    """Regressão: catálogo limpo não pode deixar badge 1 no cabeçalho."""

    def test_produto_excluido_limpa_contador_e_sessao(self):
        self.client.post(reverse('cart_add'), {'variant_id': self.variant.pk, 'quantity': 1})
        self.assertContains(self.client.get(reverse('home')), 'badge-count')
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {str(self.variant.pk): 1})
        Product.objects.filter(pk=self.product.pk).delete()
        pagina = self.client.get(reverse('home'))
        self.assertContains(pagina, '<span class="badge-count">0</span>', html=True)
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {})
        self.assertContains(self.client.get(reverse('cart')), 'Seu carrinho está pronto para receber sua próxima escolha.')

    def test_produto_desativado_sai_da_sessao(self):
        self.client.post(reverse('cart_add'), {'variant_id': self.variant.pk, 'quantity': 2})
        Product.objects.filter(pk=self.product.pk).update(active=False)
        self.assertContains(self.client.get(reverse('cart')), 'Seu carrinho está pronto para receber sua próxima escolha.')
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {})
        self.assertContains(self.client.get(reverse('home')), '<span class="badge-count">0</span>', html=True)

    def test_variacao_excluida_sai_mas_preserva_itens_validos(self):
        new_product = Product.objects.create(category=self.product.category, name='Produto novo',
                                             slug='produto-novo', price=Decimal('49.90'))
        new_variant = ProductVariant.objects.create(product=new_product, sku='NOVO-P',
                                                    size='P', color='Bege', stock=3)
        self.client.post(reverse('cart_add'), {'variant_id':self.variant.pk,'quantity':1})
        self.client.post(reverse('cart_add'), {'variant_id':new_variant.pk,'quantity':2})
        ProductVariant.objects.filter(pk=self.variant.pk).delete()
        pagina = self.client.get(reverse('cart'))
        self.assertNotContains(pagina, 'Jaqueta Teste')
        self.assertContains(pagina, 'Produto novo')
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {str(new_variant.pk):2})
        self.assertContains(pagina, '<span class="badge-count">2</span>', html=True)

    def test_variacao_desativada_limpa_carrinho(self):
        self.client.post(reverse('cart_add'), {'variant_id': self.variant.pk, 'quantity': 1})
        ProductVariant.objects.filter(pk=self.variant.pk).update(active=False)
        self.assertContains(self.client.get(reverse('home')), '<span class="badge-count">0</span>', html=True)
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {})

    def test_quantidades_e_ids_invalidos_na_sessao_nao_quebram_loja(self):
        session = self.client.session
        session['lefi_cart_v1'] = {'invalido': 8, '-123': 1, '0': 5,
                                    str(self.variant.pk): 'valor-errado', '9999999999999999999999999':1}
        session.save()
        pagina = self.client.get(reverse('home'))
        self.assertContains(pagina, '<span class="badge-count">0</span>', html=True)
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {})

    def test_item_valido_continua_no_carrinho(self):
        self.client.post(reverse('cart_add'), {'variant_id': self.variant.pk, 'quantity': 2})
        self.assertContains(self.client.get(reverse('cart')), '299,80')
        self.assertContains(self.client.get(reverse('home')), '<span class="badge-count">2</span>', html=True)
        self.assertEqual(self.client.session.get('lefi_cart_v1'), {str(self.variant.pk): 2})


# v1.7: textos comerciais e pagina informativa, sem modificar o checkout.
from django.test import override_settings
from django.urls import reverse

class V17CommercialPresentationTests(StoreTests):
    def test_home_uses_customer_copy(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'INFORMAÇÃO TRANSPARENTE')
        self.assertContains(response, 'Como comprar')
        self.assertNotContains(response, 'Checkout InfinitePay quando habilitado')

    def test_how_to_buy_page_is_public(self):
        response = self.client.get(reverse('como_comprar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ao continuar, você será direcionado ao checkout da InfinitePay')

    @override_settings(LEFI_CHECKOUT_ENABLED=False)
    def test_checkout_paused_has_no_testing_copy(self):
        from django.contrib.auth import get_user_model
        user=get_user_model().objects.create_user(username='cliente_pausa_v17', password='SenhaForteTest!232')
        self.client.force_login(user)
        self.client.post(reverse('cart_add'), {'variant_id': self.variant.pk, 'quantity': '1'})
        response=self.client.get(reverse('checkout'))
        self.assertContains(response, 'Pagamento temporariamente indisponível')
        self.assertNotContains(response, 'testes de segurança')


class CommercialInformationTests(TestCase):
    def test_commercial_pages_are_public(self):
        from django.urls import reverse
        for name in ('politica_entrega', 'trocas_devolucoes', 'politica_privacidade', 'atendimento'):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_footer_links_to_actual_pages(self):
        response = self.client.get(reverse('home'))
        for name in ('politica_entrega', 'trocas_devolucoes', 'politica_privacidade', 'atendimento'):
            self.assertContains(response, reverse(name))

    def test_contact_info_can_be_set_via_database(self):
        from .models import StoreInformation
        data=StoreInformation.objects.create(
            legal_name='Empresa Exemplo LTDA', contact_email='contato@example.org',
            contact_phone='5511999999999', service_hours='Segunda a sexta',
            delivery_estimate='Prazo informado antes do pagamento'
        )
        response=self.client.get(reverse('atendimento'))
        self.assertContains(response, 'https://wa.me/5511999999999')
        self.assertContains(response, 'contato@example.org')
        self.assertContains(response, 'Empresa Exemplo LTDA')
        self.assertContains(self.client.get(reverse('politica_entrega')), data.delivery_estimate)

    def test_admin_store_info_is_singleton(self):
        from .models import StoreInformation
        from .admin import StoreInformationAdmin
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        obj=StoreInformation.objects.create()
        self.assertFalse(StoreInformationAdmin(StoreInformation, AdminSite()).has_delete_permission(RequestFactory().get('/admin/'), obj))
        # Não adicionar uma segunda configuração comercial.
        self.assertEqual(StoreInformation.objects.count(), 1)

    def test_no_store_data_is_invented_by_default(self):
        response=self.client.get(reverse('atendimento'))
        self.assertContains(response, 'Os canais de contato ainda não foram publicados')
        self.assertNotContains(response, 'contato@lefi.com')

# Regressão v1.9: conta, solicitações, atualização financeira e e-mails.
from .models import OrderEvent, EmailNotification
from .order_workflow import request_cancellation, transition_order

class WorkflowV19Tests(CheckoutInfinitePayTests):
    @override_settings(LEFI_EMAIL_ENABLED=False,LEFI_CHECKOUT_ENABLED=True,
                       INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_cliente_consegue_sair_com_post_csrf(self):
        self.client.force_login(self.buyer)
        page = self.client.get(reverse('profile'))
        self.assertContains(page, 'Sair da minha conta')
        self.assertContains(page, 'action="' + reverse('logout') + '"')
        self.assertEqual(self.client.get(reverse('logout')).status_code,405)
        self.assertEqual(self.client.post(reverse('logout')).status_code,302)
        self.assertEqual(self.client.get(reverse('profile')).status_code,302)

    @override_settings(LEFI_EMAIL_ENABLED=False,LEFI_CHECKOUT_ENABLED=True,
                       INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_cliente_pode_solicitar_cancelamento_sem_fingir_estorno(self):
        order=self.create_order()
        self.assertContains(self.client.get(reverse('order_detail',args=[order.pk])), 'SOLICITAR CANCELAMENTO')
        response=self.client.post(reverse('order_cancellation_request',args=[order.pk]),{'reason':'Compra de teste'})
        self.assertEqual(response.status_code,302)
        order.refresh_from_db()
        self.assertEqual(order.status,'pending_payment')
        self.assertIsNotNone(order.cancellation_requested_at)
        self.assertEqual(order.payment_status,'awaiting_payment')
        self.assertEqual(OrderEvent.objects.filter(order=order,event='order.cancellation_requested').count(),1)
        self.client.post(reverse('order_cancellation_request',args=[order.pk]),{})
        self.assertEqual(OrderEvent.objects.filter(order=order,event='order.cancellation_requested').count(),1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)  # Reserva mantida até confirmação externa.

    @override_settings(LEFI_EMAIL_ENABLED=False,LEFI_CHECKOUT_ENABLED=True,
                       INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_cliente_nao_vê_pedido_alheio_nem_solicita_cancelamento(self):
        order=self.create_order()
        outra=User.objects.create_user(username='outro123',password='SenhaMuitoBoa123!')
        self.client.force_login(outra)
        self.assertEqual(self.client.get(reverse('order_detail',args=[order.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('order_cancellation_request',args=[order.pk])).status_code,404)
        order.refresh_from_db()
        self.assertIsNone(order.cancellation_requested_at)

    @override_settings(LEFI_EMAIL_ENABLED=False,LEFI_CHECKOUT_ENABLED=True,
                       INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_confirmacao_do_pagamento_e_idempotente_gera_um_email_pendente(self):
        order=self.create_order()
        payload={'success':True,'paid':True,'amount':16190}
        from .infinitepay import verify_and_apply
        with patch('store.infinitepay.payment_check',return_value=payload):
            self.assertTrue(verify_and_apply(order.pk,'tx123','slug123'))
            self.assertTrue(verify_and_apply(order.pk,'tx123','slug123'))
        order.refresh_from_db()
        self.assertEqual(order.status,'paid')
        self.assertEqual(OrderEvent.objects.filter(order=order,event='order.paid').count(),1)
        self.assertEqual(EmailNotification.objects.filter(order=order,event='order.paid').count(),1)
        self.assertEqual(EmailNotification.objects.get(order=order,event='order.paid').status,'pending')

    @override_settings(LEFI_EMAIL_ENABLED=False,LEFI_CHECKOUT_ENABLED=True,
                       INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_admin_transicoes_validas_e_estorno_dependem_de_provedor(self):
        order=self.create_order()
        admin=User.objects.create_superuser(username='admteste',email='admteste@example.com',password='SenhaGrande!234')
        Order.objects.filter(pk=order.pk).update(status='paid',gateway_payment_id='tx123',payment_status='paid')
        self.assertTrue(transition_order(order.pk,'preparing',actor=admin))
        with self.assertRaises(ValueError):
            transition_order(order.pk,'shipped',actor=admin)
        Order.objects.filter(pk=order.pk).update(tracking_carrier='Transportadora de teste',tracking_code='COD123')
        self.assertTrue(transition_order(order.pk,'shipped',actor=admin))
        self.assertTrue(transition_order(order.pk,'delivered',actor=admin))
        with self.assertRaises(ValueError):
            transition_order(order.pk,'refunded',actor=admin,provider_verified=False)
        self.assertTrue(transition_order(order.pk,'refunded',actor=admin,provider_verified=True))
        order.refresh_from_db()
        self.assertEqual(order.status,'refunded')
        self.assertEqual(order.payment_status,'refunded')
        self.assertIsNotNone(order.refund_confirmed_at)
        self.assertEqual(EmailNotification.objects.filter(order=order,event='order.refunded').count(),1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock,4)  # Não repõe mercadoria automaticamente após estorno.

    @override_settings(LEFI_EMAIL_ENABLED=False,LEFI_CHECKOUT_ENABLED=True,
                       INFINITEPAY_API_KEY='inchk_fake',INFINITEPAY_TAG='minha-loja',LEFI_SHIPPING_FLAT='12.00')
    def test_contas_pendentes_que_solicitam_cancelamento_nao_recebem_email_falso(self):
        order=self.create_order()
        request_cancellation(order,self.buyer)
        self.assertFalse(EmailNotification.objects.filter(order=order,event='order.cancelled').exists())


class LEFIIsolationTests(TestCase):
    def test_lefi_categories_without_fake_products(self):
        self.assertTrue(Category.objects.filter(slug='jaquetas').exists())
        self.assertTrue(Category.objects.filter(slug='calcas').exists())
        self.assertFalse(Product.objects.exists())
        resp=self.client.get(reverse('home'))
        self.assertContains(resp, 'LEFI')
        self.assertContains(resp, 'JAQUETAS')
        self.assertContains(resp, 'A próxima história começa aqui.')

    def test_separate_payment_order_reference(self):
        from .infinitepay import order_reference
        self.assertEqual(order_reference(123), 'LEFI-123')
        self.assertNotIn('ZAVIA', order_reference(123))

    def test_demo_products_not_shown_to_customers(self):
        cat=Category.objects.get(slug='camisetas')
        demo=Product.objects.create(category=cat,name='Imagem ilustrativa',slug='imagem-ilustrativa',price=Decimal('9.90'),is_demo=True)
        self.assertNotContains(self.client.get(reverse('home')), 'Imagem ilustrativa')
        self.assertEqual(self.client.get(reverse('product_detail', args=[demo.slug])).status_code,404)
