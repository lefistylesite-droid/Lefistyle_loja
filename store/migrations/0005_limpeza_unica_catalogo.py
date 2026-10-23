"""Limpeza única e definitiva do catálogo anterior (solicitação expressa da loja).

Preserva registros de pedidos históricos pelo snapshot de descrição, SKU, valor e quantidade,
mas remove as relações aos SKUs antigos. NÃO apaga pedidos, clientes nem categorias.
Somente executada uma vez na primeira implantação desta migração.
"""
from django.db import migrations, models
import django.db.models.deletion


def limpar_catalogo(apps, schema_editor):
    Product = apps.get_model('store', 'Product')
    db = schema_editor.connection.alias
    # TODOS os produtos existentes, reais ou demonstrativos, suas variantes,
    # fotos e binários, sem arquivamentos residuais na administração.
    # OrderItem.variant recebe NULL via SET_NULL; snapshots do pedido são mantidos.
    Product.objects.using(db).all().delete()


class Migration(migrations.Migration):
    dependencies = [('store', '0004_fotos_postgres')]
    operations = [
        migrations.AlterField(
            model_name='orderitem',
            name='variant',
            field=models.ForeignKey(to='store.productvariant', null=True, blank=True,
                                    on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.RunPython(limpar_catalogo, reverse_code=migrations.RunPython.noop),
    ]
