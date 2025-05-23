# Generated by Django 4.2.16 on 2025-05-14 09:49

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0002_container'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='client',
            options={},
        ),
        migrations.AlterModelOptions(
            name='container',
            options={},
        ),
        migrations.AlterModelOptions(
            name='order',
            options={},
        ),
        migrations.AlterModelOptions(
            name='product',
            options={},
        ),
        migrations.RemoveField(
            model_name='client',
            name='is_active',
        ),
        migrations.RemoveField(
            model_name='product',
            name='description',
        ),
        migrations.RemoveField(
            model_name='product',
            name='is_active',
        ),
        migrations.RemoveField(
            model_name='product',
            name='is_returnable',
        ),
        migrations.AlterField(
            model_name='client',
            name='address',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='client',
            name='apartment',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AlterField(
            model_name='client',
            name='email',
            field=models.EmailField(blank=True, default=2, max_length=254),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='client',
            name='entrance',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AlterField(
            model_name='client',
            name='floor',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='client',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='client',
            name='notes',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='client',
            name='phone',
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='client',
            name='registration_date',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='container',
            name='client',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='crm.client'),
        ),
        migrations.AlterField(
            model_name='container',
            name='is_at_client',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='container',
            name='last_updated',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='container',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crm.product'),
        ),
        migrations.AlterField(
            model_name='container',
            name='quantity',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='order',
            name='client',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crm.client'),
        ),
        migrations.AlterField(
            model_name='order',
            name='delivery_address',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='order',
            name='order_date',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='order',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crm.product'),
        ),
        migrations.AlterField(
            model_name='order',
            name='quantity',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('planned', 'Запланирован'), ('in_progress', 'В пути'), ('delivered', 'Доставлен'), ('canceled', 'Отменен')], default='planned', max_length=20),
        ),
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
        migrations.AlterField(
            model_name='product',
            name='volume',
            field=models.FloatField(),
        ),
        migrations.DeleteModel(
            name='Inventory',
        ),
    ]
