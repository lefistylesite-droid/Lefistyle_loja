"""Regressões da Central de Pedidos LEFI 1.2.
Executar: python manage.py test store.test_v11 store.test_operations_v12
"""
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Category, Product, ProductVariant, Order, CustomerProfile, StoreInformation
from .manual_orders import resolve_manual_order

User=get_user_model()


@override_settings(LEFI_SHIPPING_FLAT='12.00', LEFI_CHECKOUT_ENABLED=False,
                   LEFI_ACCEPT_MANUAL_ORDERS=True, LEFI_EMAIL_ENABLED=False)
class OperationsCenterTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='buyer', password='SenhaCompleta#2026',
                           email='buyer@example.test', first_name='Cliente')
        self.admin = User.objects.create_superuser(username='manager', password='SenhaCompleta#2026',
                            email='admin@example.test')
        CustomerProfile.objects.create(user=self.customer,cpf='52998224725',email=self.customer.email)
        category,_ = Category.objects.get_or_create(slug='jaquetas',defaults={'name':'Jaquetas'})
        product=Product.objects.create(category=category, name='Jaqueta Premium',slug='jaqueta-premium',price=Decimal('45.00'))
        self.variant=ProductVariant.objects.create(product=product,sku='FRALDA-P',size='P',color='Pacote 12',stock=20)
        self.client.force_login(self.customer)

    def make_order(self):
        self.client.post(reverse('cart_add'),{'variant_id':self.variant.pk,'quantity':2})
        self.client.get(reverse('checkout'))
        nonce=self.client.session['lefi_checkout_nonce']
        response=self.client.post(reverse('checkout'),{
            'nonce':nonce,'full_name':'Tutor Exemplo','email':self.customer.email,
            'phone':'11999887766','postal_code':'01001000','street':'Rua das Flores',
            'number':'42','complement':'Apto 2','neighborhood':'Centro','city':'São Paulo',
            'state':'SP','reference':'Portaria principal',
        })
        self.assertEqual(response.status_code,302)
        return Order.objects.latest('pk')

    def test_checkout_writes_all_delivery_fields_without_losing_legacy_address(self):
        order=self.make_order()
        self.assertEqual(order.total,Decimal('102.00'))
        self.assertEqual(order.payment_status,'manual_pending')
        self.assertEqual(order.contact_phone,'11999887766')
        self.assertEqual(order.shipping_postal_code,'01001000')
        self.assertEqual(order.shipping_street,'Rua das Flores')
        self.assertEqual(order.shipping_number,'42')
        self.assertEqual(order.shipping_complement,'Apto 2')
        self.assertEqual(order.shipping_neighborhood,'Centro')
        self.assertEqual(order.shipping_reference,'Portaria principal')
        self.assertIn('Rua das Flores',order.address)
        self.assertEqual(order.item_count,2)
        self.assertEqual(order.items.first().subtotal,Decimal('90.00'))

    def test_admin_can_see_complete_order_and_search_cpf(self):
        order=self.make_order();self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('operations_orders'),{'period':'all','q':'529.982.247-25'}),'Tutor Exemplo')
        response=self.client.get(reverse('operations_order_detail',args=[order.pk]))
        for info in ('529.982.247-25','11999887766','Rua das Flores','01001000','Portaria principal','FRALDA-P'):
            self.assertContains(response,info)

    def test_normal_customer_cannot_view_or_modify_admin_data(self):
        order=self.make_order()
        self.assertEqual(self.client.get(reverse('operations_orders')).status_code,302)
        self.assertEqual(self.client.get(reverse('operations_order_detail',args=[order.pk])).status_code,302)
        self.assertEqual(self.client.post(reverse('operations_order_update',args=[order.pk]),{'action':'transition','next_status':'preparing'}).status_code,302)
        order.refresh_from_db();self.assertEqual(order.status,'pending_payment')

    def test_staff_requires_permissions_for_order_and_sensitive_cpf(self):
        order=self.make_order()
        staff=User.objects.create_user(username='operator',password='SenhaCompleta#2026',is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('operations_orders')).status_code,403)
        staff.user_permissions.add(Permission.objects.get(codename='view_order',content_type__app_label='store'))
        self.assertContains(self.client.get(reverse('operations_order_detail',args=[order.pk])),'Não disponível para este perfil')
        self.assertEqual(self.client.post(reverse('operations_order_update',args=[order.pk]),{'action':'notes','notes':'x'}).status_code,403)
        staff.user_permissions.add(Permission.objects.get(codename='view_customerprofile',content_type__app_label='store'))
        self.assertContains(self.client.get(reverse('operations_order_detail',args=[order.pk])),'529.982.247-25')

    def test_cannot_ship_or_pay_pending_from_operations(self):
        order=self.make_order();self.client.force_login(self.admin)
        url=reverse('operations_order_update',args=[order.pk])
        self.client.post(url,{'action':'transition','next_status':'shipped'})
        self.client.post(url,{'action':'transition','next_status':'paid'})
        order.refresh_from_db()
        self.assertEqual(order.status,'pending_payment')
        self.assertEqual(order.payment_status,'manual_pending')

    def test_shipping_notes_and_full_operational_flow_audited(self):
        order=self.make_order();resolve_manual_order(order.pk,self.admin,'paid','MANUAL-123')
        self.client.force_login(self.admin)
        update_url=reverse('operations_order_update',args=[order.pk])
        self.client.post(update_url,{'action':'transition','next_status':'preparing'})
        self.client.post(update_url,{'action':'transition','next_status':'ready_to_ship'})
        eta=(date.today()+timedelta(days=7)).isoformat()
        self.client.post(update_url,{
            'action':'shipping','tracking_carrier':'Correios','tracking_code':'AB123456789BR',
            'tracking_url':'https://www.correios.com.br/','estimated_delivery':eta,
        })
        self.client.post(update_url,{'action':'notes','notes':'Separar pacote P com cuidado'})
        order.refresh_from_db();self.assertEqual(order.status,'ready_to_ship')
        self.assertEqual(order.tracking_code,'AB123456789BR')
        self.assertTrue(order.history.filter(event='shipping.updated',actor=self.admin).exists())
        self.assertTrue(order.history.filter(event='order.ready_to_ship',actor=self.admin).exists())
        self.assertEqual(self.client.get(reverse('dashboard')).context['paid_order_amount'],Decimal('102.00'))
        self.client.post(update_url,{'action':'transition','next_status':'shipped'})
        self.client.post(update_url,{'action':'transition','next_status':'delivered'})
        order.refresh_from_db();self.assertEqual(order.status,'delivered')
        self.assertIsNotNone(order.shipped_at)
        self.assertIsNotNone(order.delivered_at)

    def test_shipment_rejects_insecure_tracking_url(self):
        order=self.make_order();self.client.force_login(self.admin)
        url=reverse('operations_order_update',args=[order.pk])
        self.client.post(url,{'action':'shipping','tracking_url':'http://example.test/rastrear'})
        order.refresh_from_db();self.assertEqual(order.tracking_url,'')
        self.assertFalse(order.history.filter(event='shipping.updated').exists())

    def test_legacy_order_displays_original_address(self):
        order=self.make_order()
        Order.objects.filter(pk=order.pk).update(shipping_street='',shipping_number='',contact_phone='')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('operations_order_detail',args=[order.pk])),'Pedido anterior à captura de endereço estruturado')
        self.assertContains(self.client.get(reverse('operations_order_detail',args=[order.pk])),'Telefone: 11999887766')

    def test_home_is_independent_of_marketplace_claims(self):
        response=self.client.get(reverse('home'))
        self.assertContains(response,'Da rua para a arte.')
        self.assertNotContains(response,'maiores vendedores')
        StoreInformation.objects.create(shopee_url='https://shopee.com.br/exemplo-lefi')
        response=self.client.get(reverse('home'))
        self.assertNotContains(response,'maiores vendedores')
        self.assertNotContains(response,'Loja oficial na Shopee')
