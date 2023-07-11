import uuid
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models

try:
    from django.db.models import JSONField
except ImportError:
    from django.contrib.postgres.fields import JSONField


class Country(models.Model):
    uuid = models.UUIDField(verbose_name='STT', default=uuid.uuid4)
    id = models.IntegerField(primary_key=True, verbose_name='Mã đất nước')
    name = models.CharField(max_length=50, unique=True, verbose_name='Tên đất nước VN')
    name_en = models.CharField(max_length=50, null=True, blank=True, unique=True, verbose_name='Tên đất nước EN')
    description = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_country'
        verbose_name_plural = 'Đất nước'

    def __str__(self):
        tmp = str(int(self.id)) + ' - ' + self.name
        return tmp


class Province(models.Model):
    uuid = models.UUIDField(verbose_name='STT', default=uuid.uuid4)
    id = models.IntegerField(primary_key=True, unique=True, verbose_name='Mã tỉnh')
    name = models.CharField(max_length=50, verbose_name='Tên tỉnh VN')
    name_en = models.CharField(max_length=50, null=True, blank=True, verbose_name='Tên tỉnh EN')
    id_parent = models.ForeignKey(Country, on_delete=models.CASCADE,
                                  db_column='id_country')
    geom = models.MultiPolygonField(srid=4326, verbose_name='Bản đồ', null=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_province'
        verbose_name_plural = 'Tỉnh - Thành phố'

    def __str__(self):
        tmp = str(int(self.id)) + '-' + str(self.name)
        return tmp


class District(models.Model):
    uuid = models.UUIDField(verbose_name='STT', default=uuid.uuid4)
    id = models.IntegerField(primary_key=True, unique=True, verbose_name='Mã huyện')
    name = models.CharField(max_length=50, verbose_name='Tên huyện VI')
    name_en = models.CharField(max_length=50, null=True, blank=True, verbose_name='Tên huyện EN')
    id_parent = models.ForeignKey(Province, on_delete=models.CASCADE,
                                  db_column='id_province')
    geom = models.MultiPolygonField(srid=4326, verbose_name='Bản đồ', null=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_district'
        verbose_name_plural = 'Quận - Huyện - Thị xã '

    def __str__(self):
        tmp = str(int(self.id)) + ' - ' + self.name
        return tmp


class Commune(models.Model):
    uuid = models.UUIDField(verbose_name='STT', default=uuid.uuid4)
    id = models.IntegerField(primary_key=True, unique=True, verbose_name='Mã xã')
    name = models.CharField(max_length=50, verbose_name='Tên xã VI')
    name_en = models.CharField(max_length=50, null=True, blank=True, verbose_name='Tên xã EN')
    id_parent = models.ForeignKey(District, on_delete=models.CASCADE,
                                  db_column='id_district')

    geom = models.MultiPolygonField(srid=4326, verbose_name='Bản đồ', null=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_commune'
        verbose_name_plural = 'Xã/ Phường/ Thị trấn'

    def __str__(self):
        tmp = str(int(self.id)) + ' - ' + self.name
        return tmp


class history_province(models.Model):
    uuid = models.UUIDField(verbose_name='uuid', default=uuid.uuid4, primary_key=True)
    id = models.CharField(max_length=200, verbose_name='id')
    time = models.DateTimeField(auto_now_add=True, blank=True, verbose_name='Thời gian')
    info = JSONField(verbose_name='Thông tin chỉnh sửa', default=dict)
    geom = models.MultiPolygonField(srid=4326, verbose_name='Bản đồ', null=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_history_province'
        verbose_name_plural = 'Lịch sử chỉnh sửa tỉnh - Thành phố'

    def __str__(self):
        tmp = str(self.time) + str(self.uuid)
        return tmp


class history_district(models.Model):
    uuid = models.UUIDField(verbose_name='uuid', default=uuid.uuid4, primary_key=True)
    id = models.CharField(max_length=200, verbose_name='id')
    time = models.DateTimeField(auto_now_add=True, blank=True, verbose_name='Thời gian')
    info = JSONField(verbose_name='Thông tin chỉnh sửa', default=dict)
    geom = models.MultiPolygonField(srid=4326, verbose_name='Bản đồ', null=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_history_district'
        verbose_name_plural = 'Lịch sử chỉnh sửa quận - huyện'

    def __str__(self):
        tmp = str(self.time) + str(self.uuid)
        return tmp


class history_commune(models.Model):
    uuid = models.UUIDField(verbose_name='uuid', default=uuid.uuid4, primary_key=True)
    id = models.CharField(max_length=200, verbose_name='id')
    time = models.DateTimeField(auto_now_add=True, blank=True, verbose_name='Thời gian')
    info = JSONField(verbose_name='Thông tin chỉnh sửa', default=dict)
    geom = models.MultiPolygonField(srid=4326, verbose_name='Bản đồ', null=True)

    class Meta:
        ordering = ['id']
        db_table = 'tb_history_commune'
        verbose_name_plural = 'Lịch sử chỉnh sửa xã - phường - thị trấn'

    def __str__(self):
        tmp = str(self.time) + str(self.uuid)
        return tmp
