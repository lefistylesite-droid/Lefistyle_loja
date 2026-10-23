"""Fila de mensagens transacionais. Nenhuma mensagem vai ao cliente sem canal ativo.

Google Apps Script é uma opção de envio sem SMTP; erros ficam registrados e
podem ser reenviados pelo administrador. Nunca confundir e-mail com pagamento.
"""
import json
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import escape
from .models import EmailNotification, Order

TITLES = {
    'order.created':'Recebemos seu pedido',
    'order.paid':'Pagamento confirmado',
    'order.preparing':'Seu pedido está em preparação',
    'order.shipped':'Seu pedido foi enviado',
    'order.delivered':'Pedido entregue',
    'order.cancelled':'Pedido cancelado',
    'order.refunded':'Reembolso registrado',
}


def queue_order_email(order, event):
    """Idempotência DB: apenas um e-mail por (pedido,event)."""
    if event not in TITLES:
        return
    notice, created = EmailNotification.objects.get_or_create(order=order, event=event,
                                       defaults={'recipient':order.contact_email})
    if created and settings.LEFI_EMAIL_ENABLED:
        transaction.on_commit(lambda pk=notice.pk: send_notice(pk))


def send_notice(pk):
    if not settings.LEFI_EMAIL_ENABLED:
        return False
    url = settings.LEFI_MAIL_SCRIPT_URL
    secret = settings.LEFI_MAIL_SCRIPT_SECRET
    if not url or not secret or urlsplit(url).scheme != 'https' or urlsplit(url).hostname != 'script.google.com':
        return False
    # Claim atômico para evitar envios paralelos pelo webhook e pelo admin.
    claimed=EmailNotification.objects.filter(pk=pk,status__in=['pending','error'],attempts__lt=5).update(
        status='sending',attempts=F('attempts')+1)
    if not claimed:
        return False
    notice=EmailNotification.objects.select_related('order').get(pk=pk)
    order=notice.order
    message = (
        f'Olá, {escape(order.customer_name)}!<br><br>'
        f'{escape(TITLES[notice.event])} — Pedido #{order.pk}.<br>'
        f'Total: R$ {order.total:.2f}.<br>'
        f'Situação atual: {escape(order.get_status_display())}.<br>'
    )
    if notice.event == 'order.shipped':
        message += f'Transportadora: {escape(order.tracking_carrier)}. Código: {escape(order.tracking_code)}.<br>'
    if notice.event == 'order.refunded':
        message += 'O reembolso foi confirmado na plataforma de pagamento. O prazo de disponibilização depende do meio utilizado.<br>'
    message += '<br>Atenciosamente, equipe LEFI.'
    # Esse endpoint deve ser privado pelo segredo; não aceitamos URL externa aleatória.
    payload=json.dumps({'secret':secret,'to':notice.recipient,'subject':f'{TITLES[notice.event]} | LEFI',
      'html': '<div style="font-family:Arial,sans-serif;background:#FFF5EC;padding:28px">'
              '<div style="max-width:550px;margin:auto;background:white;padding:28px;color:#4A2E25">'
              '<h1 style="color:#C77C42">LEFI</h1><p>'+message+'</p></div></div>',
      'notification_id':str(notice.pk)}).encode('utf-8')
    # Fora da transação de banco: o provedor pode demorar ou estar indisponível.
    try:
        req=Request(url,data=payload,method='POST',headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=4) as res:
            data=json.loads(res.read(4096).decode('utf-8'))
        if data.get('ok') is not True:
            raise ValueError('Serviço de e-mail não confirmou a entrega')
        EmailNotification.objects.filter(pk=pk).update(status='sent',sent_at=timezone.now(),last_error='')
        return True
    except Exception:
        # Não gravar corpo, token ou URL com segredos na base/logs.
        EmailNotification.objects.filter(pk=pk,status='sending').update(status='error',last_error='Falha ao enviar. Verifique o serviço de e-mail.')
        return False
