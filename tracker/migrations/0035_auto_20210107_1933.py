# Generated by Django 2.2.2 on 2021-01-07 19:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0034_recurring_category'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='recurring',
            name='xth_after_specific_date',
        ),
        migrations.AddField(
            model_name='recurring',
            name='xth_from_specific_date',
            field=models.DateField(blank=True, null=True, verbose_name='Xth From Specific Date'),
        ),
    ]
