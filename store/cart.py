"""Carrinho por sessão, sincronizado com produtos e variações ativos no banco."""
from decimal import Decimal
from .models import ProductVariant

CART_KEY = 'lefi_cart_v1'
MAX_DB_ID = 2**63 - 1


def get_cart(request):
    items = request.session.get(CART_KEY, {})
    return items if isinstance(items, dict) else {}


def _normalized_items(items):
    """Ignora entradas inválidas/antigas, sem confiar nas quantidades da sessão."""
    normalized = {}
    for raw_id, raw_quantity in items.items():
        if not isinstance(raw_id, str) or not raw_id.isascii() or not raw_id.isdecimal():
            continue
        if isinstance(raw_quantity, bool) or not isinstance(raw_quantity, (int, str)):
            continue
        try:
            variant_id = int(raw_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError, OverflowError):
            continue
        if variant_id <= 0 or variant_id > MAX_DB_ID or quantity <= 0:
            continue
        key = str(variant_id)
        normalized[key] = max(normalized.get(key, 0), min(99, quantity))
    return normalized


def cart_lines(request):
    """Remove da sessão produtos/variações excluídos ou inativos.

    O contador do cabeçalho e a página do carrinho usam esta MESMA fonte,
    impedindo o badge antigo ('1') após limpar produtos fictícios no Admin.
    Não remove produtos meramente sem estoque: o carrinho mostra o aviso correto.
    """
    cached = getattr(request, '_lefi_cart_lines_cache', None)
    if cached is not None:
        return cached

    original = request.session.get(CART_KEY, {})
    candidates = _normalized_items(get_cart(request))
    variants = (
        ProductVariant.objects.select_related('product')
        .filter(pk__in=[int(key) for key in candidates], active=True, product__active=True, product__is_demo=False)
        if candidates else []
    )

    rows, total, count, valid_cart = [], Decimal('0'), 0, {}
    for variant in variants:
        key = str(variant.pk)
        quantity = candidates[key]
        valid_cart[key] = quantity
        price = variant.product.effective_price
        subtotal = price * quantity
        rows.append({'variant': variant, 'product': variant.product, 'quantity': quantity,
                     'subtotal': subtotal, 'available': quantity <= variant.stock})
        total += subtotal
        count += quantity

    # Persistir a limpeza para futuras visitas, após excluir produtos no Admin.
    if original != valid_cart:
        request.session[CART_KEY] = valid_cart
        request.session.modified = True
    result = rows, total, count
    request._lefi_cart_lines_cache = result
    return result


def _invalidate_cache(request):
    if hasattr(request, '_lefi_cart_lines_cache'):
        delattr(request, '_lefi_cart_lines_cache')


def add_to_cart(request, variant_id, quantity):
    # A sessão antiga pode conter referências de produtos já eliminados.
    cart_lines(request)
    cart = get_cart(request).copy()
    key = str(variant_id)
    cart[key] = max(1, min(99, int(cart.get(key, 0)) + quantity))
    request.session[CART_KEY] = cart
    request.session.modified = True
    _invalidate_cache(request)


def set_quantity(request, variant_id, quantity):
    cart = get_cart(request).copy()
    if quantity <= 0:
        cart.pop(str(variant_id), None)
    else:
        cart[str(variant_id)] = min(99, quantity)
    request.session[CART_KEY] = cart
    request.session.modified = True
    _invalidate_cache(request)
