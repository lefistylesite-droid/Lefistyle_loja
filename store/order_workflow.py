"""Transições administrativas com conferência e auditoria persistente.

Nunca cancela cobranças na InfinitePay por suposição e nunca promete estorno
sem confirmação externa. Mudanças de status são processadas com trava no DB.
"""
from django.db import transaction
from django.utils import timezone
from .models import Order, OrderEvent
from .notifications import queue_order_email

ALLOWED = {
    'preparing': ('paid',),
    'ready_to_ship': ('preparing',),
    'shipped': ('preparing', 'ready_to_ship'),
    'delivered': ('shipped',),
    'refunded': ('paid', 'preparing', 'shipped', 'delivered'),
}
EVENTS = {'preparing':'order.preparing','ready_to_ship':'order.ready_to_ship','shipped':'order.shipped','delivered':'order.delivered','refunded':'order.refunded'}


def transition_order(order_id, new_status, *, actor, provider_verified=False):
    if not actor or not actor.is_staff or not actor.has_perm('store.change_order'):
        raise ValueError('Sem permissão para alterar pedidos')
    if new_status not in ALLOWED:
        raise ValueError('Transição não permitida')
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status == new_status:
            return False
        if order.status not in ALLOWED[new_status]:
            raise ValueError(f'Pedido {order.pk}: não é possível ir de {order.status} para {new_status}')
        if new_status in ('shipped','delivered') and (not order.tracking_carrier or not order.tracking_code):
            raise ValueError('Preencha transportadora e código/referência de entrega antes de marcar como enviado/entregue')
        if new_status == 'refunded':
            if not provider_verified or not order.gateway_payment_id:
                raise ValueError('Confirme o estorno na InfinitePay antes de registrar reembolso')
            order.refund_confirmed_at=timezone.now()
            order.payment_status='refunded'
        order.status=new_status
        fields=['status','updated_at']
        if new_status == 'shipped' and order.shipped_at is None:
            order.shipped_at=timezone.now(); fields.append('shipped_at')
        if new_status == 'delivered' and order.delivered_at is None:
            order.delivered_at=timezone.now(); fields.append('delivered_at')
        if new_status == 'refunded':
            fields.extend(['refund_confirmed_at','payment_status'])
        order.save(update_fields=fields)
        OrderEvent.objects.create(order=order,event=EVENTS[new_status],actor=actor,
                   details='Atualização manual pelo administrador com confirmação externa' if new_status=='refunded' else 'Atualização pelo administrador')
        queue_order_email(order,EVENTS[new_status])
        return True


def request_cancellation(order, user, reason=''):
    with transaction.atomic():
        locked=Order.objects.select_for_update().get(pk=order.pk,user=user)
        if locked.status not in ('pending_payment','paid','preparing','ready_to_ship'):
            raise ValueError('Este pedido já foi enviado/concluído. Use a página de atendimento para solicitar devolução.')
        if locked.cancellation_requested_at:
            return False
        locked.cancellation_requested_at=timezone.now()
        locked.cancellation_reason=(reason or '')[:500]
        locked.save(update_fields=['cancellation_requested_at','cancellation_reason','updated_at'])
        OrderEvent.objects.create(order=locked,event='order.cancellation_requested',actor=user,
                                  details='Cliente solicitou cancelamento; necessita conferência administrativa')
        return True
