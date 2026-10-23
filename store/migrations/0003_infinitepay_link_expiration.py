from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('store', '0002_mercadopago_checkout')]
    operations = [
        migrations.AddField(
            model_name='order', name='payment_expires_at',
            field=models.DateTimeField('Validade do link InfinitePay', null=True, blank=True),
        ),
    ]
