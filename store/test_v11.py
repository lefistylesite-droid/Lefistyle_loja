from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from .models import CustomerProfile, Order, OrderEvent, Category, Product, ProductVariant
from .validators import normalize_cpf
from .forms import RegisterForm
from .manual_orders import resolve_manual_order
from .infinitepay import InfinitePayError

User=get_user_model()

class RegistrationTests(TestCase):
    def details(self):
        return dict(first_name='Cliente Exemplo',cpf='529.982.247-25',email='Cliente@example.test')
    def test_only_three_identity_fields(self):
        self.assertEqual(list(RegisterForm().fields), ['first_name','cpf','email'])
    def test_cpf_validation(self):
        self.assertEqual(normalize_cpf('529.982.247-25'),'52998224725')
        for value in ('11111111111','00000000000','52998224724','123','abc52998224725'):
            with self.assertRaises(ValidationError): normalize_cpf(value)
    def test_registration_email_login_and_cart_preserved(self):
        product=Product.objects.create(category=Category.objects.get(slug='jaquetas'),name='Teste',slug='teste',price=10)
        variant=ProductVariant.objects.create(product=product,sku='CART',size='UN',color='Padrão',stock=2)
        saved_cart={str(variant.pk):1}
        session=self.client.session; session['lefi_cart_v1']=saved_cart;session.save()
        self.assertRedirects(self.client.post(reverse('register'),self.details()),reverse('register_password'))
        self.assertFalse(User.objects.filter(email='cliente@example.test').exists())
        response=self.client.post(reverse('register_password'),{'new_password1':'SenhaCompleta#2026','new_password2':'SenhaCompleta#2026'})
        self.assertEqual(response.status_code,302)
        profile=CustomerProfile.objects.get()
        self.assertEqual(profile.email,'cliente@example.test')
        self.assertEqual(profile.cpf,'52998224725')
        self.assertEqual(self.client.session['lefi_cart_v1'],saved_cart)
        self.client.logout()
        self.assertTrue(self.client.login(username='CLIENTE@EXAMPLE.TEST',password='SenhaCompleta#2026'))
    def test_duplicate_document_blocked_and_database_constraint(self):
        user=User.objects.create_user(username='old',email='old@example.test')
        CustomerProfile.objects.create(user=user,cpf='52998224725',email=user.email)
        self.assertFalse(RegisterForm(self.details()).is_valid())
        other=User.objects.create_user(username='other')
        with self.assertRaises(IntegrityError),transaction.atomic():
            CustomerProfile.objects.create(user=other,cpf='52998224725',email='other@example.test')
    def test_legacy_email_duplicate_blocked(self):
        User.objects.create_user(username='old',email='CLIENTE@example.test')
        self.assertIn('email', RegisterForm(self.details()).errors)
    def test_password_required(self):
        self.client.post(reverse('register'),self.details())
        response=self.client.post(reverse('register_password'),{'new_password1':'123','new_password2':'123'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(CustomerProfile.objects.exists())
    def test_expired_signup_requires_restart(self):
        session=self.client.session;session['signup_details']=self.details();session['signup_time']=1;session.save()
        self.assertRedirects(self.client.get(reverse('register_password')),reverse('register'))
    def test_legacy_username_login(self):
        User.objects.create_user(username='antigo',password='Seguro#2026')
        self.assertTrue(self.client.login(username='antigo',password='Seguro#2026'))
    def test_csrf_registration(self):
        from django.test import Client
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('register'),self.details()).status_code,403)

