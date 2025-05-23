# Generated by Django 4.2.16 on 2025-05-17 05:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0006_client_region_driver_region_order_driver_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='driver',
            name='license_number',
        ),
        migrations.AlterField(
            model_name='driver',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='driver',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
    ]
