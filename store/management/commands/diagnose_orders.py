from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
from store.models import Order
from store.views import checkout_ready

class Command(BaseCommand):
    help = 'Diagnóstico de pedidos, sem exibir credenciais ou dados pessoais.'
    def handle(self, *args, **kwargs):
        ready, shipping = checkout_ready()
        self.stdout.write(f'Banco: {connection.vendor}')
        self.stdout.write(f'Pedidos registrados: {Order.objects.count()}')
        self.stdout.write(f'Pendentes: {Order.objects.filter(status="pending_payment").count()}')
        self.stdout.write(f'Links em revisão: {Order.objects.filter(payment_status="link_creation_uncertain").count()}')
        self.stdout.write(f'Frete definido: {shipping is not None}')
        self.stdout.write(f'Checkout online configurado: {ready}')
        self.stdout.write(f'Pedidos manuais habilitados: {settings.LEFI_ACCEPT_MANUAL_ORDERS}')
        self.stdout.write('Se houver pedidos aqui e não no painel, confira filtros, permissões e se o serviço usa este mesmo banco.')
