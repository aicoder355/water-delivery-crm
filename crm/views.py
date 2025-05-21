from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count, Max
from django.db.models.functions import TruncDay, TruncMonth
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
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
from .models import Client, Order, Product, Container, Driver, Region, Route, RouteOrder, ClientCategory, LoyaltyTransaction, Notification, LoyaltyProgram
from .serializers import ClientSerializer, OrderSerializer, ContainerSerializer, DriverSerializer, RegionSerializer
import pandas as pd
from io import BytesIO
from datetime import datetime
from django.utils.timezone import make_aware

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
    """
    Личный кабинет водителя: показывает только заказы, назначенные этому водителю.
    """
    # Проверяем связь с Driver через user
    driver = getattr(request.user, 'driver_profile', None)
    if not driver:
        messages.error(request, 'Вы не являетесь водителем.')
        return redirect('dashboard')
    orders = Order.objects.filter(driver=driver).order_by('-order_date')
    return render(request, 'driver_dashboard.html', {'orders': orders})

@login_required
def orders(request):
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    orders = Order.objects.all().order_by('-order_date')
    
    if search_query:
        orders = orders.filter(client__name__icontains=search_query)
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'orders.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
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
            license_number=request.POST.get('license_number'),
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
        driver.license_number = request.POST.get('license_number')
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
    
    clients = Client.objects.select_related('region', 'category').all()
    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(company_name__icontains=search_query) |
            Q(tax_number__icontains=search_query)
        )
    
    # Добавляем агрегацию по заказам
    clients = clients.annotate(
        orders_count=Count('order'),
        total_orders_volume=Sum('order__quantity'),
        last_order_date=Max('order__order_date')
    ).order_by('-last_order_date', 'name')
    
    paginator = Paginator(clients, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clients.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'regions': Region.objects.all(),
        'categories': ClientCategory.objects.all(),
        'can_add_client': request.user.has_perm('crm.add_client'),
        'can_change_client': request.user.has_perm('crm.change_client'),
        'can_delete_client': request.user.has_perm('crm.delete_client'),
    })

@login_required
@permission_required('crm.add_client', raise_exception=True)
def create_client(request):
    if request.method == 'POST':
        client_type = request.POST.get('client_type', 'individual')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')
        address = request.POST.get('address')
        apartment = request.POST.get('apartment', '')
        floor = request.POST.get('floor')
        entrance = request.POST.get('entrance', '')
        region_id = request.POST.get('region')
        notes = request.POST.get('notes', '')
        
        # Дополнительные поля для юридических лиц
        company_name = request.POST.get('company_name', '')
        tax_number = request.POST.get('tax_number', '')
        contact_person = request.POST.get('contact_person', '')

        try:
            client = Client.objects.create(
                client_type=client_type,
                name=name,
                phone=phone,
                email=email,
                address=address,
                apartment=apartment,
                floor=floor if floor else None,
                entrance=entrance,
                region_id=region_id if region_id else None,
                notes=notes,
                company_name=company_name if client_type == 'business' else '',
                tax_number=tax_number if client_type == 'business' else '',
                contact_person=contact_person if client_type == 'business' else ''
            )
            messages.success(request, "Клиент создан успешно.")
        except Exception as e:
            messages.error(request, f"Ошибка при создании клиента: {str(e)}")
        
        return redirect('clients')
    return redirect('clients')

@login_required
@permission_required('crm.change_client', raise_exception=True)
def edit_client(request):
    if request.method == 'POST':
        client = get_object_or_404(Client, id=request.POST.get('client_id'))
        
        # Валидация основных полей
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        client_type = request.POST.get('client_type', 'individual')
        
        if not name:
            messages.error(request, "Имя клиента обязательно для заполнения")
            return redirect('clients')
            
        if not phone:
            messages.error(request, "Номер телефона обязателен для заполнения")
            return redirect('clients')
            
        # Специальные проверки для юридических лиц
        if client_type == 'business':
            company_name = request.POST.get('company_name', '').strip()
            tax_number = request.POST.get('tax_number', '').strip()
            
            if not company_name:
                messages.error(request, "Название компании обязательно для юридического лица")
                return redirect('clients')
                
            if not tax_number:
                messages.error(request, "ИНН обязателен для юридического лица")
                return redirect('clients')
        
        # Обновление данных клиента
        client.client_type = client_type
        client.name = name
        client.phone = phone
        client.email = request.POST.get('email', '').strip()
        client.address = request.POST.get('address', '').strip()
        client.apartment = request.POST.get('apartment', '').strip()
        client.floor = request.POST.get('floor') if request.POST.get('floor') else None
        client.entrance = request.POST.get('entrance', '').strip()
        client.region_id = request.POST.get('region') if request.POST.get('region') else None
        client.notes = request.POST.get('notes', '').strip()
        
        if client_type == 'business':
            client.company_name = company_name
            client.tax_number = tax_number
            client.contact_person = request.POST.get('contact_person', '').strip()
        else:
            client.company_name = ''
            client.tax_number = ''
            client.contact_person = ''
        
        try:
            client.save()
            messages.success(request, "Клиент обновлён успешно.")
        except Exception as e:
            messages.error(request, f"Ошибка при обновлении клиента: {str(e)}")
        
        return redirect('clients')
    return redirect('clients')

