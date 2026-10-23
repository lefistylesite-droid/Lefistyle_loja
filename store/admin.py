from django.http import HttpResponseForbidden
"""Admin LEFI: gerenciamento seguro e claro para catálogo e pedidos."""
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.html import format_html
from .photo_forms import ProductPhotoForm

from .infinitepay import release_abandoned_after_manual_confirmation
from .models import Category, Product, ProductVariant, ProductImage, Order, OrderItem, StoreInformation, OrderEvent, EmailNotification
from .order_workflow import transition_order
from .notifications import send_notice


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('active',)
    search_fields = ('name',)


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('sku', 'size', 'color', 'color_hex', 'stock', 'active')
    verbose_name_plural = 'Tamanho e acabamento — estoque por peça/SKU'


class ImageInline(admin.StackedInline):
    model = ProductImage
    form = ProductPhotoForm
    extra = 2
    fields = ('upload', 'preview', 'alt', 'position')
    readonly_fields = ('preview',)
    verbose_name_plural = 'Fotos reais — adicione quantas precisar (primeira posição vira a capa)'

    def preview(self, obj):
        if obj and obj.pk and obj.public_url:
            return format_html('<img src="{}" alt="Foto do produto" style="max-width:110px;max-height:130px;border-radius:8px">', obj.public_url)
        return 'Sem foto ainda'
    preview.short_description = 'Visualização'



