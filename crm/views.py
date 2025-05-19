from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncDay, TruncMonth
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.contrib.auth.models import User
import csv
from datetime import timedelta
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from openpyxl import Workbook
from urllib.parse import quote as urlquote
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Client, Order, Product, Container, Driver, Region
from .serializers import ClientSerializer, OrderSerializer, ContainerSerializer, DriverSerializer, RegionSerializer

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'form': {'errors': True}})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    today = timezone.now().date()
    driver_profile = getattr(request.user, 'driver_profile', None)
    if driver_profile:
        # Водитель видит только свои заказы и статистику по ним
        orders = Order.objects.filter(order_date__date=today, driver=driver_profile)
        today_orders = orders.count()
        total_clients = Client.objects.filter(order__driver=driver_profile).distinct().count()
        delivered_bottles = sum(order.quantity for order in orders.filter(status='delivered'))
        today_revenue = sum(order.quantity * order.product.price for order in orders.filter(status='delivered'))
        # Тара только по клиентам этого водителя
        driver_clients = Client.objects.filter(order__driver=driver_profile).distinct()
        total_containers = Container.objects.filter(client__in=driver_clients).aggregate(total=Sum('quantity'))['total'] or 0
        containers_at_clients = Container.objects.filter(is_at_client=True, client__in=driver_clients).aggregate(total=Sum('quantity'))['total'] or 0
        containers_at_warehouse = total_containers - containers_at_clients
        # Графики и предупреждения не показываем водителю
        return render(request, 'dashboard.html', {
            'orders': orders,
            'today_orders': today_orders,
            'total_clients': total_clients,
            'delivered_bottles': delivered_bottles,
            'today_revenue': today_revenue,
            'total_containers': total_containers,
            'containers_at_clients': containers_at_clients,
            'containers_at_warehouse': containers_at_warehouse,
            'low_stock_products': [],
            'orders_by_day_labels': [],
            'orders_by_day_data': [],
            'revenue_by_month_labels': [],
            'revenue_by_month_data': [],
        })

    orders = Order.objects.filter(order_date__date=today)
    today_orders = orders.count()
    total_clients = Client.objects.count()
    delivered_bottles = sum(order.quantity for order in orders.filter(status='delivered'))
    today_revenue = sum(order.quantity * order.product.price for order in orders.filter(status='delivered'))
    
    total_containers = Container.objects.aggregate(total=Sum('quantity'))['total'] or 0
    containers_at_clients = Container.objects.filter(is_at_client=True).aggregate(total=Sum('quantity'))['total'] or 0
    containers_at_warehouse = total_containers - containers_at_clients

    # Проверка низкого уровня тары
    low_stock_products = Container.get_low_stock_products()
    if low_stock_products:
        low_stock_message = "Низкий уровень тары на складе: "
        low_stock_message += ", ".join([f"{p[0].name} ({p[1]} шт.)" for p in low_stock_products])
        messages.warning(request, low_stock_message)

    # Проверка просроченных заказов
    overdue_orders = Order.objects.filter(status='planned', order_date__lt=timezone.now() - timedelta(days=2))
    for order in overdue_orders:
        subject = 'Напоминание: Просроченный заказ'
        message = f'Заказ #{order.id} для клиента {order.client.name} просрочен. Статус: {order.get_status_display()}. Действия требуются.'
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.EMAIL_HOST_USER],  # Отправка админу
            fail_silently=True,
        )
        messages.warning(request, f'Отправлено напоминание об просроченном заказе #{order.id}.')

    # Данные для графика заказов по дням (последние 7 дней)
    end_date = today
    start_date = end_date - timedelta(days=6)  # 7 дней, включая сегодня
    orders_by_day = (Order.objects
                     .filter(order_date__date__range=[start_date, end_date])
                     .annotate(day=TruncDay('order_date'))
                     .values('day')
                     .annotate(count=Count('id'))
                     .order_by('day'))
    
    orders_by_day_data = {entry['day'].strftime('%d.%m.%Y'): entry['count'] for entry in orders_by_day}
    days = [(start_date + timedelta(days=x)).strftime('%d.%m.%Y') for x in range(7)]
    orders_by_day_counts = [orders_by_day_data.get(day, 0) for day in days]

    # Данные для графика выручки по месяцам (последние 6 месяцев)
    end_month = today.replace(day=1)  # Начало текущего месяца
    start_month = (end_month - timedelta(days=150)).replace(day=1)  # Примерно 5 месяцев назад + текущий
    revenue_by_month = (Order.objects
                        .filter(order_date__date__range=[start_month, end_month], status='delivered')
                        .annotate(month=TruncMonth('order_date'))
                        .values('month')
                        .annotate(revenue=Sum('quantity') * Sum('product__price'))
                        .order_by('month'))
    
    revenue_by_month_data = {entry['month'].strftime('%m.%Y'): entry['revenue'] or 0 for entry in revenue_by_month}
    months = []
    current_month = start_month
    while current_month <= end_month:
        months.append(current_month.strftime('%m.%Y'))
        next_month = current_month.month + 1 if current_month.month < 12 else 1
        next_year = current_month.year if current_month.month < 12 else current_month.year + 1
        current_month = current_month.replace(month=next_month, year=next_year)
    revenue_by_month_values = [revenue_by_month_data.get(month, 0) for month in months]

    return render(request, 'dashboard.html', {
        'orders': orders,
        'today_orders': today_orders,
        'total_clients': total_clients,
        'delivered_bottles': delivered_bottles,
        'today_revenue': today_revenue,
        'total_containers': total_containers,
        'containers_at_clients': containers_at_clients,
        'containers_at_warehouse': containers_at_warehouse,
        'low_stock_products': low_stock_products,
        'orders_by_day_labels': days,
        'orders_by_day_data': orders_by_day_counts,
        'revenue_by_month_labels': months,
        'revenue_by_month_data': revenue_by_month_values,
    })