@login_required
@permission_required('crm.change_client', raise_exception=True)
def attach_client_to_region(request):
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        region_id = request.POST.get('region')
        
        if not client_id:
            messages.error(request, "Клиент не выбран")
            return redirect('regions')
            
        if not region_id:
            messages.error(request, "Регион не выбран")
            return redirect('regions')
            
        try:
            client = Client.objects.get(id=client_id)
            client.region_id = region_id
            client.save()
            messages.success(request, "Клиент успешно прикреплен к региону")
        except Client.DoesNotExist:
            messages.error(request, "Клиент не найден")
        except Exception as e:
            messages.error(request, f"Ошибка при прикреплении клиента к региону: {str(e)}")
            
        return redirect('regions')
    return redirect('regions')

@login_required
def client_loyalty(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    transactions = LoyaltyTransaction.objects.filter(client=client).order_by('-created_at')
    recent_orders = Order.objects.filter(client=client).order_by('-order_date')[:5]
    
    return render(request, 'client_loyalty.html', {
        'client': client,
        'transactions': transactions,
        'recent_orders': recent_orders
    })

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
@permission_required('crm.view_order', raise_exception=True)
def export_orders_xlsx(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    region_id = request.GET.get('region')
    driver_id = request.GET.get('driver')

    orders = Order.objects.all()
    if date_from:
        orders = orders.filter(order_date__gte=make_aware(datetime.strptime(date_from, '%Y-%m-%d')))
    if date_to:
        orders = orders.filter(order_date__lte=make_aware(datetime.strptime(date_to, '%Y-%m-%d')))
    if region_id:
        orders = orders.filter(client__region_id=region_id)
    if driver_id:
        orders = orders.filter(driver_id=driver_id)

    # Создаем DataFrame
    data = {
        'ID': [],
        'Дата': [],
        'Клиент': [],
        'Регион': [],
        'Адрес': [],
        'Продукт': [],
        'Количество': [],
        'Статус': [],
        'Водитель': []
    }

    for order in orders:
        data['ID'].append(order.id)
        data['Дата'].append(order.order_date.strftime('%d.%m.%Y %H:%M'))
        data['Клиент'].append(order.client.name)
        data['Регион'].append(order.client.region.name if order.client.region else 'Не указан')
        data['Адрес'].append(order.delivery_address)
        data['Продукт'].append(order.product.name)
        data['Количество'].append(order.quantity)
        data['Статус'].append(order.get_status_display())
        data['Водитель'].append(order.driver.name if order.driver else 'Не назначен')

    df = pd.DataFrame(data)

    # Создаем Excel файл
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Заказы')

    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=orders_report.xlsx'
    return response

@login_required
@permission_required('crm.view_container', raise_exception=True)
def export_containers_xlsx(request):
    region_id = request.GET.get('region')
    driver_id = request.GET.get('driver')

    containers = Container.objects.all()
    if region_id:
        containers = containers.filter(client__region_id=region_id)
    if driver_id:
        containers = containers.filter(client__orders__driver_id=driver_id).distinct()

    # Создаем DataFrame
    data = {
        'ID': [],
        'Продукт': [],
        'Клиент': [],
        'Регион': [],
        'Количество': [],
        'Местоположение': [],
    }

    for container in containers:
        data['ID'].append(container.id)
        data['Продукт'].append(container.product.name)
        data['Клиент'].append(container.client.name if container.client else '-')
        data['Регион'].append(container.client.region.name if container.client and container.client.region else 'Не указан')
        data['Количество'].append(container.quantity)
        data['Местоположение'].append('У клиента' if container.is_at_client else 'На складе')

    df = pd.DataFrame(data)

    # Создаем Excel файл
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Тара')

    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=containers_report.xlsx'
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
                if 'status' in data:
                    order.status = data['status']
                if 'driver_comment' in data:
                    order.driver_comment = data['driver_comment']
                # Возврат тары
                if 'return_quantity' in data and data['status'] == 'returned':
                    # Логика возврата тары (по умолчанию quantity заказа)
                    from .models import Container
                    container = Container.objects.filter(product=order.product, client=order.client, is_at_client=True).first()
                    if container:
                        container.is_at_client = False
                        container.client = None
                        container.save()
                        # Добавить на склад
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

def create_route(request):
    if request.method == 'POST':
        order_ids = request.POST.getlist('orders')
        if order_ids:
            route = Route.objects.create()
            for i, order_id in enumerate(order_ids, start=1):
                RouteOrder.objects.create(
                    route=route,
                    order=Order.objects.get(id=order_id),
                    order_number=i
                )
            return redirect('route_detail', route_id=route.id)
    
    orders = Order.objects.filter(status='planned')
    return render(request, 'create_route.html', {'orders': orders})

def route_detail(request, route_id):
    route = Route.objects.prefetch_related('routeorder_set__order').get(id=route_id)
    return render(request, 'route_detail.html', {'route': route})

def routes(request):
    # Заглушка для страницы маршрутов
    return render(request, 'routes.html')

def reports(request):
    regions = Region.objects.all()
    return render(request, 'reports.html', {'regions': regions})

@login_required
def notifications_list(request):
    if request.user.is_staff:
        # Администраторы видят все уведомления
        notifications = Notification.objects.all()
    elif hasattr(request.user, 'driver_profile'):
        # Водители видят уведомления по своим заказам
        notifications = Notification.objects.filter(
            Q(client__in=Client.objects.filter(region__driver=request.user.driver_profile)) |
            Q(order__driver=request.user.driver_profile)
        )
    else:
        # Клиенты видят только свои уведомления
        try:
            client = Client.objects.get(user=request.user)
            notifications = Notification.objects.filter(client=client)
        except Client.DoesNotExist:
            notifications = Notification.objects.none()
    
    notifications = notifications.select_related('client').order_by('-created_at')
    
    return render(request, 'notifications.html', {
        'notifications': notifications
    })

@login_required
def mark_notification_read(request, notification_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        if request.user.is_staff:
            # Администраторы могут отмечать любые уведомления
            notification = Notification.objects.get(id=notification_id)
        elif hasattr(request.user, 'driver_profile'):
            # Водители могут отмечать уведомления по своим заказам
            driver_clients = Client.objects.filter(region__driver=request.user.driver_profile)
            notification = Notification.objects.filter(
                id=notification_id
            ).filter(
                Q(client__in=driver_clients) |
                Q(order__driver=request.user.driver_profile)
            ).first()
            if not notification:
                raise Notification.DoesNotExist()
        else:
            # Клиенты могут отмечать только свои уведомления
            client = Client.objects.get(user=request.user)
            notification = Notification.objects.get(id=notification_id, client=client)

        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
        
    except (Notification.DoesNotExist, Client.DoesNotExist):
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

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

def is_manager(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_manager)
def loyalty_dashboard(request):
    programs = LoyaltyProgram.objects.all()
    categories = ClientCategory.objects.all()
    total_points = LoyaltyTransaction.objects.aggregate(total=Sum('points'))['total'] or 0
    
    context = {
        'programs': programs,
        'categories': categories,
        'total_points': total_points,
        'active_programs': programs.filter(is_active=True).count(),
    }
    return render(request, 'loyalty/dashboard.html', context)

@user_passes_test(is_manager)
def loyalty_program_edit(request, program_id=None):
    if program_id:
        program = get_object_or_404(LoyaltyProgram, id=program_id)
    else:
        program = None
    
    if request.method == 'POST':
        name = request.POST.get('name')
        points_per_liter = request.POST.get('points_per_liter')
        points_to_money_rate = request.POST.get('points_to_money_rate')
        min_points_to_redeem = request.POST.get('min_points_to_redeem')
        is_active = request.POST.get('is_active') == 'on'
        
        if program is None:
            program = LoyaltyProgram.objects.create(
                name=name,
                points_per_liter=points_per_liter,
                points_to_money_rate=points_to_money_rate,
                min_points_to_redeem=min_points_to_redeem,
                is_active=is_active
            )
        else:
            program.name = name
            program.points_per_liter = points_per_liter
            program.points_to_money_rate = points_to_money_rate
            program.min_points_to_redeem = min_points_to_redeem
            program.is_active = is_active
            program.save()
            
        messages.success(request, 'Программа лояльности успешно сохранена')
        return redirect('loyalty_dashboard')
        
    return render(request, 'loyalty/program_form.html', {'program': program})

@user_passes_test(is_manager)
def loyalty_category_edit(request, category_id=None):
    if category_id:
        category = get_object_or_404(ClientCategory, id=category_id)
    else:
        category = None
        
    if request.method == 'POST':
        name = request.POST.get('name')
        discount_percentage = request.POST.get('discount_percentage')
        min_points_required = request.POST.get('min_points_required')
        
        if category is None:
            category = ClientCategory.objects.create(
                name=name,
                discount_percentage=discount_percentage,
                min_points_required=min_points_required
            )
        else:
            category.name = name
            category.discount_percentage = discount_percentage
            category.min_points_required = min_points_required
            category.save()
            
        messages.success(request, 'Категория клиентов успешно сохранена')
        return redirect('loyalty_dashboard')
        
    return render(request, 'loyalty/category_form.html', {'category': category})

@user_passes_test(is_manager)
def loyalty_transactions(request):
    transactions = LoyaltyTransaction.objects.select_related('client').order_by('-created_at')
    return render(request, 'loyalty/transactions.html', {'transactions': transactions})