@override_settings(LEFI_SHIPPING_FLAT='12.00',LEFI_CHECKOUT_ENABLED=False,LEFI_ACCEPT_MANUAL_ORDERS=True,LEFI_EMAIL_ENABLED=False)
class OrderAndDashboardTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='buyer',email='buyer@example.test',password='Seguro#2026')
        self.admin=User.objects.create_superuser(username='admin',email='admin@example.test',password='Seguro#2026')
        self.product=Product.objects.create(category=Category.objects.get(slug='jaquetas'),name='Teste',slug='teste',price=100)
        self.variant=ProductVariant.objects.create(product=self.product,sku='SKU-1',size='UN',color='Padrão',stock=4)
        self.client.force_login(self.user)
    def checkout_data(self):
        self.client.post(reverse('cart_add'),{'variant_id':self.variant.pk,'quantity':1})
        self.client.get(reverse('checkout'))
        return dict(nonce=self.client.session['lefi_checkout_nonce'],full_name='Cliente Teste',email='buyer@example.test',phone='11999999999',postal_code='01001000',street='Rua Teste',number='1',neighborhood='Centro',city='São Paulo',state='SP')
    def order(self):
        self.client.post(reverse('checkout'),self.checkout_data())
        return Order.objects.get()
    def test_manual_saved_without_gateway_and_visible_in_admin(self):
        with patch('store.views.create_payment_link') as gateway:
            order=self.order(); gateway.assert_not_called()
        self.assertEqual(order.total,Decimal('112.00'))
        self.assertEqual(order.payment_status,'manual_pending')
        self.assertEqual(order.status,'pending_payment')
        self.assertEqual(order.shipping_state,'SP')
        self.assertEqual(order.items.count(),1)
        self.assertEqual(order.history.filter(event='order.created').count(),1)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('dashboard')),'Cliente Teste')
        self.assertContains(self.client.get(reverse('admin:store_order_changelist')),'buyer')
    def test_double_post_does_not_duplicate(self):
        data=self.checkout_data()
        self.client.post(reverse('checkout'),data)
        self.client.post(reverse('checkout'),data)
        self.assertEqual(Order.objects.count(),1)
        self.variant.refresh_from_db();self.assertEqual(self.variant.stock,3)
    @override_settings(LEFI_CHECKOUT_ENABLED=True,INFINITEPAY_API_KEY='fake',INFINITEPAY_TAG='fake')
    def test_gateway_failure_preserves_order_event_and_clears_cart(self):
        data=self.checkout_data()
        with patch('store.views.create_payment_link',side_effect=InfinitePayError('timeout')):
            response=self.client.post(reverse('checkout'),data)
        self.assertEqual(response.status_code,302)
        order=Order.objects.get(); self.assertEqual(order.payment_status,'link_creation_uncertain')
        self.assertTrue(order.history.filter(event='order.created').exists())
        self.assertNotIn('lefi_cart_v1',self.client.session)
    @override_settings(LEFI_SHIPPING_FLAT='')
    def test_unknown_shipping_does_not_create_free_order(self):
        self.client.post(reverse('cart_add'),{'variant_id':self.variant.pk,'quantity':1})
        self.client.post(reverse('checkout'),{})
        self.assertFalse(Order.objects.exists())
    def test_invalid_nonce_and_form(self):
        data=self.checkout_data();data['nonce']='wrong'
        self.assertEqual(self.client.post(reverse('checkout'),data).status_code,302)
        self.assertFalse(Order.objects.exists())
        data['nonce']=self.client.session['lefi_checkout_nonce'];data['state']='XX'
        self.assertEqual(self.client.post(reverse('checkout'),data).status_code,200)
        self.assertFalse(Order.objects.exists())
    def test_manual_payment_and_cancel_are_audited_and_not_repeatable(self):
        order=self.order()
        with self.assertRaises(ValueError): resolve_manual_order(order.pk,self.user,'paid','PIX123')
        with self.assertRaises(ValueError): resolve_manual_order(order.pk,self.admin,'paid','')
        resolve_manual_order(order.pk,self.admin,'paid','PIX123')
        order.refresh_from_db();self.assertEqual(order.payment_status,'manual_paid')
        self.assertEqual(order.history.get(event='order.paid').actor,self.admin)
        with self.assertRaises(ValueError): resolve_manual_order(order.pk,self.admin,'cancelled')
    def test_manual_cancel_returns_stock_once(self):
        order=self.order();resolve_manual_order(order.pk,self.admin,'cancelled')
        self.variant.refresh_from_db();self.assertEqual(self.variant.stock,4)
        with self.assertRaises(ValueError): resolve_manual_order(order.pk,self.admin,'cancelled')
        self.variant.refresh_from_db();self.assertEqual(self.variant.stock,4)
    def test_filters_and_metrics_exclude_unpaid_from_revenue(self):
        order=self.order();self.client.force_login(self.admin)
        response=self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['paid_order_amount'],0)
        resolve_manual_order(order.pk,self.admin,'paid','PIX123')
        response=self.client.get(reverse('dashboard'),{'period':'all','q':str(order.pk)})
        self.assertEqual(response.context['paid_order_amount'],Decimal('112'))
        self.assertEqual(response.context['paid_count'],1)
        self.assertEqual(self.client.get(reverse('dashboard'),{'status':'shipped'}).context['orders_count'],0)
    def test_staff_without_order_permission_cannot_read_finances(self):
        self.user.is_staff=True;self.user.save()
        self.assertEqual(self.client.get(reverse('dashboard')).status_code,403)
    def test_customer_cannot_read_dashboard_or_others_order(self):
        order=self.order()
        other=User.objects.create_user(username='other');self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code,302)
        self.assertEqual(self.client.get(reverse('order_detail',args=[order.pk])).status_code,404)
    def test_alias_exists(self):
        self.assertEqual(self.client.get(reverse('payment_checkout')).status_code,302)
    def test_large_numeric_search_is_safe(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('dashboard'),{'q':'9'*100}).status_code,200)
    def test_manual_admin_confirmation_form(self):
        order=self.order();self.client.force_login(self.admin)
        url=reverse('admin:store_order_changelist')
        payload={'action':'confirm_manual_payment','_selected_action':[str(order.pk)]}
        self.assertContains(self.client.post(url,payload),'Referência do recebimento')
        self.client.post(url,{**payload,'confirmation':'CONFIRMAR','reference':'PIX123'})
        order.refresh_from_db();self.assertEqual(order.payment_status,'manual_paid')
    def test_admin_dashboard_entry(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('admin:index')),'Abrir painel de gestão')