@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name','category','collection','creation_type','one_of_one','effective_price_display','is_demo','active','featured','stock_quantity')
    list_filter = ('category','creation_type','one_of_one','active','featured','is_demo')
    list_editable = ('active', 'featured')
    list_per_page = 30
    search_fields = ('name','slug','collection','materials','variants__sku')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [VariantInline, ImageInline]
    actions = ('archive_selected', 'activate_real_products', 'remove_demos_safely')
    fieldsets = (
        ('Identificação e coleção', {'fields': ('category', 'name', 'slug', 'collection', 'description')}),
        ('Criação e autenticidade', {'fields': ('creation_type','one_of_one','materials','artistic_process','origin_story','conservation','measurements','care_instructions'), 'description':'Descreva materiais e procedência com precisão. Não atribua parceria, autenticação ou endosso de outras marcas sem comprovação.'}),
        ('Preço e exposição', {'fields': ('price', 'sale_price', 'cost_price')}),
        ('Publicação', {'fields': ('active', 'featured', 'is_demo'),
                        'description': 'Cadastre fotos no fim da página, em GALERIA DE FOTOS. A menor posição é usada como capa. Publique quando estiver pronto.'}),
    )

    @admin.display(description='Preço de venda')
    def effective_price_display(self, obj):
        return f'R$ {obj.effective_price:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    @admin.display(description='Estoque')
    def stock_quantity(self, obj):
        return obj.stock_total

    @admin.action(description='Arquivar selecionados (sumir da vitrine, preservar pedidos)')
    def archive_selected(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, 'Sem permissão para arquivar produtos.', messages.ERROR)
            return
        changed = queryset.update(active=False, featured=False)
        self.message_user(request, f'{changed} produto(s) arquivado(s). O histórico foi preservado.', messages.SUCCESS)

    @admin.action(description='Publicar selecionados que NÃO são fictícios')
    def activate_real_products(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, 'Sem permissão.', messages.ERROR)
            return
        changed = queryset.filter(is_demo=False).update(active=True)
        self.message_user(request, f'{changed} produto(s) real(is) ativado(s). Confira fotos, preços e estoque.', messages.SUCCESS)

    @admin.action(description='Excluir fictícios selecionados (com confirmação)')
    def remove_demos_safely(self, request, queryset):
        if not self.has_delete_permission(request):
            self.message_user(request, 'Sem permissão para excluir produtos.', messages.ERROR)
            return
        candidates = queryset.filter(is_demo=True).order_by('pk')
        if request.POST.get('delete_demos_confirm') != 'EXCLUIR FICTICIOS':
            return TemplateResponse(request, 'admin/store/product/confirm_delete_demos.html', {
                **self.admin_site.each_context(request),
                'title': 'Exclusão cuidadosa de produtos fictícios',
                'products': candidates,
                'opts': self.model._meta,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                'action_name': 'remove_demos_safely',
            })
        removed = candidates.count()
        candidates.delete()  # Pedidos históricos permanecem como snapshot, sem variação vinculada.
        self.message_user(request, f'{removed} produto(s) fictício(s) excluído(s) do cadastro, incluindo suas fotos.', messages.SUCCESS)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ('variant', 'description', 'sku', 'quantity', 'unit_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'open_operations', 'customer_name', 'status', 'payment_status', 'cancel_requested', 'tracking_carrier', 'tracking_code', 'total', 'created_at')
    list_select_related = ('user',)
    list_filter = ('status', 'stock_reserved', 'created_at')
    actions = ['confirm_manual_payment', 'cancel_manual_order', 'release_after_verified_unpaid', 'mark_preparing', 'mark_shipped', 'mark_delivered', 'mark_refunded_after_verification']
    list_per_page = 30

    @admin.action(description='Pedido MANUAL: registrar recebimento já conferido')
    def confirm_manual_payment(self, request, queryset):
        return self.manual_resolution(request, queryset, 'paid', 'confirm_manual_payment')

    @admin.action(description='Pedido MANUAL: cancelar sem cobrança e devolver estoque')
    def cancel_manual_order(self, request, queryset):
        return self.manual_resolution(request, queryset, 'cancelled', 'cancel_manual_order')

    def manual_resolution(self, request, queryset, operation, action):
        from .manual_orders import resolve_manual_order
        if not self.has_change_permission(request):
            return HttpResponseForbidden()
        if queryset.count() != 1:
            self.message_user(request, 'Selecione exatamente um pedido.', level=messages.ERROR)
            return
        if request.POST.get('confirmation') != 'CONFIRMAR':
            return TemplateResponse(request, 'admin/store/order/manual_confirmation.html', {
                **self.admin_site.each_context(request), 'title':'Conferência de pedido manual',
                'orders':queryset, 'action_checkbox_name':helpers.ACTION_CHECKBOX_NAME,
                'action_name':action, 'operation':operation, 'opts':self.model._meta})
        try:
            resolve_manual_order(queryset.get().pk, request.user, operation, request.POST.get('reference',''))
            self.message_user(request, 'Pedido atualizado e histórico registrado.', level=messages.SUCCESS)
        except ValueError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)

    @admin.display(boolean=True, description='Cancelamento solicitado')
    def cancel_requested(self,obj):
        return bool(obj.cancellation_requested_at)

    @admin.action(description='Marcar como EM PREPARAÇÃO (somente pedidos pagos)')
    def mark_preparing(self, request, queryset):
        self._do_transition(request, queryset, 'preparing')

    @admin.action(description='Marcar como ENVIADO (preencher rastreio antes)')
    def mark_shipped(self, request, queryset):
        self._do_transition(request, queryset, 'shipped')

    @admin.action(description='Marcar como ENTREGUE (somente enviados)')
    def mark_delivered(self, request, queryset):
        self._do_transition(request, queryset, 'delivered')

    def _do_transition(self, request, queryset, state):
        if not self.has_change_permission(request):
            self.message_user(request, 'Você não possui permissão.', level=messages.ERROR)
            return
        count=0
        for order_id in queryset.values_list('pk', flat=True)[:50]:
            try:
                if transition_order(order_id,state,actor=request.user):count+=1
            except ValueError as exc:
                self.message_user(request, str(exc), level=messages.WARNING)
        self.message_user(request, f'{count} pedido(s) atualizado(s).', level=messages.SUCCESS if count else messages.INFO)

    @admin.action(description='REGISTRAR ESTORNO INTEGRAL já confirmado na InfinitePay')
    def mark_refunded_after_verification(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, 'Você não possui permissão.', level=messages.ERROR)
            return
        ids=list(queryset.values_list('pk',flat=True)[:10])
        if request.POST.get('confirmed_refund') != 'ESTORNO CONFIRMADO NA INFINITEPAY':
            return TemplateResponse(request, 'admin/store/order/confirm_refund.html', {
                **self.admin_site.each_context(request), 'title':'Confirmar estorno já realizado na InfinitePay',
                'orders':queryset[:10], 'action_checkbox_name':helpers.ACTION_CHECKBOX_NAME,
                'action_name':'mark_refunded_after_verification', 'opts':self.model._meta,
            })
        count=0
        for order_id in ids:
            try:
                if transition_order(order_id,'refunded',actor=request.user,provider_verified=True):count+=1
            except ValueError as exc:self.message_user(request,str(exc),level=messages.WARNING)
        self.message_user(request, f'{count} reembolso(s) registrado(s), após conferência externa.', level=messages.INFO)

    @admin.display(boolean=True, description='Reserva expirada')
    def expired_reservation(self, obj):
        return (obj.status == 'pending_payment' and obj.stock_reserved and
                obj.payment_expires_at is not None and obj.payment_expires_at <= timezone.now())

    @admin.action(description='Cancelar e repor estoque SOMENTE após conferir não pagamento na InfinitePay')
    def release_after_verified_unpaid(self, request, queryset):
        if not self.has_change_permission(request):
            self.message_user(request, 'Você não possui permissão.', level=messages.ERROR)
            return
        ids = list(queryset.values_list('pk', flat=True))
        if not ids or len(ids) > 10:
            self.message_user(request, 'Selecione de 1 a 10 pedidos.', level=messages.ERROR)
            return
        if request.POST.get('confirmed_unpaid') != 'CONFERI NA INFINITEPAY':
            return TemplateResponse(request, 'admin/store/order/confirm_release.html', {
                **self.admin_site.each_context(request),
                'title': 'Confirmação manual da InfinitePay — ação irreversível',
                'orders': queryset,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                'action_name': 'release_after_verified_unpaid',
                'opts': self.model._meta,
            })
        count = 0
        for order_id in ids:
            try:
                if release_abandoned_after_manual_confirmation(order_id, staff_user=request.user, provider_checked=True):
                    count += 1
            except ValueError as exc:
                self.message_user(request, f'Pedido #{order_id}: {exc}', level=messages.WARNING)
        self.message_user(request, f'{count} reserva(s) devolvida(s) após conferência manual.', level=messages.INFO)

    @admin.display(description='Operação')
    def open_operations(self, obj):
        from django.urls import reverse
        return format_html('<a href="{}">Ver pedido completo ↗</a>', reverse('operations_order_detail', args=[obj.pk]))

    search_fields = ('=id', 'customer_name', 'user__email', 'contact_email', 'contact_phone', 'tracking_code', 'gateway_payment_id')
    readonly_fields = ('user', 'created_at', 'updated_at', 'total', 'shipping_amount', 'customer_name', 'contact_email', 'address', 'gateway_payment_id', 'gateway_preference_id', 'gateway_checkout_url', 'checkout_nonce', 'payment_status', 'stock_reserved', 'paid_at', 'payment_expires_at', 'status', 'cancellation_requested_at', 'refund_confirmed_at')
    inlines = [OrderItemInline]
    fieldsets = (
        ('Pedido e cliente',{'fields':('user','created_at','updated_at','status','payment_status','total','shipping_amount','customer_name','contact_email','contact_phone','address','shipping_postal_code','shipping_street','shipping_number','shipping_complement','shipping_neighborhood','shipping_city','shipping_state','shipping_reference')}),
        ('Acompanhamento e envio',{'fields':('tracking_carrier','tracking_code','tracking_url','shipped_at','estimated_delivery','delivered_at','cancellation_requested_at','cancellation_reason','notes')}),
        ('Pagamento InfinitePay — somente leitura',{'fields':('gateway_payment_id','gateway_preference_id','gateway_checkout_url','checkout_nonce','stock_reserved','paid_at','payment_expires_at','refund_confirmed_at')}),
    )

    def save_model(self, request, obj, form, change):
        # Mudanças realizadas pelo Django Admin também ficam no histórico.
        changed = list(form.changed_data) if change else []
        super().save_model(request, obj, form, change)
        if change and changed:
            OrderEvent.objects.create(order=obj,actor=request.user,event='order.admin_updated',
                details='Campos alterados via Django Admin: ' + ', '.join(changed))

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'size', 'color', 'stock', 'active')
    list_editable = ('stock', 'active')
    list_filter = ('size', 'color', 'active')
    search_fields = ('sku', 'product__name')


