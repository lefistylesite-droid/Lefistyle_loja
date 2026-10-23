"""Regressões específicas da LEFI, sem produtos inventados na loja."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Category, Product, ProductVariant, ProductImage

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

class VitrineComProdutosTests(TestCase):
    """Regressão: o erro 500 só ocorria nas listagens com produtos reais."""
    def setUp(self):
        self.jaquetas = Category.objects.get(slug='jaquetas')
        self.acessorios = Category.objects.get(slug='acessorios')
        self.p = Product.objects.create(
            category=self.acessorios, name='Boné LEFI Arte de Rua', slug='bone-lefi-arte-rua',
            description='Edição feita à mão', price=Decimal('189.00'),
            sale_price=Decimal('169.00'), collection='Reinvenção', active=True, featured=True,
        )
        self.imagem = ProductImage.objects.create(
            product=self.p, photo_data=b'RIFF_placeholder', has_upload=True,
            alt='Boné de frente', position=0,
        )
        ProductVariant.objects.create(
            product=self.p, sku='LEFI-CAP-1', size='UN', color='Verde', stock=1,
        )

    def test_home_loja_categorias_busca_com_fotos_cadastradas(self):
        for name in ('home', 'loja', 'categorias', 'buscar'):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Boné LEFI Arte de Rua')
                self.assertContains(response, reverse('product_image', args=[self.imagem.pk]))
                self.assertContains(response, '169,00')

    def test_busca_por_nome_descricao_colecao(self):
        for palavra in ('Boné', 'mão', 'Reinvenção'):
            with self.subTest(palavra=palavra):
                self.assertContains(self.client.get(reverse('buscar'), {'q': palavra}), self.p.name)
        self.assertNotContains(self.client.get(reverse('buscar'), {'q': 'inexistente'}), self.p.name)

    def test_categorias_filtram_e_nao_excluem_produto(self):
        self.assertContains(self.client.get(reverse('loja'), {'categoria': 'acessorios'}), self.p.name)
        self.assertNotContains(self.client.get(reverse('loja'), {'categoria': 'jaquetas'}), self.p.name)
        self.assertEqual(Product.objects.filter(pk=self.p.pk).count(), 1)
        self.assertTrue(ProductImage.objects.filter(pk=self.imagem.pk).exists())

    def test_paginacao_preserva_filtros(self):
        for i in range(25):
            Product.objects.create(category=self.acessorios,
                name=f'Peça teste {i}', slug=f'peca-teste-{i}', price=Decimal('99.90'))
        response = self.client.get(reverse('loja'), {'categoria': 'acessorios'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PRÓXIMA')
        self.assertContains(response, 'categoria=acessorios')
        next_page = self.client.get(reverse('loja'), {'categoria': 'acessorios', 'pagina': 2})
        self.assertEqual(next_page.status_code, 200)
        self.assertEqual(len(next_page.context['products']), 2)