@login_required
def driver_dashboard(request):
    driver = getattr(request.user, 'driver_profile', None)
    if not driver:
        messages.error(request, 'Вы не являетесь водителем.')
        return redirect('dashboard')
    # Показываем только НЕвыполненные заказы
    orders = Order.objects.filter(driver=driver).exclude(status='delivered').order_by('-order_date')
    # Фильтры
    status_filter = request.GET.get('status', '')
    region_id = request.GET.get('region', '')
    client_id = request.GET.get('client', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    if region_id:
        orders = orders.filter(client__region_id=region_id)
    if client_id:
        orders = orders.filter(client_id=client_id)
    regions = Region.objects.all()
    clients = Client.objects.filter(order__driver=driver).distinct()
    return render(request, 'driver_dashboard.html', {
        'orders': orders,
        'regions': regions,
        'clients': clients,
        'region_id': region_id,
        'client_id': client_id,
        'status_filter': status_filter,
    })

@login_required
def orders(request):
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    region_id = request.GET.get('region', '')
    driver_id = request.GET.get('driver', '')
    client_id = request.GET.get('client', '')
    orders = Order.objects.exclude(status='delivered').order_by('-order_date')
    if search_query:
        orders = orders.filter(client__name__icontains=search_query)
    if status_filter:
        orders = orders.filter(status=status_filter)
    if region_id:
        orders = orders.filter(client__region_id=region_id)
    if driver_id:
        orders = orders.filter(driver_id=driver_id)
    if client_id:
        orders = orders.filter(client_id=client_id)
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'orders.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'region_id': region_id,
        'driver_id': driver_id,
        'client_id': client_id,
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
        'regions': Region.objects.all(),
        'drivers': Driver.objects.all(),
        'can_add_order': request.user.has_perm('crm.add_order'),
        'can_change_order': request.user.has_perm('crm.change_order'),
        'can_delete_order': request.user.has_perm('crm.delete_order'),
    })

