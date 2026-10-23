from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('store', '0003_infinitepay_link_expiration')]
    operations = [
        migrations.AlterField(model_name='product', name='image_url', field=models.CharField('Imagem anterior (legado)', max_length=500, blank=True, default='')),
        migrations.AlterField(model_name='productimage', name='image_url', field=models.CharField('URL antiga (compatibilidade)', max_length=500, blank=True, default='')),
        migrations.AddField(model_name='productimage', name='photo_data', field=models.BinaryField('Imagem otimizada (WebP)', blank=True, null=True, editable=False)),
        migrations.AddField(model_name='productimage', name='has_upload', field=models.BooleanField('Imagem enviada', default=False, editable=False)),
    ]
