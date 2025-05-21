from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Client, Product, Order, Container, Driver, Region,
    LoyaltyProgram, ClientCategory, LoyaltyTransaction,
    Route, RouteOrder, Notification
)

@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'points_per_liter', 'points_to_money_rate', 'min_points_to_redeem')

@admin.register(ClientCategory)
class ClientCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_percent', 'min_monthly_volume')

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'client_type', 'phone', 'email', 'category', 'loyalty_points', 'total_volume_purchased')
    list_filter = ('client_type', 'category', 'region')
    search_fields = ('name', 'phone', 'email', 'company_name', 'tax_number')
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'phone', 'email', 'client_type')
        }),
        ('Адрес', {
            'fields': ('region', 'address', 'apartment', 'floor', 'entrance')
        }),
        ('Информация о компании', {
            'classes': ('collapse',),
            'fields': ('company_name', 'tax_number', 'contact_person')
        }),
        ('Система лояльности', {
            'fields': ('category', 'loyalty_points', 'total_volume_purchased', 'last_purchase_date')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'registration_date')
        })
    )
    readonly_fields = ('registration_date', 'loyalty_points', 'total_volume_purchased', 'last_purchase_date')

@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('client', 'points', 'transaction_type', 'created_at', 'order_link')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('client__name', 'description')
    readonly_fields = ('created_at',)

    def order_link(self, obj):
        if obj.order:
            url = reverse('admin:crm_order_change', args=[obj.order.id])
            return format_html('<a href="{}">{}</a>', url, f'Заказ #{obj.order.id}')
        return '-'
    order_link.short_description = 'Заказ'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'volume', 'price')
    search_fields = ('name',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'product', 'quantity', 'status', 'payment_type', 
                   'total_amount', 'points_used', 'points_earned', 'order_date')
    list_filter = ('status', 'payment_type', 'order_date', 'driver')
    search_fields = ('client__name', 'product__name', 'delivery_address', 'call_id')
    readonly_fields = ('points_earned', 'delivery_confirmation_preview')
    fieldsets = (
        ('Основная информация', {
            'fields': ('client', 'product', 'quantity', 'status', 'driver')
        }),
        ('Доставка', {
            'fields': ('delivery_address', 'estimated_delivery_time', 'actual_delivery_time', 
                      'delivery_confirmation', 'delivery_confirmation_preview', 'driver_comment')
        }),
        ('Оплата', {
            'fields': ('payment_type', 'payment_amount', 'points_used', 'points_earned',
                      'discount_amount', 'total_amount')
        }),
        ('IP-телефония', {
            'classes': ('collapse',),
            'fields': ('call_id',)
        })
    )

    def delivery_confirmation_preview(self, obj):
        if obj.delivery_confirmation:
            return format_html('<img src="{}" style="max-height: 200px;"/>', obj.delivery_confirmation.url)
        return '-'
    delivery_confirmation_preview.short_description = 'Предпросмотр подтверждения'

@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'client', 'quantity', 'is_at_client', 'last_updated')
    list_filter = ('is_at_client', 'product')
    search_fields = ('client__name', 'product__name')

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'region', 'user', 'active_orders_count')
    search_fields = ('name', 'phone', 'email')
    list_filter = ('region', 'created_at')
    fields = ('name', 'phone', 'email', 'region', 'user', 'created_at')
    readonly_fields = ('created_at',)

    def active_orders_count(self, obj):
        return obj.order_set.filter(status__in=['planned', 'in_progress']).count()
    active_orders_count.short_description = 'Активные заказы'

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'drivers_count', 'active_clients_count')
    search_fields = ('name', 'description')

    def drivers_count(self, obj):
        return obj.driver_set.count()
    drivers_count.short_description = 'Водители'

    def active_clients_count(self, obj):
        return obj.client_set.filter(
            order__status='delivered',
            order__order_date__gte='2025-04-21'
        ).distinct().count()
    active_clients_count.short_description = 'Активные клиенты'

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'completed', 'orders_count')
    list_filter = ('completed', 'created_at')
    
    def orders_count(self, obj):
        return obj.routeorder_set.count()
    orders_count.short_description = 'Заказов'

@admin.register(RouteOrder)
class RouteOrderAdmin(admin.ModelAdmin):
    list_display = ('route', 'order', 'order_number')
    list_filter = ('route__completed',)
    ordering = ('route', 'order_number')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('client', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('client__name', 'title', 'message')
    ordering = ('-created_at',)