@login_required
@permission_required('crm.add_order', raise_exception=True)
def create_order(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity'))
        status = request.POST.get('status')

        # Поиск клиента по номеру телефона
        client = Client.objects.filter(phone=phone).first()
        if not client:
            messages.error(request, f"Клиент с номером телефона {phone} не найден.")
            return redirect('orders')

        product = Product.objects.get(id=product_id)

        # Автоматическое заполнение адреса доставки
        delivery_address = f"{client.address}, {client.apartment or ''}, {client.floor or ''} этаж, {client.entrance or ''}".strip().replace(', ,', ',').replace(' ,', '')

        # Автоматическое прикрепление водителя по региону клиента
        driver = None
        if client.region and client.region.driver_set.exists():
            driver = client.region.driver_set.first()

        if status == 'delivered':
            if not Container.check_warehouse_stock(product, quantity):
                messages.error(request, f"Недостаточно тары ({product.name}) на складе для доставки.")
                return redirect('orders')

        order = Order.objects.create(
            client=client,
            product=product,
            quantity=quantity,
            status=status,
            delivery_address=delivery_address,
            driver=driver
        )

        # PUSH-УВЕДОМЛЕНИЕ ВОДИТЕЛЮ
        if driver:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'driver_{driver.id}',
                {
                    'type': 'send_notification',
                    'message': f'Вам назначен новый заказ #{order.id} для клиента {client.name}.'
                }
            )

        if status == 'delivered':
            Container.objects.create(
                product=product,
                client=client,
                quantity=quantity,
                is_at_client=True
            )

            warehouse_container = Container.objects.filter(
                product=product, is_at_client=False
            ).first()
            if warehouse_container:
                warehouse_container.quantity -= quantity
                if warehouse_container.quantity <= 0:
                    warehouse_container.delete()
                else:
                    warehouse_container.save()

            # Отправка email клиенту
            subject = 'Ваш заказ доставлен'
            message = f'Уважаемый {order.client.name},\n\nВаш заказ #{order.id} успешно доставлен.\nДетали:\n- Продукт: {product.name}\n- Количество: {quantity}\n- Адрес: {delivery_address}\n- Водитель: {driver.name if driver else "Не назначен"}\n\nСпасибо за покупку!\nКоманда {settings.DEFAULT_FROM_EMAIL}'
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [order.client.email],
                fail_silently=True,
            )
            messages.success(request, f"Заказ создан, тара ({quantity} x {product.name}) отправлена клиенту. Email отправлен.")

        else:
            messages.success(request, "Заказ создан.")

        return redirect('orders')
    return render(request, 'orders.html', {
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
    })

@login_required
@permission_required('crm.change_order', raise_exception=True)
def edit_order(request):
    if request.method == 'POST':
        order = Order.objects.get(id=request.POST.get('order_id'))
        old_status = order.status  # Сохраняем старый статус для сравнения
        phone = request.POST.get('phone')
        product_id = request.POST.get('product')
        new_quantity = int(request.POST.get('quantity'))
        new_status = request.POST.get('status')

        # Поиск клиента по номеру телефона
        client = Client.objects.filter(phone=phone).first()
        if not client:
            messages.error(request, f"Клиент с номером телефона {phone} не найден.")
            return redirect('orders')

        product = Product.objects.get(id=product_id)

        # Автоматическое заполнение адреса доставки
        delivery_address = f"{client.address}, {client.apartment or ''}, {client.floor or ''} этаж, {client.entrance or ''}".strip().replace(', ,', ',').replace(' ,', '')

        # Автоматическое прикрепление водителя по региону клиента
        driver = None
        if client.region and client.region.driver_set.exists():
            driver = client.region.driver_set.first()

        # Если водитель изменился и назначен
        if driver and (order.driver != driver):
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'driver_{driver.id}',
                {
                    'type': 'send_notification',
                    'message': f'Вам назначен новый заказ #{order.id} для клиента {client.name}.'
                }
            )

        # Если статус меняется на "Доставлен"
        if new_status == 'delivered' and old_status != 'delivered':
            if not Container.check_warehouse_stock(product, new_quantity):
                messages.error(request, f"Недостаточно тары ({product.name}) на складе для доставки.")
                return redirect('orders')

            # Создаём тару для клиента
            Container.objects.create(
                product=product,
                client=client,
                quantity=new_quantity,
                is_at_client=True
            )

            # Уменьшаем тару на складе
            warehouse_container = Container.objects.filter(
                product=product, is_at_client=False
            ).first()
            if warehouse_container:
                warehouse_container.quantity -= new_quantity
                if warehouse_container.quantity <= 0:
                    warehouse_container.delete()
                else:
                    warehouse_container.save()

            # Отправка email клиенту
            subject = 'Ваш заказ доставлен'
            message = f'Уважаемый {client.name},\n\nВаш заказ #{order.id} успешно доставлен.\nДетали:\n- Продукт: {product.name}\n- Количество: {new_quantity}\n- Адрес: {delivery_address}\n- Водитель: {driver.name if driver else "Не назначен"}\n\nСпасибо за покупку!\nКоманда {settings.DEFAULT_FROM_EMAIL}'
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [client.email],
                fail_silently=True,
            )
            messages.success(request, f"Заказ обновлён, тара ({new_quantity} x {product.name}) отправлена клиенту. Email отправлен.")

        # Если статус меняется на "Отменён" и ранее был "Доставлен"
        elif new_status == 'canceled' and old_status == 'delivered':
            container = Container.objects.filter(
                product=product, client=client, is_at_client=True
            ).first()
            if container:
                container.is_at_client = False
                container.client_id = None
                container.save()

                # Добавляем тару обратно на склад
                warehouse_container = Container.objects.filter(
                    product=product, is_at_client=False
                ).first()
                if warehouse_container:
                    warehouse_container.quantity += container.quantity
                    warehouse_container.save()
                else:
                    Container.objects.create(
                        product=product,
                        quantity=container.quantity,
                        is_at_client=False
                    )
                messages.success(request, f"Заказ отменён, тара ({container.quantity} x {product.name}) возвращена на склад.")

        else:
            messages.success(request, "Заказ обновлён.")

        order.client = client
        order.product = product
        order.quantity = new_quantity
        order.status = new_status
        order.delivery_address = delivery_address
        order.driver = driver
        order.save()
        return redirect('orders')
    return redirect('orders')

