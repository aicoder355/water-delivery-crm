# Generated by Django 5.0 on 2025-05-14 04:27

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Имя')),
                ('phone', models.CharField(max_length=20, verbose_name='Телефон')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email')),
                ('address', models.TextField(verbose_name='Адрес')),
                ('apartment', models.CharField(blank=True, max_length=10, verbose_name='Квартира')),
                ('floor', models.IntegerField(blank=True, null=True, verbose_name='Этаж')),
                ('entrance', models.CharField(blank=True, max_length=10, verbose_name='Подъезд')),
                ('notes', models.TextField(blank=True, verbose_name='Заметки')),
                ('registration_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата регистрации')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
            ],
            options={
                'verbose_name': 'Клиент',
                'verbose_name_plural': 'Клиенты',
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('volume', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Объем (л)')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Цена')),
                ('is_returnable', models.BooleanField(default=True, verbose_name='Возвратная тара')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
            ],
            options={
                'verbose_name': 'Продукт',
                'verbose_name_plural': 'Продукты',
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(verbose_name='Количество')),
                ('order_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Дата заказа')),
                ('status', models.CharField(choices=[('planned', 'Запланирован'), ('in_progress', 'В пути'), ('delivered', 'Доставлен'), ('canceled', 'Отменен')], default='planned', max_length=20, verbose_name='Статус')),
                ('delivery_address', models.TextField(verbose_name='Адрес доставки')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crm.client', verbose_name='Клиент')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crm.product', verbose_name='Продукт')),
            ],
            options={
                'verbose_name': 'Заказ',
                'verbose_name_plural': 'Заказы',
            },
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=0, verbose_name='Количество')),
                ('reserved_quantity', models.IntegerField(default=0, verbose_name='Зарезервировано')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crm.product', verbose_name='Продукт')),
            ],
            options={
                'verbose_name': 'Инвентарь',
                'verbose_name_plural': 'Инвентарь',
            },
        ),
    ]
