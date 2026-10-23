from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import Order, OrderEvent, ProductVariant
from .notifications import queue_order_email


def resolve_manual_order(order_id, actor, operation, reference=''):
    if not actor.has_perm('store.change_order'):
        raise ValueError('Permissão insuficiente.')
    if operation not in ('paid', 'cancelled'):
        raise ValueError('Operação inválida.')
    if operation == 'paid' and len(reference.strip()) < 5:
        raise ValueError('Informe uma referência do recebimento conferido, com pelo menos 5 caracteres.')
    with transaction.atomic():
        order=Order.objects.select_for_update().get(pk=order_id)
        if order.status != 'pending_payment' or order.payment_status != 'manual_pending' or order.gateway_checkout_url:
            raise ValueError('Esta ação é exclusiva para pedido manual ainda pendente e sem link de pagamento.')
        if operation == 'paid':
            order.status='paid'; order.payment_status='manual_paid'; order.paid_at=timezone.now()
        else:
            if order.stock_reserved:
                for item in order.items.order_by('variant_id'):
                    if item.variant_id:
                        ProductVariant.objects.filter(pk=item.variant_id).update(stock=F('stock')+item.quantity)
            order.stock_reserved=False; order.status='cancelled'; order.payment_status='cancelled'
        order.save(update_fields=['status','payment_status','stock_reserved','paid_at','updated_at'])
        OrderEvent.objects.create(order=order,event='order.'+operation,actor=actor,
            details=('Recebimento conferido manualmente. Referência: '+reference.strip()[:180]) if operation=='paid' else 'Pedido manual cancelado sem cobrança; estoque devolvido.')
        queue_order_email(order,'order.'+operation)
