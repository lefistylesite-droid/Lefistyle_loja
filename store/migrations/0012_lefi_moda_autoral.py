from django.db import migrations, models

CATEGORIAS = [
 ('Jaquetas e casacos','jaquetas'),('Calças','calcas'),('Camisetas e tops','camisetas'),
 ('Acessórios','acessorios'),('Peças únicas','pecas-unicas'),('Arte e objetos','arte-objetos')]
ANTIGAS = ['cachorros','gatos','fraldas','higiene','alimentacao','ofertas']

def instalar_colecoes(apps, schema_editor):
    Categoria=apps.get_model('store','Category')
    Loja=apps.get_model('store','StoreInformation')
    alias=schema_editor.connection.alias
    for nome, slug in CATEGORIAS:
        obj, criado = Categoria.objects.using(alias).get_or_create(slug=slug,defaults={'name':nome,'active':True})
        if not criado and obj.name != nome:
            obj.name=nome
            obj.save(update_fields=['name'])
    for item in Categoria.objects.using(alias).filter(slug__in=ANTIGAS):
        if not item.products.exists(): item.delete()
    Loja.objects.using(alias).filter(brand_name='Klaus Pet').update(brand_name='LEFI')

class Migration(migrations.Migration):
    dependencies=[('store','0011_order_operations_center')]
    operations=[
        migrations.AddField(model_name='product',name='collection',field=models.CharField(blank=True,max_length=100,verbose_name='Coleção / cápsula')),
        migrations.AddField(model_name='product',name='creation_type',field=models.CharField(choices=[('reconstruida','Reconstruída'),('autoral','Autoral'),('vintage','Vintage selecionado'),('arte','Arte / objeto'),('outro','Outro')],default='reconstruida',max_length=30,verbose_name='Tipo de peça')),
        migrations.AddField(model_name='product',name='one_of_one',field=models.BooleanField(default=False,verbose_name='Peça única — edição 1/1')),
        migrations.AddField(model_name='product',name='materials',field=models.CharField(blank=True,max_length=300,verbose_name='Materiais e composição')),
        migrations.AddField(model_name='product',name='artistic_process',field=models.TextField(blank=True,verbose_name='Processo criativo / intervenção manual')),
        migrations.AddField(model_name='product',name='origin_story',field=models.TextField(blank=True,verbose_name='História e procedência da peça')),
        migrations.AddField(model_name='product',name='conservation',field=models.CharField(blank=True,max_length=220,verbose_name='Condição / sinais de uso')),
        migrations.AddField(model_name='product',name='measurements',field=models.TextField(blank=True,verbose_name='Medidas da peça')),
        migrations.AddField(model_name='product',name='care_instructions',field=models.TextField(blank=True,verbose_name='Cuidados e conservação')),
        migrations.AlterField(model_name='productvariant',name='size',field=models.CharField(choices=[('PP','PP'),('P','P'),('M','M'),('G','G'),('GG','GG'),('XG','XG'),('UN','Único'),('34','34'),('36','36'),('38','38'),('40','40'),('42','42'),('44','44'),('46','46'),('48','48')],max_length=3,verbose_name='Tamanho')),
        migrations.AlterField(model_name='productvariant',name='color',field=models.CharField(max_length=70,verbose_name='Cor / acabamento')),
        migrations.AlterField(model_name='productvariant',name='color_hex',field=models.CharField(default='#222222',max_length=7,verbose_name='Cor de referência (opcional)')),
        migrations.AlterField(model_name='storeinformation',name='brand_name',field=models.CharField(default='LEFI',max_length=100,verbose_name='Marca exibida')),
        migrations.RunPython(instalar_colecoes,migrations.RunPython.noop),
    ]
