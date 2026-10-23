from datetime import timedelta
from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from .models import Order, ProductVariant, EmailNotification

PAID = ('paid', 'preparing', 'ready_to_ship', 'shipped', 'delivered')
# Distribuição esquemática das UFs; não representa endereços ou limites geográficos.
TILES = [('RR',2,1),('AP',6,1),('AM',2,2),('PA',5,2),('MA',7,2),('CE',9,2),('RN',10,2),
         ('AC',1,3),('RO',2,3),('MT',4,3),('TO',6,3),('PI',7,3),('PE',9,3),('PB',10,3),
         ('MS',4,5),('GO',5,4),('DF',6,4),('BA',7,4),('SE',9,4),('AL',10,4),
         ('SP',5,6),('MG',6,5),('ES',8,5),('RJ',7,6),('PR',4,6),('SC',4,7),('RS',3,8)]

def dashboard_context(request):
    days = request.GET.get('period', '30')
    if days not in ('7','30','90','all'): days='30'
    orders = Order.objects.all()
    if days != 'all':
        start = timezone.localdate() - timedelta(days=int(days)-1)
        orders = orders.filter(created_at__date__gte=start)
    status = request.GET.get('status','')
    if status in dict(Order.STATUSES): orders=orders.filter(status=status)
    else: status=''
    query = request.GET.get('q','').strip()[:100]
    if query:
        search = (Q(customer_name__icontains=query) | Q(contact_email__icontains=query) |
                  Q(contact_phone__icontains=query) | Q(tracking_code__icontains=query))
        number=query.lstrip('#')
        if number.isascii() and number.isdigit() and len(number) <= 19 and int(number) <= 2**63-1:
            search |= Q(pk=int(number))
        orders=orders.filter(search)
    paid = orders.filter(status__in=PAID)
    amount = paid.aggregate(total=Sum('total'))['total'] or Decimal('0')
    paid_count = paid.count()
    states = list(paid.values('shipping_state').annotate(count=Count('pk'),total=Sum('total')).order_by('-count'))
    lookup = {r['shipping_state']:r for r in states}
    peak = max([r['count'] for r in states] or [1])
    tiles = [dict(uf=uf,x=x,y=y,count=lookup.get(uf,{}).get('count',0),
                  level=round(lookup.get(uf,{}).get('count',0)/peak*70)+15) for uf,x,y in TILES]
    daily = {r['day']:r['count'] for r in orders.filter(created_at__date__gte=timezone.localdate()-timedelta(days=13))
             .annotate(day=TruncDate('created_at')).values('day').annotate(count=Count('pk')).order_by()}
    maximum = max(daily.values(), default=1) or 1
    trend=[]
    for offset in range(13,-1,-1):
        day=timezone.localdate()-timedelta(days=offset); count=daily.get(day,0)
        trend.append({'day':day,'count':count,'height':max(2,round(count/maximum*100))})
    params=request.GET.copy(); params.pop('page',None)
    from .views import checkout_ready
    ready, shipping = checkout_ready()
    return dict(period=days,status=status,query=query,statuses=Order.STATUSES,
        orders_count=orders.count(),pending_count=orders.filter(status='pending_payment').count(),
        paid_count=paid_count,paid_order_amount=amount,ticket=amount/paid_count if paid_count else 0,
        to_separate=orders.filter(status='paid').count(),
        in_preparation=orders.filter(status='preparing').count(),
        ready_to_ship=orders.filter(status='ready_to_ship').count(),
        in_transit=orders.filter(status='shipped').count(),
        delivered=orders.filter(status='delivered').count(),
        cancelled=orders.filter(status='cancelled').count(),
        overdue=orders.filter(status='shipped',estimated_delivery__lt=timezone.localdate()).count(),
        page=Paginator(orders.select_related('user'),15).get_page(request.GET.get('page')),
        filter_query=params.urlencode(),states=states,tiles=tiles,trend=trend,
        unknown_state=lookup.get('',{}).get('count',0),
        low_stock=ProductVariant.objects.select_related('product').filter(active=True,product__active=True,product__is_demo=False,stock__lte=3).order_by('stock')[:8],
        uncertain=Order.objects.filter(payment_status='link_creation_uncertain').count(),
        email_errors=EmailNotification.objects.filter(status='error').count(),
        checkout_ready=ready,shipping_configured=shipping is not None,
        cancellations=Order.objects.filter(cancellation_requested_at__isnull=False,status__in=('pending_payment',*PAID)).count())