@login_required
@permission_required('crm.delete_order', raise_exception=True)
def delete_order(request, order_id):
    order = Order.objects.get(id=order_id)
    order.delete()
    messages.success(request, "Заказ удалён.")
    return redirect('orders')

@login_required
def drivers(request):
    drivers_list = Driver.objects.all()
    search_query = request.GET.get('search', '')
    if search_query:
        drivers_list = drivers_list.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    paginator = Paginator(drivers_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'drivers.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'can_add_driver': request.user.has_perm('crm.add_driver'),
        'can_change_driver': request.user.has_perm('crm.change_driver'),
        'can_delete_driver': request.user.has_perm('crm.delete_driver'),
        'regions': Region.objects.all(),  # Убедись, что эта строка есть
    })

@login_required
@permission_required('crm.add_driver', raise_exception=True)
def create_driver(request):
    if request.method == 'POST':
        Driver.objects.create(
            name=request.POST.get('name'),
            phone=request.POST.get('phone'),
            email=request.POST.get('email', ''),
            region_id=request.POST.get('region'),
            created_at=timezone.now()
        )
        messages.success(request, "Водитель добавлен.")
        return redirect('drivers')
    return render(request, 'drivers.html', {
        'regions': Region.objects.all(),
    })

@login_required
@permission_required('crm.change_driver', raise_exception=True)
def edit_driver(request):
    if request.method == 'POST':
        driver = Driver.objects.get(id=request.POST.get('driver_id'))
        driver.name = request.POST.get('name')
        driver.phone = request.POST.get('phone')
        driver.email = request.POST.get('email', '')
        driver.region_id = request.POST.get('region')
        driver.save()
        messages.success(request, "Водитель обновлён.")
        return redirect('drivers')
    return redirect('drivers')

@login_required
@permission_required('crm.delete_driver', raise_exception=True)
def delete_driver(request, driver_id):
    driver = Driver.objects.get(id=driver_id)
    driver.delete()
    messages.success(request, "Водитель удалён.")
    return redirect('drivers')

@login_required
def regions(request):
    search_query = request.GET.get('search', '')
    
    regions = Region.objects.prefetch_related('client_set').all().order_by('id')
    
    if search_query:
        regions = regions.filter(name__icontains=search_query)
    
    paginator = Paginator(regions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'regions.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'can_add_region': request.user.has_perm('crm.add_region'),
        'can_change_region': request.user.has_perm('crm.change_region'),
        'can_delete_region': request.user.has_perm('crm.delete_region'),
        'clients': Client.objects.all(),  # Добавляем список всех клиентов
        'regions': Region.objects.all(),  # Для формы добавления клиента
    })

@login_required
@permission_required('crm.add_region', raise_exception=True)
def create_region(request):
    if request.method == 'POST':
        Region.objects.create(
            name=request.POST.get('name'),
            description=request.POST.get('description', ''),
            created_at=timezone.now()
        )
        messages.success(request, "Регион добавлен.")
        return redirect('regions')
    return redirect('regions')

