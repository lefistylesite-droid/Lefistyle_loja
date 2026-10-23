import re
from django.db import migrations


def backfill(apps, schema_editor):
    Order=apps.get_model('store','Order')
    states=set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
    for order in Order.objects.using(schema_editor.connection.alias).filter(shipping_state='').iterator():
        matches=re.findall(r'^([^\n/]{1,100}) / ([A-Z]{2})\s*$',order.address,re.MULTILINE)
        if len(matches)==1 and matches[0][1] in states:
            Order.objects.using(schema_editor.connection.alias).filter(pk=order.pk).update(
                shipping_city=matches[0][0].strip(),shipping_state=matches[0][1])

class Migration(migrations.Migration):
    dependencies=[('store','0009_order_shipping_city_order_shipping_state_and_more')]
    operations=[migrations.RunPython(backfill,migrations.RunPython.noop)]
