# Initial migration for Klaus Pet 1.0 (schema versioned)
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('name',models.CharField(max_length=90,unique=True,verbose_name='Nome')),
                ('slug',models.SlugField(unique=True,verbose_name='Identificador')),
                ('active',models.BooleanField(default=True,verbose_name='Ativa')),
            ],
            options={'verbose_name':'Categoria','verbose_name_plural':'Categorias','ordering':['name']},
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('name',models.CharField(max_length=160,verbose_name='Nome')),
                ('slug',models.SlugField(unique=True,verbose_name='Identificador')),
                ('description',models.TextField(blank=True,verbose_name='Descrição')),
                ('price',models.DecimalField(decimal_places=2,max_digits=10,validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],verbose_name='Preço')),
                ('sale_price',models.DecimalField(blank=True,decimal_places=2,max_digits=10,null=True,validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],verbose_name='Preço promocional')),
                ('cost_price',models.DecimalField(decimal_places=2,default=0,max_digits=10,verbose_name='Custo')),
                ('image_url',models.CharField(default='/static/img/conjunto-mocha.webp',max_length=500,verbose_name='Imagem principal (URL/estático)')),
                ('featured',models.BooleanField(default=False,verbose_name='Destaque')),
                ('active',models.BooleanField(default=True,verbose_name='Ativo')),
                ('created_at',models.DateTimeField(auto_now_add=True,verbose_name='Criado em')),
                ('category',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='products',to='store.category',verbose_name='Categoria')),
            ],
            options={'verbose_name':'Produto','verbose_name_plural':'Produtos','ordering':['-featured','-created_at']},
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('sku',models.CharField(max_length=60,unique=True,verbose_name='SKU')),
                ('size',models.CharField(choices=[('PP','PP'),('P','P'),('M','M'),('G','G'),('GG','GG'),('XG','XG'),('UN','Único')],max_length=3,verbose_name='Tamanho / porte')),
                ('color',models.CharField(max_length=70,verbose_name='Modelo / embalagem')),
                ('color_hex',models.CharField(default='#C77D43',max_length=7,verbose_name='Cor de referência (opcional)')),
                ('stock',models.PositiveIntegerField(default=0,verbose_name='Estoque')),
                ('active',models.BooleanField(default=True,verbose_name='Ativo')),
                ('product',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='variants',to='store.product',verbose_name='Produto')),
            ],
            options={'verbose_name':'Variação','verbose_name_plural':'Variações','ordering':['color','size']},
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('image_url',models.CharField(max_length=500,verbose_name='URL da imagem')),
                ('alt',models.CharField(blank=True,max_length=140,verbose_name='Texto alternativo')),
                ('position',models.PositiveSmallIntegerField(default=0,verbose_name='Posição')),
                ('product',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='gallery',to='store.product',verbose_name='Produto')),
            ],
            options={'verbose_name':'Imagem de produto','verbose_name_plural':'Imagens de produtos','ordering':['position','id']},
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('created_at',models.DateTimeField(auto_now_add=True)),
                ('status',models.CharField(choices=[('pending_payment','Aguardando pagamento'),('paid','Pago'),('preparing','Separação'),('shipped','Enviado'),('delivered','Entregue'),('cancelled','Cancelado'),('refunded','Estornado')],default='pending_payment',max_length=24)),
                ('total',models.DecimalField(decimal_places=2,default=0,max_digits=12)),
                ('shipping_amount',models.DecimalField(decimal_places=2,default=0,max_digits=12)),
                ('customer_name',models.CharField(max_length=150)),
                ('contact_email',models.EmailField(max_length=254)),
                ('address',models.TextField(blank=True)),
                ('gateway_payment_id',models.CharField(blank=True,max_length=140)),
                ('notes',models.TextField(blank=True)),
                ('user',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='orders',to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name':'Pedido','verbose_name_plural':'Pedidos','ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('description',models.CharField(max_length=220)),
                ('sku',models.CharField(max_length=60)),
                ('quantity',models.PositiveIntegerField()),
                ('unit_price',models.DecimalField(decimal_places=2,max_digits=10)),
                ('order',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='items',to='store.order')),
                ('variant',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to='store.productvariant')),
            ],
            options={'verbose_name':'Item do pedido','verbose_name_plural':'Itens do pedido'},
        ),
        migrations.AddConstraint(
            model_name='productvariant',
            constraint=models.UniqueConstraint(fields=('product','size','color'),name='klauspet_unique_product_size_color'),
        ),
    ]