@login_required
@permission_required('crm.change_region', raise_exception=True)
def edit_region(request):
    if request.method == 'POST':
        region = Region.objects.get(id=request.POST.get('region_id'))
        region.name = request.POST.get('name')
        region.description = request.POST.get('description', '')
        region.save()
        messages.success(request, "Регион обновлён.")
        return redirect('regions')
    return redirect('regions')

@login_required
@permission_required('crm.delete_region', raise_exception=True)
def delete_region(request, region_id):
    region = Region.objects.get(id=region_id)
    region.delete()
    messages.success(request, "Регион удалён.")
    return redirect('regions')

@login_required
def clients(request):
    search_query = request.GET.get('search', '')
    
    clients = Client.objects.all().order_by('id')
    
    if search_query:
        clients = clients.filter(Q(name__icontains=search_query) | Q(phone__icontains=search_query))
    
    paginator = Paginator(clients, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clients.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'regions': Region.objects.all(),
        'can_add_client': request.user.has_perm('crm.add_client'),
        'can_change_client': request.user.has_perm('crm.change_client'),
        'can_delete_client': request.user.has_perm('crm.delete_client'),
    })

@login_required
@permission_required('crm.add_client', raise_exception=True)
def create_client(request):
    if request.method == 'POST':
        floor_value = request.POST.get('floor')
        floor = int(floor_value) if floor_value else None
        
        client = Client.objects.create(
            name=request.POST.get('name'),
            phone=request.POST.get('phone'),
            email=request.POST.get('email', ''),
            address=request.POST.get('address'),
            apartment=request.POST.get('apartment', ''),
            floor=floor,
            entrance=request.POST.get('entrance', ''),
            notes=request.POST.get('notes', ''),
            region_id=request.POST.get('region'),
            registration_date=timezone.now()
        )
        messages.success(request, "Клиент добавлен.")
        return redirect('clients')
    return redirect('clients')

@login_required
@permission_required('crm.change_client', raise_exception=True)
def edit_client(request):
    if request.method == 'POST':
        client = Client.objects.get(id=request.POST.get('client_id'))
        # Если форма пришла только с region и client_id (прикрепление к региону)
        if 'region' in request.POST and len(request.POST) <= 4:
            client.region_id = request.POST.get('region')
            client.save()
            messages.success(request, "Клиент прикреплён к региону.")
            return redirect('regions')
        client.name = request.POST.get('name')
        client.phone = request.POST.get('phone')
        client.email = request.POST.get('email', '')
        client.address = request.POST.get('address')
        client.apartment = request.POST.get('apartment', '')
        floor_value = request.POST.get('floor')
        client.floor = int(floor_value) if floor_value else None
        client.entrance = request.POST.get('entrance', '')
        client.notes = request.POST.get('notes', '')
        client.region_id = request.POST.get('region')
        client.save()
        messages.success(request, "Клиент обновлён.")
        return redirect('clients')
    return redirect('clients')

@login_required
@permission_required('crm.delete_client', raise_exception=True)
def delete_client(request, client_id):
    client = Client.objects.get(id=client_id)
    # Проверка на наличие заказов или тары
    if client.order_set.exists():
        messages.error(request, "Нельзя удалить клиента, у которого есть заказы.")
        return redirect('clients')
    if Container.objects.filter(client=client, is_at_client=True).exists():
        messages.error(request, "Нельзя удалить клиента, у которого есть тара.")
        return redirect('clients')
    client.delete()
    messages.success(request, "Клиент удалён.")
    return redirect('clients')

@login_required
def containers(request):
    search_query = request.GET.get('search', '')
    
    containers = Container.objects.all().order_by('id')
    
    if search_query:
        containers = containers.filter(Q(product__name__icontains=search_query) | Q(client__name__icontains=search_query))
    
    paginator = Paginator(containers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Проверка низкого уровня тары
    low_stock_products = Container.get_low_stock_products()
    if low_stock_products:
        messages.warning(request, f"Низкий уровень тары на складе: {', '.join([f'{p[0].name} ({p[1]} шт.)' for p in low_stock_products])}")

    # Определяем контейнеры с низким уровнем тары
    low_stock_container_ids = []
    for container in page_obj:
        if not container.is_at_client:  # Только для тары на складе
            for product, quantity in low_stock_products:
                if container.product.id == product.id and quantity < 10:
                    low_stock_container_ids.append(container.id)
                    break

    return render(request, 'containers.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
        'can_add_container': request.user.has_perm('crm.add_container'),
        'can_change_container': request.user.has_perm('crm.change_container'),
        'can_delete_container': request.user.has_perm('crm.delete_container'),
        'low_stock_products': low_stock_products,
        'low_stock_container_ids': low_stock_container_ids,
    })

