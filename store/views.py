from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum, Count, Prefetch
from django.views.decorators.http import require_http_methods, require_GET
from django.utils import timezone
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .cart import add_to_cart, set_quantity, cart_lines
from .forms import RegisterForm
from .models import Category, Product, ProductVariant, ProductImage, Order


def home(request):
    products = Product.objects.filter(active=True, is_demo=False).select_related('category').prefetch_related('variants', Prefetch('gallery', queryset=ProductImage.objects.defer('photo_data')))
    categories = Category.objects.filter(active=True)
    collections = (Product.objects.filter(active=True,is_demo=False)
                   .exclude(collection='').values_list('collection', flat=True).distinct()[:12])
    category_slug = request.GET.get('categoria','').strip()
    query = request.GET.get('q','').strip()[:80]
    if category_slug:
        products = products.filter(category__slug=category_slug)
    colecao = request.GET.get('colecao','').strip()[:100]
    if colecao:
        products = products.filter(collection__iexact=colecao)
    if query:
        from django.db.models import Q
        products = products.filter(Q(name__icontains=query)|Q(description__icontains=query)|Q(collection__icontains=query))
    return render(request,'store/home.html',{'products':products,'categories':categories,'selected_category':category_slug,'search':query,'selected_collection':colecao,'collections':collections})


def detail(request, slug):
    product = get_object_or_404(Product.objects.prefetch_related('variants', Prefetch('gallery', queryset=ProductImage.objects.defer('photo_data'))),slug=slug,active=True,is_demo=False)
    variants = product.variants.filter(active=True)
    return render(request,'store/product.html',{'product':product,'variants':variants})

@require_POST
def cart_add(request):
    variant_id = request.POST.get('variant_id')
    try:
        quantity = int(request.POST.get('quantity','1'))
    except ValueError:
        return HttpResponseBadRequest('Quantidade inválida')
    if not variant_id or not str(variant_id).isdigit() or quantity < 1 or quantity > 99:
        return HttpResponseBadRequest('Variação ou quantidade inválida')
    variant = get_object_or_404(ProductVariant.objects.select_related('product'),id=int(variant_id),active=True,product__active=True,product__is_demo=False)
    # No pagamento, estoque deve ser verificado novamente dentro de transação.
    current = int(request.session.get('lefi_cart_v1',{}).get(str(variant.id),0))
    if variant.product.one_of_one and current + quantity > 1:
        messages.error(request, 'Peça única: somente uma unidade por pedido.')
        return redirect(variant.product.get_absolute_url())
    if current + quantity > variant.stock:
        messages.error(request,'Não há unidades suficientes deste produto no estoque.')
        return redirect(variant.product.get_absolute_url())
    add_to_cart(request,variant.id,quantity)
    messages.success(request,'Produto adicionado ao carrinho!')
    return redirect('cart')


def cart(request):
    lines, total, count = cart_lines(request)
    shipping = fixed_shipping_amount()
    return render(request, 'store/cart.html', {
        'lines': lines,
        'total': total,
        'count': count,
        'shipping': shipping,
        'shipping_configured': shipping is not None,
        'total_with_shipping': total + shipping if shipping is not None else None,
    })

@require_POST
def cart_update(request):
    try:
        variant_id = int(request.POST.get('variant_id',''))
        quantity = int(request.POST.get('quantity',''))
    except ValueError: return HttpResponseBadRequest('Parâmetros inválidos')
    if quantity > 99 or quantity < 0: return HttpResponseBadRequest('Quantidade inválida')
    set_quantity(request,variant_id,quantity)
    return redirect('cart')


@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated: return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session['signup_details'] = dict(form.cleaned_data)
        request.session['signup_time'] = timezone.now().timestamp()
        return redirect('register_password')
    return render(request, 'store/register.html', {'form':form})