@admin.register(StoreInformation)
class StoreInformationAdmin(admin.ModelAdmin):
    """Uma configuração pública por loja. Nenhum token ou segredo aqui."""
    fieldsets = (
        ('Marca e identificação comercial', {'fields':('brand_name','legal_name','tax_id','business_address'),
            'description':'Preencha os dados reais da empresa antes de divulgar a loja. Não invente CNPJ ou endereço.'}),
        ('Atendimento', {'fields':('contact_email','contact_phone','service_hours','instagram_url','privacy_email','shopee_url','tiktok_shop_url'),
            'description':'WhatsApp no padrão internacional: 55 + DDD + número, sem espaços ou símbolos. Não coloque chaves de API.'}),
        ('Entregas e política de trocas', {'fields':('dispatch_region','shipping_preparation','delivery_estimate','shipping_details','exchange_details'),
            'description':'Informe prazos e procedimentos reais. Estes textos aparecem ao cliente na área de informações.'}),
    )
    def has_add_permission(self, request):
        return super().has_add_permission(request) and not StoreInformation.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return False
    def changelist_view(self, request, extra_context=None):
        existing=StoreInformation.objects.order_by('pk').first()
        if existing and self.has_view_or_change_permission(request, existing):
            from django.shortcuts import redirect
            return redirect('admin:store_storeinformation_change', existing.pk)
        return super().changelist_view(request, extra_context)


