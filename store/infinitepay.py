"""Adaptador InfinitePay Checkout Integrado (API Key) — valores em centavos.

Não confiar em parâmetros de redirecionamento ou conteúdo do webhook.
A confirmação requer payment_check autenticado e checagem de pedido/valor.
"""
import json
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Order, ProductVariant

API_BASE = 'https://api.checkout.infinitepay.io'
CHECKOUT_HOSTS = {'checkout.infinitepay.com.br', 'checkout.infinitepay.io'}

class InfinitePayError(Exception):
    pass


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _call(path, payload):
    key = getattr(settings, 'INFINITEPAY_API_KEY', '')
    if not key:
        raise InfinitePayError('API Key InfinitePay não configurada')
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = Request(API_BASE + path, data=data, method='POST', headers={
        'X-Api-Key': key, 'Content-Type': 'application/json', 'Accept': 'application/json',
    })
    try:
        with urlopen(request, timeout=12) as response:
            result = json.loads(response.read(250000).decode('utf-8'))
            if not isinstance(result, dict):
                raise ValueError('Resposta inesperada')
            return result
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        # Nunca devolver/registrar credenciais nem payload completo em mensagens de erro.
        raise InfinitePayError('A InfinitePay não pôde responder. Tente novamente.') from exc


def order_reference(order_id):
    return f'LEFI-{order_id}'


def create_payment_link(order, base_url):
    if not settings.INFINITEPAY_TAG:
        raise InfinitePayError('InfiniteTag não configurada')
    items = [
        {'quantity': line.quantity, 'price': cents(line.unit_price), 'description': line.description[:150]}
        for line in order.items.all()
    ]
    if cents(order.shipping_amount) > 0:
        items.append({'quantity': 1, 'price': cents(order.shipping_amount), 'description': 'Entrega LEFI'})
    if not items or sum(i['quantity'] * i['price'] for i in items) != cents(order.total):
        raise InfinitePayError('Total do pedido divergente')
    payload = {
        'order_nsu': order_reference(order.pk),
        'redirect_url': f'{base_url}/pagamento/retorno/{order.pk}/',
        'items': items,
        'customer': {'name': order.customer_name, 'email': order.contact_email},
        'options': {'single_payment': True,
                    'valid_until': order.payment_expires_at.isoformat() if order.payment_expires_at else None,
                    'payment_methods_enabled': ['credit_card', 'pix']},
        'webhook': {
            'url': f'{base_url}/pagamento/webhook/',
            'events': ['paid', 'refunded', 'canceled', 'payment_failed'],
        },
    }
    if not order.payment_expires_at or order.payment_expires_at <= timezone.now():
        raise InfinitePayError('Pedido sem prazo válido de pagamento')
    if not settings.INFINITEPAY_API_KEY:
        # Por segurança, a LEFI exige API Key mesmo existindo um modo sem chave.
        raise InfinitePayError('API Key obrigatória na integração LEFI')
    result = _call('/links', payload)
    url = result.get('url') or result.get('checkout_url')
    if not isinstance(url, str) or urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in CHECKOUT_HOSTS:
        raise InfinitePayError('Link de pagamento InfinitePay inválido')
    return order_reference(order.pk), url


def payment_check(order_id, transaction_nsu, slug):
    """Verifica transação usando o endpoint autenticado (não os dados de webhook)."""
    if not all(isinstance(v, str) and 1 <= len(v) <= 160 for v in (transaction_nsu, slug)):
        raise InfinitePayError('Identificadores de pagamento inválidos')
    return _call('/payment_check', {
        'handle': settings.INFINITEPAY_TAG,
        'order_nsu': order_reference(order_id),
        'transaction_nsu': transaction_nsu,
        'slug': slug,
    })


