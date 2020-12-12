# Generated by Django 2.2.2 on 2020-12-08 19:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0027_auto_20201208_1744'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='accountupdate',
            options={'ordering': ['-timestamp'], 'verbose_name': 'Account Update', 'verbose_name_plural': 'Account Updates'},
        ),
        migrations.AlterField(
            model_name='accountupdate',
            name='account',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='tracker.Account', verbose_name='Account'),
        ),
        migrations.AlterField(
            model_name='accountupdate',
            name='value',
            field=models.DecimalField(decimal_places=2, max_digits=9, verbose_name='Value'),
        ),
    ]