from rest_framework import serializers
from .models import Client, Order, Container, Driver, Region, Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'volume', 'price']

class ClientSerializer(serializers.ModelSerializer):
    region = serializers.StringRelatedField()

    class Meta:
        model = Client
        fields = ['id', 'name', 'phone', 'email', 'address', 'apartment', 'floor', 'entrance', 'notes', 'registration_date', 'region']

class OrderSerializer(serializers.ModelSerializer):
    client = ClientSerializer()
    product = ProductSerializer()
    driver = serializers.StringRelatedField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'client', 'product', 'quantity', 'status', 'status_display', 'order_date', 'delivery_address', 'driver']

class ContainerSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    client = ClientSerializer(allow_null=True)

    class Meta:
        model = Container
        fields = ['id', 'product', 'client', 'quantity', 'is_at_client', 'last_updated']

class DriverSerializer(serializers.ModelSerializer):
    region = serializers.StringRelatedField()

    class Meta:
        model = Driver
        fields = ['id', 'name', 'phone', 'email', 'license_number', 'created_at', 'region']

class RegionSerializer(serializers.ModelSerializer):
    clients = ClientSerializer(many=True, read_only=True)

    class Meta:
        model = Region
        fields = ['id', 'name', 'description', 'created_at', 'clients']