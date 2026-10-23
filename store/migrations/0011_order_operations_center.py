# Ampliação incremental e aditiva. Nenhum pedido ou dado prévio é apagado.
from django.db import migrations, models
import django.utils.timezone


def backfill_initial_updates(apps, schema_editor):
    Order = apps.get_model("store", "Order")
    Order.objects.using(schema_editor.connection.alias).all().update(updated_at=models.F("created_at"))

class Migration(migrations.Migration):
    dependencies = [('store','0010_backfill_order_regions')]
    operations = [
        migrations.AlterField(model_name='order',name='status',field=models.CharField(max_length=24,default='pending_payment',choices=[('pending_payment','Aguardando pagamento'),('paid','Pago'),('preparing','Em separação'),('ready_to_ship','Pronto para envio'),('shipped','Enviado'),('delivered','Entregue'),('cancelled','Cancelado'),('refunded','Estornado')])),
        migrations.AddField(model_name='order',name='updated_at',field=models.DateTimeField(auto_now=True,default=django.utils.timezone.now),preserve_default=False),
        migrations.RunPython(backfill_initial_updates, migrations.RunPython.noop),
        migrations.AddField(model_name='order',name='contact_phone',field=models.CharField(max_length=20,blank=True,verbose_name='Telefone do cliente')),
        migrations.AddField(model_name='order',name='shipping_postal_code',field=models.CharField(max_length=9,blank=True,verbose_name='CEP')),
        migrations.AddField(model_name='order',name='shipping_street',field=models.CharField(max_length=160,blank=True,verbose_name='Rua / avenida')),
        migrations.AddField(model_name='order',name='shipping_number',field=models.CharField(max_length=20,blank=True,verbose_name='Número')),
        migrations.AddField(model_name='order',name='shipping_complement',field=models.CharField(max_length=140,blank=True,verbose_name='Complemento')),
        migrations.AddField(model_name='order',name='shipping_neighborhood',field=models.CharField(max_length=100,blank=True,verbose_name='Bairro')),
        migrations.AddField(model_name='order',name='shipping_reference',field=models.CharField(max_length=200,blank=True,verbose_name='Referência para entrega')),
        migrations.AddField(model_name='order',name='tracking_url',field=models.URLField(max_length=600,blank=True,verbose_name='Link de acompanhamento')),
        migrations.AddField(model_name='order',name='shipped_at',field=models.DateTimeField(null=True,blank=True,verbose_name='Data da postagem')),
        migrations.AddField(model_name='order',name='delivered_at',field=models.DateTimeField(null=True,blank=True,verbose_name='Data da entrega confirmada')),
        migrations.AddField(model_name='order',name='estimated_delivery',field=models.DateField(null=True,blank=True,verbose_name='Previsão de entrega')),
        migrations.AddField(model_name='storeinformation',name='shopee_url',field=models.URLField(blank=True,verbose_name='Loja oficial na Shopee (quando confirmada)')),
        migrations.AddField(model_name='storeinformation',name='tiktok_shop_url',field=models.URLField(blank=True,verbose_name='Loja oficial no TikTok Shop (quando confirmada)')),
        migrations.AddIndex(model_name='order',index=models.Index(fields=['-created_at'],name='klaus_order_created_idx')),
        migrations.AddIndex(model_name='order',index=models.Index(fields=['status','-created_at'],name='klaus_order_status_idx')),
    ]