@require_http_methods(['GET', 'POST'])
def register_password(request):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.forms import SetPasswordForm
    from django.db import IntegrityError
    from .models import CustomerProfile
    if request.user.is_authenticated: return redirect('home')
    details = request.session.get('signup_details')
    if not details or timezone.now().timestamp() - request.session.get('signup_time', 0) > 1800:
        request.session.pop('signup_details', None)
        return redirect('register')
    user = get_user_model()(username='cliente_' + uuid.uuid4().hex,
                           first_name=details['first_name'], email=details['email'])
    form = SetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        check = RegisterForm(details)
        if not check.is_valid():
            return render(request, 'store/register.html', {'form':check})
        try:
            with transaction.atomic():
                form.save()
                CustomerProfile.objects.create(user=user, cpf=details['cpf'], email=details['email'])
        except IntegrityError:
            form.add_error(None, 'CPF ou e-mail já cadastrado. Volte ao cadastro ou acesse sua conta.')
        else:
            request.session.pop('signup_details', None)
            request.session.pop('signup_time', None)
            login(request, user, backend='store.backends.EmailOrUsernameBackend')
            messages.success(request, 'Sua conta LEFI foi criada! Entre sempre com seu e-mail.')
            return redirect('cart' if request.session.get(CART_KEY) else 'profile')
    return render(request, 'store/register_password.html', {'form':form})

@login_required
def profile(request):
    orders=Order.objects.filter(user=request.user)[:30]
    return render(request,'store/profile.html',{'orders':orders})


@login_required
@require_GET
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related('items', 'history'), pk=order_id, user=request.user)
    return render(request, 'store/order_detail.html', {'order':order})


