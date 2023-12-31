# Generated by Django 3.2.15 on 2023-05-30 15:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_boundary', '0002_auto_20230516_0958'),
    ]

    operations = [
        migrations.AddField(
            model_name='commune',
            name='description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='commune',
            name='name_en',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tên xã EN'),
        ),
        migrations.AddField(
            model_name='country',
            name='description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='country',
            name='name_en',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True, verbose_name='Tên đất nước EN'),
        ),
        migrations.AddField(
            model_name='district',
            name='description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='district',
            name='name_en',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tên huyện EN'),
        ),
        migrations.AddField(
            model_name='province',
            name='description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='province',
            name='name_en',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tên tỉnh EN'),
        ),
        migrations.AlterField(
            model_name='commune',
            name='name',
            field=models.CharField(max_length=50, verbose_name='Tên xã VI'),
        ),
        migrations.AlterField(
            model_name='country',
            name='name',
            field=models.CharField(max_length=50, unique=True, verbose_name='Tên đất nước VN'),
        ),
        migrations.AlterField(
            model_name='district',
            name='name',
            field=models.CharField(max_length=50, verbose_name='Tên huyện VI'),
        ),
        migrations.AlterField(
            model_name='history_commune',
            name='info',
            field=models.JSONField(default=dict, verbose_name='Thông tin chỉnh sửa'),
        ),
        migrations.AlterField(
            model_name='history_district',
            name='info',
            field=models.JSONField(default=dict, verbose_name='Thông tin chỉnh sửa'),
        ),
        migrations.AlterField(
            model_name='history_province',
            name='info',
            field=models.JSONField(default=dict, verbose_name='Thông tin chỉnh sửa'),
        ),
        migrations.AlterField(
            model_name='province',
            name='name',
            field=models.CharField(max_length=50, verbose_name='Tên tỉnh VN'),
        ),
    ]
