"""Central operacional dos pedidos, sem substituir checkout ou fonte de pagamentos.

Somente perfis staff com permissões explícitas podem visualizar/modificar.
Consultas paginadas em DB, atualizações auditadas e sem manipular pagamentos.
"""
import re
from datetime import date, timedelta
from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import Order, OrderEvent, CustomerProfile
from .order_workflow import transition_order


class ShippingUpdateForm(forms.Form):
    tracking_carrier = forms.CharField(label='Transportadora ou entrega', max_length=120, required=False)
    tracking_code = forms.CharField(label='Código de rastreio / referência', max_length=150, required=False)
    tracking_url = forms.URLField(label='Link de rastreamento (HTTPS)', max_length=600, required=False)
    estimated_delivery = forms.DateField(label='Previsão de entrega', required=False,
                                        widget=forms.DateInput(attrs={'type':'date'}, format='%Y-%m-%d'),
                                        input_formats=['%Y-%m-%d'])

    def clean_tracking_url(self):
        url = self.cleaned_data['tracking_url']
        if url and not url.lower().startswith('https://'):
            raise forms.ValidationError('Utilize endereço HTTPS do transportador.')
        return url


def can_view(user):
    return user.has_perm('store.view_order')


def can_edit(user):
    return user.has_perm('store.change_order')


def search_orders(queryset, text, can_search_cpf):
    text = (text or '').strip()[:100]
    if not text:
        return queryset
    normalized = re.sub(r'\D', '', text)
    condition = (Q(customer_name__icontains=text) | Q(contact_email__icontains=text) |
                 Q(contact_phone__icontains=text) | Q(tracking_code__icontains=text) |
                 Q(shipping_city__icontains=text))
    if normalized and normalized != text and len(normalized) >= 7:
        condition |= Q(contact_phone__icontains=normalized)
    # Buscar no campo legado de endereço para recuperar telefones antigos.
    if len(normalized) >= 8 and len(normalized) <= 15:
        condition |= Q(address__icontains=normalized)
    number = text.lstrip('#')
    if number.isascii() and number.isdecimal() and len(number) <= 18:
        condition |= Q(pk=int(number))
    # CPF não entra na exportação/lista e só é pesquisável por perfil autorizado.
    if can_search_cpf and len(normalized) == 11:
        condition |= Q(user__customer_profile__cpf=normalized)
    return queryset.filter(condition)


def filtered_orders(request):
    queryset = Order.objects.all()
    period = request.GET.get('period', '30')
    if period not in {'today', '7', '30', '90', 'all', 'custom'}:
        period = '30'
    if period in {'today', '7', '30', '90'}:
        start = timezone.localdate() - timedelta(days=(1 if period == 'today' else int(period))-1)
        queryset = queryset.filter(created_at__date__gte=start)
    start_date = end_date = ''
    if period == 'custom':
        start_date = request.GET.get('from', '')[:10]
        end_date = request.GET.get('to', '')[:10]
        try:
            if start_date:
                queryset = queryset.filter(created_at__date__gte=date.fromisoformat(start_date))
            if end_date:
                queryset = queryset.filter(created_at__date__lte=date.fromisoformat(end_date))
        except ValueError:
            queryset = queryset.none()
    status = request.GET.get('status','')
    if status in dict(Order.STATUSES):
        queryset = queryset.filter(status=status)
    else:
        status = ''
    queue = request.GET.get('queue', '')
    if queue == 'needs_separation':
        queryset = queryset.filter(status='paid')
    elif queue == 'ready':
        queryset = queryset.filter(status='ready_to_ship')
    elif queue == 'no_tracking':
        queryset = queryset.filter(status__in=['preparing', 'ready_to_ship', 'shipped'], tracking_code='')
    elif queue == 'in_transit':
        queryset = queryset.filter(status='shipped')
    elif queue == 'attention':
        queryset = queryset.filter(Q(payment_status='link_creation_uncertain') | Q(cancellation_requested_at__isnull=False, status__in=['pending_payment','paid','preparing','ready_to_ship']))
    else:
        queue = ''
    query = request.GET.get('q', '').strip()[:100]
    queryset = search_orders(queryset, query, request.user.has_perm('store.view_customerprofile'))
    sort = request.GET.get('sort', 'new')
    choices = {'new':'-created_at', 'old':'created_at', 'largest':'-total', 'smallest':'total', 'status':'status'}
    queryset = queryset.order_by(choices.get(sort, '-created_at'), '-id')
    if sort not in choices: sort='new'
    return queryset, dict(period=period, status=status, queue=queue, query=query,
                          start_date=start_date, end_date=end_date, sort=sort)


