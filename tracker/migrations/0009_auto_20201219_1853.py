# Generated by Django 2.2.2 on 2020-12-19 18:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0008_auto_20201218_2252'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='filter',
            options={'ordering': ['id'], 'verbose_name': 'Filter', 'verbose_name_plural': 'Filters'},
        ),
    ]
