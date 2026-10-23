"""Cabeçalho e carrinho devem contar apenas produtos ainda existentes."""
from .cart import cart_lines


def cart_summary(request):
    _lines, _total, count = cart_lines(request)
    return {'cart_count': count}



def storefront_information(request):
    from .models import StoreInformation
    return {'store_info': StoreInformation.objects.order_by('pk').first()}
