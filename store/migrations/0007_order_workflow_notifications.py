from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('store','0006_store_information'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='order',name='cancellation_requested_at',field=models.DateTimeField(blank=True,null=True,verbose_name='Solicitação de cancelamento')),
        migrations.AddField(model_name='order',name='cancellation_reason',field=models.TextField(blank=True,verbose_name='Motivo informado pela cliente')),
        migrations.AddField(model_name='order',name='tracking_carrier',field=models.CharField(blank=True,max_length=120,verbose_name='Transportadora / forma de entrega')),
        migrations.AddField(model_name='order',name='tracking_code',field=models.CharField(blank=True,max_length=150,verbose_name='Código de rastreio / referência de entrega')),
        migrations.AddField(model_name='order',name='refund_confirmed_at',field=models.DateTimeField(blank=True,null=True,verbose_name='Reembolso confirmado no provedor')),
        migrations.CreateModel(name='OrderEvent',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('event',models.CharField(max_length=48)),('details',models.TextField(blank=True)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('actor',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
            ('order',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='history',to='store.order')),
        ],options={'ordering':['-created_at'],'verbose_name':'Histórico do pedido','verbose_name_plural':'Histórico dos pedidos'}),
        migrations.CreateModel(name='EmailNotification',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('event',models.CharField(max_length=48)),('recipient',models.EmailField(max_length=254)),
            ('status',models.CharField(choices=[('pending','Pendente'),('sending','Enviando'),('sent','Enviado'),('error','Falha')],default='pending',max_length=12)),
            ('attempts',models.PositiveSmallIntegerField(default=0)),('last_error',models.CharField(blank=True,max_length=240)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('sent_at',models.DateTimeField(blank=True,null=True)),
            ('order',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='notifications',to='store.order')),
        ],options={'ordering':['-created_at'],'verbose_name':'Notificação de e-mail','verbose_name_plural':'Notificações de e-mail'}),
        migrations.AddConstraint(model_name='emailnotification',constraint=models.UniqueConstraint(fields=['order','event'],name='klauspet_unique_order_notice')),
    ]