@admin.register(OrderEvent)
class OrderEventAdmin(admin.ModelAdmin):
    list_display=('order','event','actor','created_at')
    list_filter=('event','created_at')
    search_fields=('order__id',)
    readonly_fields=('order','event','details','actor','created_at')
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display=('order','event','recipient','status','attempts','created_at','sent_at')
    list_filter=('status','event')
    actions=['retry_delivery']
    readonly_fields=('order','event','recipient','status','attempts','last_error','sent_at','created_at')
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False
    @admin.action(description='Tentar enviar e-mails pendentes (requer integração habilitada)')
    def retry_delivery(self,request,queryset):
        if not self.has_change_permission(request):
            self.message_user(request,'Sem permissão',level=messages.ERROR)
            return
        n=sum(bool(send_notice(pk)) for pk in queryset.exclude(status='sent').values_list('pk',flat=True)[:20])
        self.message_user(request,f'{n} e-mail(s) enviados. Outros permanecem na fila para revisão.',level=messages.INFO)

from .models import CustomerProfile

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'masked_document')
    search_fields = ('email', 'user__first_name')
    readonly_fields = ('user', 'email', 'masked_document')
    fields = readonly_fields
    @admin.display(description='CPF (protegido)')
    def masked_document(self, obj): return obj.masked_cpf
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False


class OrderHistoryInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    can_delete = False
    readonly_fields = ('created_at', 'event', 'details', 'actor')
    fields = readonly_fields
    def has_add_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return False

OrderAdmin.inlines = [OrderItemInline, OrderHistoryInline]
OrderAdmin.search_fields = ('=id', 'customer_name', 'user__email', 'contact_email', 'gateway_payment_id')
OrderAdmin.list_filter = ('status', 'payment_status', 'shipping_state', 'created_at')
