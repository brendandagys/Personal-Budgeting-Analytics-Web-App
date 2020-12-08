# Generated by Django 2.2.2 on 2020-12-06 10:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_auto_20200228_2323'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=30, verbose_name='Category')),
            ],
            options={
                'verbose_name': 'Purchase Category',
                'verbose_name_plural': 'Purchase Categories',
            },
        ),
    ]