@login_required
@permission_required('crm.add_container', raise_exception=True)
def create_container(request):
    if request.method == 'POST':
        client_id = request.POST.get('client') or None
        Container.objects.create(
            product_id=request.POST.get('product'),
            client_id=client_id,
            quantity=request.POST.get('quantity'),
            is_at_client=request.POST.get('is_at_client') == 'True'
        )
        messages.success(request, "Тара добавлена.")
        return redirect('containers')
    return redirect('containers')

@login_required
@permission_required('crm.change_container', raise_exception=True)
def edit_container(request):
    if request.method == 'POST':
        container = Container.objects.get(id=request.POST.get('container_id'))
        container.product_id = request.POST.get('product')
        container.client_id = request.POST.get('client') or None
        container.quantity = request.POST.get('quantity')
        container.is_at_client = request.POST.get('is_at_client') == 'True'
        container.save()
        messages.success(request, "Тара обновлена.")
        return redirect('containers')
    return redirect('containers')

@login_required
@permission_required('crm.change_container', raise_exception=True)
def return_container(request, container_id):
    container = Container.objects.get(id=container_id)
    if container.is_at_client:
        container.is_at_client = False
        container.client_id = None
        container.save()
        messages.success(request, "Тара возвращена на склад.")
    return redirect('containers')

@login_required
@permission_required('crm.change_container', raise_exception=True)
def bulk_return_containers(request):
    if request.method == 'POST':
        client_id = request.POST.get('client')
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity'))

        client = Client.objects.get(id=client_id)
        product = Product.objects.get(id=product_id)

        containers = Container.objects.filter(client=client, product=product, is_at_client=True)
        total_quantity = containers.aggregate(total=Sum('quantity'))['total'] or 0

        if quantity > total_quantity:
            messages.error(request, f"У клиента {client.name} недостаточно тары ({product.name}) для возврата.")
            return redirect('containers')

        if quantity == total_quantity:
            containers.delete()
        else:
            for container in containers:
                if quantity <= 0:
                    break
                if container.quantity <= quantity:
                    quantity -= container.quantity
                    container.delete()
                else:
                    container.quantity -= quantity
                    container.save()
                    quantity = 0

        # Добавляем тару на склад
        warehouse_container = Container.objects.filter(product=product, is_at_client=False).first()
        if warehouse_container:
            warehouse_container.quantity += (total_quantity - quantity)
            warehouse_container.save()
        else:
            Container.objects.create(
                product=product,
                quantity=(total_quantity - quantity),
                is_at_client=False
            )

        messages.success(request, f"Возвращено {total_quantity - quantity} x {product.name} на склад.")
        return redirect('containers')

    return render(request, 'containers.html', {
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
    })

@login_required
@permission_required('crm.delete_container', raise_exception=True)
def delete_container(request, container_id):
    container = Container.objects.get(id=container_id)
    container.delete()
    messages.success(request, "Тара удалена.")
    return redirect('containers')

@login_required
@permission_required('crm.add_product', raise_exception=True)
@csrf_protect
def create_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        volume = request.POST.get('volume')
        price = request.POST.get('price')
        Product.objects.create(
            name=name,
            volume=volume,
            price=price
        )
        messages.success(request, "Продукт добавлен.")
        return redirect('containers')
    return redirect('containers')

@login_required
@permission_required('crm.view_client', raise_exception=True)
def export_clients_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clients.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Имя', 'Телефон', 'Email', 'Адрес', 'Квартира', 'Этаж', 'Подъезд', 'Заметки', 'Дата регистрации', 'Регион'])
    
    clients = Client.objects.all()
    for client in clients:
        writer.writerow([
            client.id,
            client.name,
            client.phone,
            client.email,
            client.address,
            client.apartment,
            client.floor,
            client.entrance,
            client.notes,
            client.registration_date,
            client.region.name if client.region else "Не указан"
        ])
    
    return response