@login_required
@require_POST
def order_cancellation_request(request, order_id):
    from .order_workflow import request_cancellation
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    try:
        if request_cancellation(order, request.user, request.POST.get('reason','')):
            messages.success(request, 'Solicitação registrada. A equipe LEFI vai conferir o pagamento e a situação do envio.')
        else:
            messages.info(request, 'Sua solicitação já havia sido recebida.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('order_detail', order_id=order_id)


def checkout(request):
    return redirect('payment_checkout')

@staff_member_required
@require_http_methods(['GET', 'POST'])
def dashboard(request):
    """Painel visual de operação: não confundir pedidos com faturamento liquidado."""
    if request.method == 'POST':
        if not request.user.has_perm('store.change_product'):
            return HttpResponse(status=403)
        action = request.POST.get('action', '')
        if action == 'archive_demos':
            updated = Product.objects.filter(is_demo=True, active=True).update(active=False, featured=False)
            messages.success(request, f'{updated} produto(s) fictício(s) retirado(s) da vitrine. Nenhum pedido foi apagado.')
        else:
            messages.error(request, 'Ação administrativa não reconhecida.')
        return redirect('dashboard')

    if not request.user.has_perm('store.view_order'):
        return HttpResponse('Seu perfil precisa da permissão de visualizar pedidos.', status=403)
    from .analytics import dashboard_context
    return render(request, 'store/dashboard.html', dashboard_context(request))



@require_http_methods(['GET'])
def product_image(request, image_id):
    """Serve arquivo WebP realmente enviado. Nunca depende de disco temporário."""
    photo = get_object_or_404(ProductImage.objects.select_related('product').only('photo_data', 'has_upload', 'product__active'), pk=image_id, has_upload=True)
    # Admin pode conferir fotos enquanto cadastra produtos ainda não publicados.
    if not photo.product.active and not request.user.is_staff:
        raise Http404('Foto não publicada')
    if not photo.photo_data:
        raise Http404('Foto não encontrada')
    response = HttpResponse(bytes(photo.photo_data), content_type='image/webp')
    response['Cache-Control'] = 'public, max-age=300'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def como_comprar(request):
    return render(request, 'store/como_comprar.html')

def manifesto(request):
    return render(request, 'store/manifesto.html')

def atelie(request):
    return render(request, 'store/atelie.html')


def health(request):
    return HttpResponse('ok',content_type='text/plain')

# ---------------- InfinitePay Checkout Integrado ----------------
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from .cart import CART_KEY
from .checkout_forms import CheckoutForm
from .models import OrderItem
from .infinitepay import create_payment_link, InfinitePayError, verify_and_apply, order_reference


def fixed_shipping_amount():
    """Obtém o frete fixo, independentemente de o pagamento estar habilitado."""
    try:
        fixed = Decimal(str(settings.LEFI_SHIPPING_FLAT).replace(',', '.')).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not fixed.is_finite() or fixed < 0 or fixed > 1000:
        return None
    return fixed


def checkout_ready():
    fixed = fixed_shipping_amount()
    ready = (fixed is not None and bool(settings.INFINITEPAY_API_KEY)
             and bool(settings.INFINITEPAY_TAG) and settings.LEFI_CHECKOUT_ENABLED)
    return bool(ready), fixed


@login_required
def payment_checkout(request):
    lines, subtotal, count = cart_lines(request)
    ready, shipping = checkout_ready()
    if not lines:
        messages.error(request, 'Seu carrinho está vazio.')
        return redirect('cart')
    manual = not ready and settings.LEFI_ACCEPT_MANUAL_ORDERS and shipping is not None
    if not ready and not manual:
        return render(request, 'store/checkout.html', {'configured': False, 'lines':lines, 'total':subtotal, 'shipping':shipping, 'shipping_configured':shipping is not None, 'total_with_shipping':subtotal + shipping if shipping is not None else None})
    product_quantities = {}
    for row in lines:
        product_quantities[row['product'].pk] = product_quantities.get(row['product'].pk, 0) + row['quantity']
    if any(row['product'].one_of_one and product_quantities[row['product'].pk] > 1 for row in lines):
        messages.error(request, 'Uma peça de edição única não pode ser comprada mais de uma vez no mesmo pedido.')
        return redirect('cart')
    if any(not x['available'] or x['product'].is_demo for x in lines):
        messages.error(request, 'Confira o estoque. Produtos de demonstração não podem ser vendidos.')
        return redirect('cart')
    if not request.session.get('lefi_checkout_nonce'):
        request.session['lefi_checkout_nonce'] = uuid.uuid4().hex
    initial = {'full_name': request.user.get_full_name() or request.user.username, 'email': request.user.email}
    form = CheckoutForm(request.POST or None, initial=initial)
    grand_total = subtotal + shipping
    if request.method == 'POST' and form.is_valid():
        nonce = request.POST.get('nonce', '')
        if not nonce or nonce != request.session.get('lefi_checkout_nonce'):
            messages.error(request, 'Recarregue o checkout para confirmar seu pedido.')
            return redirect('payment_checkout')
        # HTTP externo sempre fora da transação; reserva de estoque com row locks no PostgreSQL.
        order = None
        with transaction.atomic():
            # Bloqueio por cliente + nonce para impedir dupla reserva em POST simultâneo.
            from django.contrib.auth import get_user_model
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            existing = Order.objects.filter(checkout_nonce=nonce).first()
            if existing:
                messages.warning(request, 'Esse pedido já está registrado. Confira a situação antes de tentar novamente.')
                return redirect('payment_return', order_id=existing.pk)
            ids = sorted(x['variant'].pk for x in lines)
            locked = {v.pk: v for v in ProductVariant.objects.select_for_update().select_related('product').filter(pk__in=ids)}
            current_lines = []
            for row in lines:
                variant = locked.get(row['variant'].pk)
                if not variant or not variant.active or not variant.product.active or variant.product.is_demo or variant.stock < row['quantity']:
                    messages.error(request, 'Um produto ficou indisponível. Atualize seu carrinho.')
                    return redirect('cart')
                current_lines.append((variant, row['quantity'], variant.product.effective_price))
            real_subtotal = sum((p * qty for v, qty, p in current_lines), Decimal('0'))
            order = Order.objects.create(user=request.user, checkout_nonce=nonce,
                customer_name=form.cleaned_data['full_name'], contact_email=form.cleaned_data['email'],
                address=f"Telefone: {form.cleaned_data['phone']}\n{form.cleaned_address()}",
                shipping_city=form.cleaned_data['city'], shipping_state=form.cleaned_data['state'],
                contact_phone=form.cleaned_data['phone'],
                shipping_postal_code=form.cleaned_data['postal_code'],
                shipping_street=form.cleaned_data['street'],
                shipping_number=form.cleaned_data['number'],
                shipping_complement=form.cleaned_data['complement'],
                shipping_neighborhood=form.cleaned_data['neighborhood'],
                shipping_reference=form.cleaned_data['reference'],
                shipping_amount=shipping, total=real_subtotal + shipping,
                payment_status='manual_pending' if manual else 'awaiting_payment', stock_reserved=True,
                payment_expires_at=timezone.now() + timedelta(minutes=30))
            for variant, qty, price in current_lines:
                ProductVariant.objects.filter(pk=variant.pk).update(stock=F('stock')-qty)
                OrderItem.objects.create(order=order, variant=variant,
                    description=f'{variant.product.name} — {variant.color}, {variant.size}',
                    sku=variant.sku, quantity=qty, unit_price=price)
            from .models import OrderEvent
            from .notifications import queue_order_email
            OrderEvent.objects.create(order=order, event='order.created', details='Pedido registrado; pagamento pendente.')
            queue_order_email(order, 'order.created')
        request.session.pop('lefi_checkout_nonce', None)
        request.session.pop(CART_KEY, None)
        if manual:
            messages.success(request, 'Pedido registrado! A loja fará contato para combinar o pagamento. Nenhuma cobrança foi realizada.')
            return redirect('payment_return', order_id=order.pk)
        try:
            base_url = request.build_absolute_uri('/').rstrip('/')
            pref_id, redirect_url = create_payment_link(order, base_url)
        except InfinitePayError:
            # Um timeout não comprova que a InfinitePay NÃO criou o link.
            # Preserva-se a reserva para conferência manual: não duplicar venda de SKU.
            Order.objects.filter(pk=order.pk, status='pending_payment').update(payment_status='link_creation_uncertain',updated_at=timezone.now())
            messages.error(request, 'Não foi possível confirmar a criação do pagamento. Pedido em revisão; nenhuma nova cobrança será iniciada automaticamente.')
            return redirect('payment_return', order_id=order.pk)
        order.gateway_preference_id = pref_id
        order.gateway_checkout_url = redirect_url
        order.save(update_fields=['gateway_preference_id', 'gateway_checkout_url','updated_at'])
        OrderEvent.objects.create(order=order, event='payment.link_created', details='Link InfinitePay criado')
        request.session.pop(CART_KEY, None)
        return redirect(redirect_url)
    return render(request, 'store/checkout.html',
                  {'configured': True, 'lines': lines, 'subtotal': subtotal,
                   'shipping': shipping, 'total': grand_total,
                   'form': form, 'nonce': request.session['lefi_checkout_nonce'],
                   'checkout_provider':'InfinitePay', 'manual':manual})


@login_required
@require_GET
def payment_return(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    # Nunca confiar somente em parâmetros de retorno. Consulta autenticada à InfinitePay.
    transaction_nsu = request.GET.get('transaction_nsu', '')
    slug = request.GET.get('slug', '')
    order_nsu = request.GET.get('order_nsu', '')
    if order_nsu == order_reference(order.pk) and transaction_nsu and slug:
        try:
            verify_and_apply(order.pk, transaction_nsu, slug)
            order.refresh_from_db()
        except InfinitePayError:
            pass  # O webhook/reconciliação poderá confirmar posteriormente.
    return render(request, 'store/payment_return.html', {'order': order})


@csrf_exempt
@require_POST
def payment_webhook(request):
    # Não confiar no corpo: validar pagamento via API autenticada antes de qualquer alteração.
    if len(request.body) > 16000:
        return HttpResponse(status=413)
    try:
        import json
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)
    if not isinstance(payload, dict):
        return HttpResponse(status=400)
    nsu = payload.get('order_nsu', '')
    transaction_nsu = payload.get('transaction_nsu', '')
    slug = payload.get('slug') or payload.get('invoice_slug')
    if not (isinstance(nsu, str) and nsu.startswith('LEFI-') and nsu[len('LEFI-'):].isdecimal()):
        return HttpResponse(status=400)
    if not (isinstance(transaction_nsu, str) and isinstance(slug, str)):
        return HttpResponse(status=400)
    if not (0 < len(transaction_nsu) <= 160 and 0 < len(slug) <= 160):
        return HttpResponse(status=400)
    try:
        confirmed = verify_and_apply(int(nsu[len('LEFI-'):]), transaction_nsu, slug)
    except InfinitePayError:
        return HttpResponse(status=503)
    # 200 para eventos que não representam aprovação; nada é marcado pago sem confirmação.
    return HttpResponse(status=200)


@require_GET
def politica_entrega(request):
    return render(request, 'store/politica_entrega.html')

@require_GET
def trocas_devolucoes(request):
    return render(request, 'store/trocas_devolucoes.html')

@require_GET
def politica_privacidade(request):
    return render(request, 'store/politica_privacidade.html')

@require_GET
def atendimento(request):
    return render(request, 'store/atendimento.html')

# Central profissional de operações (autenticação, transições e dados reais).
from . import operations
operations_orders = operations.orders
operations_order_detail = operations.order_detail
operations_order_update = operations.order_update
