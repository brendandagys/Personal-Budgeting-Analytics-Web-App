# Generated by Django 2.2.2 on 2020-12-07 21:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0019_auto_20201207_2107'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchase',
            name='category_2',
        ),
    ]