@login_required
@permission_required('crm.view_order', raise_exception=True)
def export_orders_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Клиент', 'Продукт', 'Количество', 'Статус', 'Дата заказа', 'Адрес доставки', 'Водитель'])
    
    orders = Order.objects.all()
    for order in orders:
        writer.writerow([
            order.id,
            order.client.name,
            order.product.name,
            order.quantity,
            order.get_status_display(),
            order.order_date,
            order.delivery_address,
            order.driver.name if order.driver else "Не назначен"
        ])
    
    return response

@login_required
@permission_required('crm.view_order', raise_exception=True)
def export_orders_by_day_csv(request):
    today = timezone.now().date()
    end_date = today
    start_date = end_date - timedelta(days=6)  # 7 дней, включая сегодня
    orders_by_day = (Order.objects
                     .filter(order_date__date__range=[start_date, end_date])
                     .annotate(day=TruncDay('order_date'))
                     .values('day')
                     .annotate(count=Count('id'))
                     .order_by('day'))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders_by_day.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Дата', 'Количество заказов'])
    
    orders_by_day_data = {entry['day'].strftime('%d.%m.%Y'): entry['count'] for entry in orders_by_day}
    days = [(start_date + timedelta(days=x)) for x in range(7)]
    for day in days:
        day_str = day.strftime('%d.%m.%Y')
        writer.writerow([day_str, orders_by_day_data.get(day_str, 0)])
    
    return response

@login_required
@permission_required('crm.view_order', raise_exception=True)
def export_revenue_by_month_csv(request):
    today = timezone.now().date()
    end_month = today.replace(day=1)  # Начало текущего месяца
    start_month = (end_month - timedelta(days=150)).replace(day=1)  # Примерно 5 месяцев назад + текущий
    revenue_by_month = (Order.objects
                        .filter(order_date__date__range=[start_month, end_month], status='delivered')
                        .annotate(month=TruncMonth('order_date'))
                        .values('month')
                        .annotate(revenue=Sum('quantity') * Sum('product__price'))
                        .order_by('month'))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="revenue_by_month.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Месяц', 'Выручка (руб.)'])
    
    revenue_by_month_data = {entry['month'].strftime('%m.%Y'): entry['revenue'] or 0 for entry in revenue_by_month}
    months = []
    current_month = start_month
    while current_month <= end_month:
        months.append(current_month)
        next_month = current_month.month + 1 if current_month.month < 12 else 1
        next_year = current_month.year if current_month.month < 12 else current_month.year + 1
        current_month = current_month.replace(month=next_month, year=next_year)
    for month in months:
        month_str = month.strftime('%m.%Y')
        writer.writerow([month_str, revenue_by_month_data.get(month_str, 0)])
    
    return response

