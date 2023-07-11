import json
import traceback
from .core import mapdata
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import model_meta
from .models import Province, Commune, District, Country
from rest_framework import serializers


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ('id', 'name')


class ProvinceDetailSerializer(serializers.ModelSerializer):
    geom = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Province
        fields = ('id', 'name', 'name_en', 'description', 'id_parent', 'geom')

    def get_geom(self, obj):
        if obj.geom:
            return json.loads(obj.geom.geojson)
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        is_contain_geom, geom_data = mapdata(request=request)
        try:
            if is_contain_geom:
                validated_data['geom'] = geom_data
        except:
            pass
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        try:
            instance = ModelClass._default_manager.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                    'Got a `TypeError` when calling `%s.%s.create()`. '
                    'This may be because you have a writable field on the '
                    'serializer class that is not a valid argument to '
                    '`%s.%s.create()`. You may need to make the field '
                    'read-only, or override the %s.create() method to handle '
                    'this correctly.\nOriginal exception was:\n %s' %
                    (
                        ModelClass.__name__,
                        ModelClass._default_manager.name,
                        ModelClass.__name__,
                        ModelClass._default_manager.name,
                        self.__class__.__name__,
                        tb
                    )
            )
            raise TypeError(msg)
        return instance

    def update(self, instance, validated_data):
        request = self.context.get('request')
        is_contain_geom, geom_data = mapdata(request=request)
        try:
            if is_contain_geom:
                validated_data['geom'] = geom_data
        except:
            pass
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(instance)
        m2m_fields = []
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                m2m_fields.append((attr, value))
            else:
                setattr(instance, attr, value)

        instance = super().update(instance, validated_data)

        return instance


class DistrictDetailSerializer(serializers.ModelSerializer):
    geom = serializers.SerializerMethodField(required=False)

    class Meta:
        model = District
        fields = ('id', 'name', 'name_en', 'description', 'id_parent', 'geom')

    def get_geom(self, obj):
        if obj.geom:
            return json.loads(obj.geom.geojson)

    def create(self, validated_data):
        request = self.context.get('request')
        is_contain_geom, geom_data = mapdata(request=request)
        try:
            if is_contain_geom:
                validated_data['geom'] = geom_data
        except:
            pass
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        try:
            instance = ModelClass._default_manager.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                    'Got a `TypeError` when calling `%s.%s.create()`. '
                    'This may be because you have a writable field on the '
                    'serializer class that is not a valid argument to '
                    '`%s.%s.create()`. You may need to make the field '
                    'read-only, or override the %s.create() method to handle '
                    'this correctly.\nOriginal exception was:\n %s' %
                    (
                        ModelClass.__name__,
                        ModelClass._default_manager.name,
                        ModelClass.__name__,
                        ModelClass._default_manager.name,
                        self.__class__.__name__,
                        tb
                    )
            )
            raise TypeError(msg)
        return instance


class CommuneDetailSerializer(serializers.ModelSerializer):
    geom = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Commune
        fields = ('id', 'name', 'name_en', 'description', 'id_parent', 'geom')

    def get_geom(self, obj):
        if obj.geom:
            return json.loads(obj.geom.geojson)

    def create(self, validated_data):
        request = self.context.get('request')
        is_contain_geom, geom_data = mapdata(request=request)
        try:
            if is_contain_geom:
                validated_data['geom'] = geom_data
        except:
            pass
        raise_errors_on_nested_writes('create', self, validated_data)
        ModelClass = self.Meta.model
        try:
            instance = ModelClass._default_manager.create(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                    'Got a `TypeError` when calling `%s.%s.create()`. '
                    'This may be because you have a writable field on the '
                    'serializer class that is not a valid argument to '
                    '`%s.%s.create()`. You may need to make the field '
                    'read-only, or override the %s.create() method to handle '
                    'this correctly.\nOriginal exception was:\n %s' %
                    (
                        ModelClass.__name__,
                        ModelClass._default_manager.name,
                        ModelClass.__name__,
                        ModelClass._default_manager.name,
                        self.__class__.__name__,
                        tb
                    )
            )
            raise TypeError(msg)
        return instance
