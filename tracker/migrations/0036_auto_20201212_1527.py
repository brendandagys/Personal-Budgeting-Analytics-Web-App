# Generated by Django 2.2.2 on 2020-12-12 15:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0035_auto_20201212_0845'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='id',
            field=models.AutoField(auto_created=True, default=1, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='bill',
            name='bill',
            field=models.CharField(max_length=40, verbose_name='Bill'),
        ),
    ]
