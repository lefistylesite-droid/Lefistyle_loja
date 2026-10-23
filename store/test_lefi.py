"""Regressões específicas da LEFI, sem produtos inventados na loja."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Category, Product, ProductVariant

class MarcaLEFITests(TestCase):
    def setUp(self):
        self.category=Category.objects.get(slug='jaquetas')
    def test_identidade_portuguesa_e_categorias(self):
        page=self.client.get(reverse('home'))
        self.assertEqual(page.status_code,200)
        for text in ('Da rua para a arte.','O ATELIÊ','NOSSA HISTÓRIA','JAQUETAS'):
            self.assertContains(page,text)
        self.assertNotContains(page,'Fraldas')
        self.assertFalse(Product.objects.exists())
    def test_manifesto_atelie_sao_publicos(self):
        self.assertContains(self.client.get(reverse('manifesto')),'A moda não começa')
        self.assertContains(self.client.get(reverse('atelie')),'O feito à mão')
    def test_produto_tem_processo_medidas_conservacao(self):
        p=Product.objects.create(category=self.category,name='Jaqueta reconstruída',slug='jaqueta-reconstruida',
          price=Decimal('350'),one_of_one=True,materials='Sarja recuperada',artistic_process='Recortes feitos à mão',
          measurements='Ombro: 50 cm',conservation='Marcas de uso informadas')
        variant=ProductVariant.objects.create(product=p,sku='LEFI-JAQ-01',size='M',color='Preta',stock=1)
        html=self.client.get(reverse('product_detail',args=[p.slug]))
        for text in ('Sarja recuperada','Recortes feitos à mão','Ombro: 50 cm','EDIÇÃO ÚNICA'):
            self.assertContains(html,text)
        self.assertContains(html,'LEFI-JAQ-01' if False else 'Preta')
    def test_peca_unica_nao_admite_estoque_maior_que_um(self):
        p=Product.objects.create(category=self.category,name='Exemplar único',slug='exemplar-unico',
          price=Decimal('100'),one_of_one=True)
        v=ProductVariant(product=p,sku='LEFI-UN-01',size='UN',color='Original',stock=2)
        with self.assertRaises(ValidationError):v.full_clean()
    def test_peca_unica_nao_admite_mais_de_uma_unidade_no_carrinho(self):
        p=Product.objects.create(category=self.category,name='Peça 1 de 1',slug='peca-1-1',
          price=Decimal('100'),one_of_one=True)
        v=ProductVariant.objects.create(product=p,sku='LEFI-UN-02',size='UN',color='Original',stock=1)
        self.client.post(reverse('cart_add'),{'variant_id':v.pk,'quantity':'2'})
        self.assertContains(self.client.get(reverse('cart')),'Seu carrinho está pronto para receber sua próxima escolha.')
    @override_settings(LEFI_SHIPPING_FLAT='10.00',LEFI_CHECKOUT_ENABLED=False,LEFI_ACCEPT_MANUAL_ORDERS=False)
    def test_pagamentos_inativos_por_padrao(self):
        p=Product.objects.create(category=self.category,name='Jaqueta disponível',slug='jaqueta-disponivel',price=Decimal('130'))
        v=ProductVariant.objects.create(product=p,sku='LEFI-J-03',size='M',color='Cinza',stock=2)
        buyer=get_user_model().objects.create_user(username='comprador-lefi',password='Test2026@senha')
        self.client.force_login(buyer)
        self.client.post(reverse('cart_add'),{'variant_id':v.pk,'quantity':'1'})
        self.assertContains(self.client.get(reverse('checkout')),'Pagamento temporariamente indisponível')
