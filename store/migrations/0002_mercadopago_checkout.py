from django.db import migrations, models

DEMO_SLUGS = ['conjunto-aura-mocha', 'top-essential-areia', 'legging-sculpt-nude', 'short-move-rose', 'legging-performance-cacau', 'conjunto-flow-rose']

def mark_existing_demo(apps, schema_editor):
    Product = apps.get_model('store', 'Product')
    Product.objects.filter(slug__in=DEMO_SLUGS).update(is_demo=True)

class Migration(migrations.Migration):
    dependencies = [('store', '0001_initial')]
    operations = [
        migrations.AddField(model_name='product', name='is_demo', field=models.BooleanField(default=False, verbose_name='Produto ilustrativo — não vender')),
        migrations.AddField(model_name='order', name='gateway_preference_id', field=models.CharField(max_length=160, blank=True)),
        migrations.AddField(model_name='order', name='gateway_checkout_url', field=models.URLField(max_length=1000, blank=True)),
        migrations.AddField(model_name='order', name='checkout_nonce', field=models.CharField(max_length=50, null=True, blank=True, unique=True)),
        migrations.AddField(model_name='order', name='payment_status', field=models.CharField(max_length=40, default='not_started', blank=True)),
        migrations.AddField(model_name='order', name='stock_reserved', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='order', name='paid_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.RunPython(mark_existing_demo, migrations.RunPython.noop),
    ]
