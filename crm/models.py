from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

class Product(models.Model):
    name = models.CharField(max_length=100)
    volume = models.FloatField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.volume}л)"

class LoyaltyProgram(models.Model):
    name = models.CharField(max_length=100)
    points_per_liter = models.DecimalField(max_digits=5, decimal_places=2)
    points_to_money_rate = models.DecimalField(max_digits=5, decimal_places=2)
    min_points_to_redeem = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ClientCategory(models.Model):
    name = models.CharField(max_length=50)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    min_monthly_volume = models.PositiveIntegerField(help_text="Минимальный объем в литрах для категории")

    def __str__(self):
        return self.name

class Client(models.Model):
    TYPE_CHOICES = [
        ('individual', 'Физическое лицо'),
        ('business', 'Юридическое лицо'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Номер телефона должен быть в формате: '+999999999'"
    )
    phone = models.CharField(validators=[phone_regex], max_length=20, unique=True)
    email = models.EmailField(blank=True)
    address = models.TextField()
    apartment = models.CharField(max_length=10, blank=True)
    floor = models.IntegerField(null=True, blank=True)
    entrance = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    registration_date = models.DateTimeField(default=timezone.now)
    region = models.ForeignKey('Region', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Новые поля
    client_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='individual')
    company_name = models.CharField(max_length=200, blank=True, null=True)
    tax_number = models.CharField(max_length=50, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    category = models.ForeignKey(ClientCategory, on_delete=models.SET_NULL, null=True, blank=True)
    loyalty_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_volume_purchased = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_purchase_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        if self.client_type == 'business':
            return f"{self.company_name} ({self.contact_person})"
        return self.name

    def calculate_category(self):
        """Автоматический расчет категории клиента на основе объема закупок"""
        monthly_volume = self.total_volume_purchased
        categories = ClientCategory.objects.order_by('-min_monthly_volume')
        for category in categories:
            if monthly_volume >= category.min_monthly_volume:
                self.category = category
                self.save()
                break

class LoyaltyTransaction(models.Model):
    TYPE_CHOICES = [
        ('earned', 'Начислено'),
        ('redeemed', 'Списано'),
        ('expired', 'Сгорело'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    points = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.client.name} - {self.get_transaction_type_display()}: {self.points}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('planned', 'Запланирован'),
        ('in_progress', 'В пути'),
        ('delivered', 'Доставлен'),
        ('canceled', 'Отменён'),
    ]
    PAYMENT_TYPES = [
        ('cash', 'Наличные'),
        ('card', 'Карта'),
        ('points', 'Баллы'),
        ('mixed', 'Смешанная'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    order_date = models.DateTimeField(default=timezone.now)
    delivery_address = models.TextField()
    driver = models.ForeignKey('Driver', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Новые поля
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='cash')
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_used = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    points_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    call_id = models.CharField(max_length=100, blank=True, null=True)
    driver_comment = models.TextField(blank=True)
    delivery_confirmation = models.ImageField(upload_to='delivery_confirmations/', null=True, blank=True)
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Заказ #{self.id} - {self.client.name}"

    def calculate_points(self):
        """Расчет баллов за заказ"""
        if self.status == 'delivered' and not self.points_earned:
            program = LoyaltyProgram.objects.first()
            if program:
                volume = self.quantity * self.product.volume
                self.points_earned = volume * program.points_per_liter
                self.save()

    def apply_loyalty_points(self, points_to_use):
        """Применение баллов лояльности к заказу"""
        program = LoyaltyProgram.objects.first()
        if program and points_to_use <= self.client.loyalty_points:
            points_value = points_to_use * program.points_to_money_rate
            if points_value > self.total_amount:
                points_value = self.total_amount
                points_to_use = points_value / program.points_to_money_rate
            
            self.points_used = points_to_use
            self.payment_amount = self.total_amount - points_value
            self.save()
            
            # Списываем баллы у клиента
            self.client.loyalty_points -= points_to_use
            self.client.save()
            
            # Создаем транзакцию списания баллов
            LoyaltyTransaction.objects.create(
                client=self.client,
                points=-points_to_use,
                transaction_type='redeemed',
                order=self,
                description=f'Использовано в заказе #{self.id}'
            )

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

class Route(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Маршрут'
        verbose_name_plural = 'Маршруты'
        ordering = ['-created_at']

    def __str__(self):
        return f'Маршрут #{self.id} от {self.created_at.strftime("%d.%m.%Y %H:%M")}'

class RouteOrder(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    order_number = models.PositiveIntegerField()  # Порядок точки в маршруте

    class Meta:
        verbose_name = 'Заказ в маршруте'
        verbose_name_plural = 'Заказы в маршруте'
        ordering = ['order_number']
        unique_together = [['route', 'order']]  # Заказ может быть в маршруте только один раз

    def __str__(self):
        return f'Точка #{self.order_number} маршрута #{self.route_id}'

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('ORDER_STATUS', 'Статус заказа'),
        ('LOYALTY_POINTS', 'Баллы лояльности'),
        ('PROMO', 'Промо-акция'),
        ('DELIVERY', 'Информация о доставке'),
    ]
    
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
    
    def __str__(self):
        return f"{self.get_notification_type_display()} для {self.client.name}"