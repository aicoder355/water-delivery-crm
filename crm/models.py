from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Product(models.Model):
    name = models.CharField(max_length=100)
    volume = models.FloatField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.volume}л)"

class Client(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    address = models.TextField()
    apartment = models.CharField(max_length=10, blank=True)
    floor = models.IntegerField(null=True, blank=True)
    entrance = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    registration_date = models.DateTimeField(default=timezone.now)
    region = models.ForeignKey('Region', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Запланирован'),
        ('delivered', 'Доставлен'),
        ('canceled', 'Отменён'),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    order_date = models.DateTimeField(default=timezone.now)
    delivery_address = models.TextField()
    driver = models.ForeignKey('Driver', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Заказ #{self.id} - {self.client.name}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

class Container(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    is_at_client = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} шт."

    @staticmethod
    def check_warehouse_stock(product, quantity_needed):
        total_in_warehouse = Container.objects.filter(
            product=product, is_at_client=False
        ).aggregate(total=models.Sum('quantity'))['total'] or 0
        return total_in_warehouse >= quantity_needed

    @staticmethod
    def get_low_stock_products():
        low_stock = []
        products = Product.objects.all()
        for product in products:
            total_in_warehouse = Container.objects.filter(
                product=product, is_at_client=False
            ).aggregate(total=models.Sum('quantity'))['total'] or 0
            if total_in_warehouse < 10:
                low_stock.append((product, total_in_warehouse))
        return low_stock

class Driver(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    region = models.ForeignKey('Region', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='driver_profile')

    def __str__(self):
        return self.name

class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name