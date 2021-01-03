# Generated by Django 2.2.2 on 2021-01-03 17:47

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tracker', '0024_auto_20210102_1650'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchase',
            name='category',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchases_2', to='tracker.PurchaseCategory', verbose_name='Category'),
        ),
        migrations.AlterField(
            model_name='purchase',
            name='category_2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchases_3', to='tracker.PurchaseCategory', verbose_name='Category 2'),
        ),
        migrations.AlterField(
            model_name='purchase',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchases_1', to=settings.AUTH_USER_MODEL, verbose_name='User'),
        ),
        migrations.AlterField(
            model_name='recurring',
            name='account',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurrings_2', to='tracker.Account', verbose_name='Account'),
        ),
        migrations.AlterField(
            model_name='recurring',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recurrings_1', to=settings.AUTH_USER_MODEL, verbose_name='User'),
        ),
        migrations.CreateModel(
            name='QuickEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item', models.CharField(max_length=100, verbose_name='Item(s)')),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Amount')),
                ('amount_2', models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='Amount 2')),
                ('description', models.TextField(blank=True, verbose_name='Details')),
                ('category', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quick_entry_2', to='tracker.PurchaseCategory', verbose_name='Category')),
                ('category_2', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quick_entry_3', to='tracker.PurchaseCategory', verbose_name='Category 2')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quick_entry_1', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Purchase',
                'verbose_name_plural': 'Purchases',
            },
        ),
    ]
