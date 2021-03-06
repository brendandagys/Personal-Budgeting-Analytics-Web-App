# Generated by Django 3.1.7 on 2021-02-19 20:17

from django.db import migrations, models
import django.db.models.deletion
import tracker.models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0047_auto_20210122_2213'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountupdate',
            name='purchase',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='account_updates_2', to='tracker.purchase', verbose_name='Purchase'),
        ),
        migrations.AlterField(
            model_name='accountupdate',
            name='timestamp',
            field=models.DateTimeField(default=tracker.models.current_datetime, verbose_name='Account Timestamp'),
        ),
    ]