def verify_and_apply(order_id, transaction_nsu, slug):
    """Somente payment_check autenticado com paid=True e valor correto pode aprovar pedido."""
    try:
        reference = order_reference(order_id)
        # Impede consultas desnecessárias sobre pedidos inexistentes.
        if not Order.objects.filter(pk=order_id, gateway_preference_id=reference).exists():
            return False
        result = payment_check(order_id, transaction_nsu, slug)
        if result.get('success') is not True or result.get('paid') is not True:
            return False
        # Esta API retorna amount em centavos. paid_amount pode incluir encargos/parcelas.
        amount = result.get('amount')
        if isinstance(amount, bool) or not isinstance(amount, int):
            return False
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=order_id).first()
            if not order or order.gateway_preference_id != reference or amount != cents(order.total):
                return False
            if order.gateway_payment_id and order.gateway_payment_id != transaction_nsu:
                return False
            if order.status in ('cancelled', 'refunded') or not order.stock_reserved:
                return False
            first_approval = order.status == 'pending_payment'
            if first_approval:
                order.status = 'paid'
                order.paid_at = timezone.now()
                order.payment_status = 'paid'
            order.gateway_payment_id = transaction_nsu
            order.save(update_fields=['status','paid_at','payment_status','gateway_payment_id','updated_at'])
            if first_approval:
                from .models import OrderEvent
                from .notifications import queue_order_email
                OrderEvent.objects.create(order=order, event='order.paid', details='Confirmação autenticada payment_check InfinitePay')
                queue_order_email(order, 'order.paid')
        return True
    except (ValueError, TypeError):
        return False


def release_reservation(order_id):
    """Apenas para falhas no início, antes de haver URL de checkout utilizável."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if not order.stock_reserved or order.status != 'pending_payment':
            return
        for line in order.items.all():
            ProductVariant.objects.filter(pk=line.variant_id).update(stock=F('stock') + line.quantity)
        order.stock_reserved = False
        order.status = 'cancelled'
        order.payment_status = 'link_error'
        order.save(update_fields=['stock_reserved','status','payment_status','updated_at'])


def release_abandoned_after_manual_confirmation(order_id, *, staff_user, provider_checked=False):
    """Revogação MANUAL: só após expiração + 24h e conferência de NÃO pagamento
    diretamente na InfinitePay. Em caso de dúvida, NÃO liberar estoque.

    Não confundir expiração do link com confirmação de não pagamento.
    Chamadas repetidas não somam estoque duas vezes.
    """
    if not provider_checked or not staff_user or not staff_user.is_staff:
        raise ValueError('A conferência manual por um administrador é obrigatória')
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if not order.stock_reserved or order.status != 'pending_payment':
            return False
        if not order.payment_expires_at or timezone.now() < order.payment_expires_at + timedelta(hours=24):
            raise ValueError('Aguarde pelo menos 24h após vencer o prazo antes de analisar')
        # Também permite liberação MANUAL de timeout sem URL, sujeito à mesma
        # quarentena e à conferência explícita do order_nsu diretamente no provedor.
        if not order.gateway_checkout_url and order.payment_status not in ('link_creation_uncertain', 'awaiting_payment'):
            raise ValueError('Sem link validado: procure suporte antes de liberar')
        if order.gateway_payment_id or order.paid_at:
            raise ValueError('O pedido tem registro de pagamento; NÃO devolver estoque')
        for item in order.items.all():
            ProductVariant.objects.filter(pk=item.variant_id).update(stock=F('stock') + item.quantity)
        order.stock_reserved = False
        order.status = 'cancelled'
        order.payment_status = 'manually_confirmed_unpaid'
        order.notes = ((order.notes or '') + '\n' +
                       f'[{timezone.now().isoformat()}] Cancelamento manual após conferência '
                       f'InfinitePay; operador={staff_user.pk}').strip()
        order.save(update_fields=['stock_reserved','status','payment_status','notes','updated_at'])
        from .models import OrderEvent
        from .notifications import queue_order_email
        OrderEvent.objects.create(order=order,event='order.cancelled',actor=staff_user,
                                  details='Cancelado após verificação manual de não pagamento no provedor')
        queue_order_email(order,'order.cancelled')
        return True
