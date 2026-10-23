from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('store', '0005_limpeza_unica_catalogo')]
    operations = [
        migrations.CreateModel(
            name='StoreInformation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brand_name', models.CharField(default='Klaus Pet', max_length=100, verbose_name='Marca exibida')),
                ('legal_name', models.CharField(blank=True, max_length=180, verbose_name='Razão social / nome empresarial')),
                ('tax_id', models.CharField(blank=True, max_length=25, verbose_name='CNPJ (se aplicável)')),
                ('business_address', models.TextField(blank=True, verbose_name='Endereço comercial para divulgação')),
                ('contact_email', models.EmailField(blank=True, max_length=254, verbose_name='E-mail de atendimento')),
                ('privacy_email', models.EmailField(blank=True, max_length=254, verbose_name='E-mail para solicitações LGPD (opcional)')),
                ('contact_phone', models.CharField(blank=True, max_length=24, verbose_name='WhatsApp de atendimento (somente números, com DDI)')),
                ('service_hours', models.CharField(blank=True, max_length=180, verbose_name='Horário de atendimento')),
                ('instagram_url', models.URLField(blank=True, verbose_name='Instagram oficial')),
                ('dispatch_region', models.CharField(default='', max_length=160, verbose_name='Origem dos envios')),
                ('shipping_preparation', models.CharField(blank=True, max_length=190, verbose_name='Prazo de preparação para envio')),
                ('delivery_estimate', models.CharField(blank=True, max_length=300, verbose_name='Informações sobre prazos de entrega')),
                ('shipping_details', models.TextField(blank=True, verbose_name='Informações adicionais de entrega (opcional)')),
                ('exchange_details', models.TextField(blank=True, verbose_name='Procedimento de trocas/devoluções (opcional)')),
                ('last_updated', models.DateTimeField(auto_now=True, verbose_name='Última atualização')),
            ],
            options={'verbose_name':'Informações comerciais e atendimento', 'verbose_name_plural':'Informações comerciais e atendimento'},
        ),
    ]
