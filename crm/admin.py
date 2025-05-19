from django.contrib import admin
from .models import Client, Product, Order, Container, Driver

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'address')
    search_fields = ('name', 'phone', 'email')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'volume', 'price')
    search_fields = ('name',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'client', 'product', 'quantity', 'status', 'order_date')
    list_filter = ('status', 'order_date')
    search_fields = ('client__name', 'product__name')
    fields = ('client', 'product', 'quantity', 'status', 'order_date', 'delivery_address', 'driver')

@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'client', 'quantity', 'is_at_client', 'last_updated')
    list_filter = ('is_at_client', 'product')
    search_fields = ('client__name', 'product__name')

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'region', 'user')
    search_fields = ('name', 'phone', 'email')
    list_filter = ('region',)
    fields = ('name', 'phone', 'email', 'region', 'user', 'created_at')
    readonly_fields = ('created_at',)