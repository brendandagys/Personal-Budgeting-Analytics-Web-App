# Generated by Django 2.2.2 on 2021-01-10 21:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0040_auto_20210110_1848'),
    ]

    operations = [
        migrations.RenameField(
            model_name='filter',
            old_name='amount',
            new_name='maximum_amount',
        ),
    ]