@login_required
def export_orders_xlsx(request):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Заказы'
    ws.append(['ID', 'Клиент', 'Продукт', 'Количество', 'Статус', 'Дата заказа', 'Адрес доставки', 'Водитель', 'Регион'])
    # Фильтры
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    region_id = request.GET.get('region')
    driver_id = request.GET.get('driver')
    orders = Order.objects.select_related('client', 'product', 'driver', 'client__region')
    if date_from:
        orders = orders.filter(order_date__date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__date__lte=date_to)
    if region_id:
        orders = orders.filter(client__region_id=region_id)
    if driver_id:
        orders = orders.filter(driver_id=driver_id)
    for order in orders:
        ws.append([
            order.id,
            order.client.name,
            order.product.name,
            order.quantity,
            order.get_status_display(),
            order.order_date.strftime('%d.%m.%Y %H:%M'),
            order.delivery_address,
            order.driver.name if order.driver else '',
            order.client.region.name if order.client.region else '',
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = 'orders.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{urlquote(filename)}"'
    wb.save(response)
    return response

@login_required
def export_containers_xlsx(request):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Тара'
    ws.append(['ID', 'Продукт', 'Клиент', 'Количество', 'На руках у клиента', 'Последнее обновление', 'Регион', 'Водитель'])
    region_id = request.GET.get('region')
    driver_id = request.GET.get('driver')
    containers = Container.objects.select_related('product', 'client', 'client__region')
    if region_id:
        containers = containers.filter(client__region_id=region_id)
    if driver_id:
        containers = containers.filter(client__region__driver__id=driver_id)
    for container in containers:
        ws.append([
            container.id,
            container.product.name,
            container.client.name if container.client else '',
            container.quantity,
            'Да' if container.is_at_client else 'Нет',
            container.last_updated.strftime('%d.%m.%Y %H:%M'),
            container.client.region.name if container.client and container.client.region else '',
            container.client.region.driver_set.first().name if container.client and container.client.region and container.client.region.driver_set.exists() else '',
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = 'containers.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{urlquote(filename)}"'
    wb.save(response)
    return response

@csrf_exempt
@login_required
def api_update_order(request, order_id):
    if request.method == 'PATCH':
        import json
        data = json.loads(request.body)
        try:
            order = Order.objects.get(id=order_id)
            driver = getattr(request.user, 'driver_profile', None)
            if request.user.is_authenticated and driver and order.driver == driver:
                # Если пришёл статус delivered и paid и return_quantity, делаем все действия сразу
                if data.get('status') == 'delivered' and data.get('paid', False):
                    order.status = 'delivered'
                    # Логика возврата тары
                    return_qty = int(data.get('return_quantity', order.quantity))
                    from .models import Container
                    container = Container.objects.filter(product=order.product, client=order.client, is_at_client=True).first()
                    if container:
                        container.is_at_client = False
                        container.client = None
                        container.save()
                        # Добавить на склад
                        warehouse_container = Container.objects.filter(product=order.product, is_at_client=False).first()
                        if warehouse_container:
                            warehouse_container.quantity += return_qty
                            warehouse_container.save()
                        else:
                            Container.objects.create(product=order.product, quantity=return_qty, is_at_client=False)
                else:
                    if 'status' in data:
                        order.status = data['status']
                    if 'driver_comment' in data:
                        order.driver_comment = data['driver_comment']
                    if 'return_quantity' in data and data['status'] == 'returned':
                        from .models import Container
                        container = Container.objects.filter(product=order.product, client=order.client, is_at_client=True).first()
                        if container:
                            container.is_at_client = False
                            container.client = None
                            container.save()
                            warehouse_container = Container.objects.filter(product=order.product, is_at_client=False).first()
                            if warehouse_container:
                                warehouse_container.quantity += data['return_quantity']
                                warehouse_container.save()
                            else:
                                Container.objects.create(product=order.product, quantity=data['return_quantity'], is_at_client=False)
                order.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Нет прав'}, status=403)
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Заказ не найден'}, status=404)
    return JsonResponse({'success': False, 'error': 'Метод не поддерживается'}, status=405)

@login_required
def reports(request):
    regions = Region.objects.all()
    drivers = Driver.objects.all()
    # Фильтры
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    region_id = request.GET.get('region')
    driver_id = request.GET.get('driver')
    orders = Order.objects.select_related('client', 'product', 'driver', 'client__region').all()

    # Если пользователь — водитель, показываем только его заказы
    driver_profile = getattr(request.user, 'driver_profile', None)
    if driver_profile:
        orders = orders.filter(driver=driver_profile)
    if date_from:
        orders = orders.filter(order_date__date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__date__lte=date_to)
    if region_id:
        orders = orders.filter(client__region_id=region_id)
    if driver_id:
        orders = orders.filter(driver_id=driver_id)
    return render(request, 'reports.html', {
        'regions': regions,
        'drivers': drivers,
        'orders': orders,
    })

@login_required
def export_containers_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="containers.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Продукт', 'Клиент', 'Количество', 'На руках у клиента', 'Последнее обновление'])
    for container in Container.objects.all():
        writer.writerow([
            container.id,
            container.product.name,
            container.client.name if container.client else '',
            container.quantity,
            'Да' if container.is_at_client else 'Нет',
            container.last_updated.strftime('%d.%m.%Y %H:%M'),
        ])
    return response

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

class ContainerViewSet(viewsets.ModelViewSet):
    queryset = Container.objects.all()
    serializer_class = ContainerSerializer
    permission_classes = [IsAuthenticated]

class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]

class RegionViewSet(viewsets.ModelViewSet):
    queryset = Region.objects.prefetch_related('client_set').all()
    serializer_class = RegionSerializer
    permission_classes = [IsAuthenticated]