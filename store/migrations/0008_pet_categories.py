from django.db import migrations

CATEGORIES = [
    ('Cachorros', 'cachorros'),
    ('Gatos', 'gatos'),
    ('Fraldas', 'fraldas'),
    ('Higiene', 'higiene'),
    ('Alimentação', 'alimentacao'),
    ('Acessórios', 'acessorios'),
    ('Ofertas', 'ofertas'),
]


def create_pet_categories(apps, schema_editor):
    Category = apps.get_model('store', 'Category')
    for name, slug in CATEGORIES:
        Category.objects.using(schema_editor.connection.alias).get_or_create(slug=slug, defaults={'name': name})

class Migration(migrations.Migration):
    dependencies = [('store', '0007_order_workflow_notifications')]
    operations = [migrations.RunPython(create_pet_categories, migrations.RunPython.noop)]
