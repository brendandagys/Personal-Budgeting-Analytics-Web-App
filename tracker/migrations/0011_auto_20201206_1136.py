# Generated by Django 2.2.2 on 2020-12-06 11:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0010_auto_20201206_1108'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchase',
            name='category',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='category_1', to='tracker.PurchaseCategory', verbose_name='Category'),
        ),
        migrations.AlterField(
            model_name='purchase',
            name='category_2',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='category_2', to='tracker.PurchaseCategory', verbose_name='Category 2'),
        ),
    ]