@staff_member_required
@require_GET
def orders(request):
    if not can_view(request.user):
        return HttpResponseForbidden('Perfil sem permissão para visualizar pedidos.')
    queryset, filters = filtered_orders(request)
    counts = queryset.aggregate(total_orders=Count('id'), order_amount=Sum('total'))
    context = {**filters,
        'total_orders':counts['total_orders'],
        'filtered_order_amount':counts['order_amount'] or 0,
        'page': Paginator(queryset.select_related('user').prefetch_related('items'), 20).get_page(request.GET.get('page')),
        'statuses':Order.STATUSES,
        'can_edit_orders':can_edit(request.user),
    }
    params = request.GET.copy()
    params.pop('page',None)
    context['filter_query'] = params.urlencode()
    return render(request, 'store/operations/orders.html', context)


def existing_legacy_phone(order):
    if order.contact_phone:
        return order.contact_phone
    phone = re.search(r'^Telefone:\s*(.{8,20})$', order.address or '', re.M)
    return phone.group(1) if phone else ''


@staff_member_required
@require_GET
def order_detail(request, order_id):
    if not can_view(request.user):
        return HttpResponseForbidden('Perfil sem permissão para visualizar pedidos.')
    order = get_object_or_404(Order.objects.select_related('user').prefetch_related('items', 'history__actor'),pk=order_id)
    profile = (CustomerProfile.objects.filter(user_id=order.user_id).first()
               if request.user.has_perm('store.view_customerprofile') else None)
    context = {
        'order':order,
        'phone':existing_legacy_phone(order),
        'profile':profile,
        'can_edit_orders':can_edit(request.user),
        'shipping_form':ShippingUpdateForm(initial={
            'tracking_carrier':order.tracking_carrier, 'tracking_code':order.tracking_code,
            'tracking_url':order.tracking_url, 'estimated_delivery':order.estimated_delivery,
        }),
        'back_query':(request.GET.get('back','')[:300] if request.GET.get('back','') else ''),
    }
    return render(request, 'store/operations/order_detail.html', context)


@staff_member_required
@require_POST
def order_update(request, order_id):
    if not can_edit(request.user):
        return HttpResponseForbidden('Perfil sem permissão para alterar pedidos.')
    get_object_or_404(Order, pk=order_id)
    operation = request.POST.get('action', '')
    return_url = reverse('operations_order_detail', args=[order_id])
    if operation == 'transition':
        target = request.POST.get('next_status', '')
        if target not in ('preparing','ready_to_ship','shipped','delivered'):
            messages.error(request,'Etapa operacional inválida.')
        else:
            try:
                changed = transition_order(order_id, target, actor=request.user)
                messages.success(request,'Etapa atualizada e registrada no histórico.' if changed else 'Pedido já está nessa etapa.')
            except ValueError as exc:
                messages.error(request,str(exc))
        return redirect(return_url)
    if operation == 'shipping':
        form = ShippingUpdateForm(request.POST)
        if not form.is_valid():
            for errors in form.errors.values():
                for message in errors: messages.error(request,message)
            return redirect(return_url)
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
            if order.status in ('cancelled','refunded'):
                messages.error(request,'Pedido encerrado: dados de envio não podem ser alterados.')
                return redirect(return_url)
            if order.status in ('shipped','delivered') and not (form.cleaned_data['tracking_carrier'] and form.cleaned_data['tracking_code']):
                messages.error(request,'Não retire transportadora ou código de um pedido já despachado.')
                return redirect(return_url)
            changed_fields=[]
            for field, value in form.cleaned_data.items():
                if getattr(order,field) != value:
                    setattr(order,field,value)
                    changed_fields.append(field)
            if changed_fields:
                order.save(update_fields=changed_fields + ['updated_at'])
                OrderEvent.objects.create(order=order,event='shipping.updated',actor=request.user,
                    details='Campos logísticos atualizados: ' + ', '.join(changed_fields))
                messages.success(request,'Envio atualizado e mudança auditada.')
            else:
                messages.info(request,'Nenhuma informação foi modificada.')
        return redirect(return_url)
    if operation == 'notes':
        content = (request.POST.get('notes','') or '').strip()
        if len(content) > 4000:
            messages.error(request, 'Observação excede 4.000 caracteres.')
            return redirect(return_url)
        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(),pk=order_id)
            if order.notes != content:
                order.notes = content
                order.save(update_fields=['notes','updated_at'])
                OrderEvent.objects.create(order=order, event='order.notes_updated',actor=request.user,
                                          details='Observação interna atualizada (conteúdo restrito).')
        messages.success(request,'Observações registradas.')
        return redirect(return_url)
    messages.error(request,'Ação desconhecida.')
    return redirect(return_url)
