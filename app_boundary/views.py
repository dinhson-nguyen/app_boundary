import os
import re
from datetime import datetime
import datetime
import json

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from app_api_gate_way.paginator import CustomPagination
from backend.cores import no_accent_vietnamese
from .core import get_file_shp, get_file_geojson, get_data_dict, get_histoy_data, get_info_excel, get_history_excel
import requests
from rest_framework.exceptions import ValidationError
from .models import Province, Commune, District, Country, history_district, history_province, history_commune
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from shapely.geometry import Polygon
from django.contrib.gis.geos import MultiPolygon, Polygon
import urllib.request
import urllib.parse
from .serializer import ProvinceDetailSerializer, DistrictDetailSerializer, CommuneDetailSerializer, CountrySerializer
from .core import savehistory, createjson, unique_geom, get_data_from_map4d


class CountryViewSet(viewsets.ModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer


class ProvinceViewSet(viewsets.ModelViewSet):
    pagination_class = CustomPagination

    def get_queryset(self):
        if self.action == 'list':
            queryset = Province.objects.filter(is_active=True).values('id', 'name', 'name_en', 'description',
                                                                      'id_parent')
        else:
            queryset = Province.objects.filter(is_active=True)
        request = self.request
        q = request.query_params.get('q')
        if q:
            list_search_name = [obj['id'] for obj in queryset if
                                re.search(no_accent_vietnamese(q).lower(),
                                          no_accent_vietnamese(obj['name']).lower())]
            list_search_en = [obj['id'] for obj in queryset if
                              re.search(no_accent_vietnamese(q).lower(),
                                        no_accent_vietnamese(obj['name_en']).lower())]
            list_search_des = [obj['id'] for obj in queryset if
                               re.search(no_accent_vietnamese(q).lower(),
                                         no_accent_vietnamese(obj['description']).lower())]
            list_search = {*list_search_name, *list_search_en, *list_search_des}
            queryset = queryset.filter(id__in=list_search)
        return queryset

    def get_serializer_class(self):
        if self.action in ['list']:
            return None
        return ProvinceDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        results = []
        for obj in queryset:
            results.append(
                {
                    'id': obj['id'],
                    'name': obj['name'],
                    'id_parent': obj['id_parent'],
                }
            )
        page = self.paginate_queryset(results)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(results)

    @action(detail=False, methods=['post'], url_path='upload-list')
    def upload_list_province(self, request):
        data = request.FILES.get('data')
        if not data:
            return Response('Expected file data!', status=400)
        file_name = default_storage.save(f'{data.name}', ContentFile(data.read()))
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        extension = data.name.split('.')[-1]
        created = 0
        if 'shp' in extension:
            return Response("Not supported yet!", status=400)

        elif 'geojson' in extension:
            with open(file_path, encoding="utf8") as f:
                data = json.load(f)
                features = data['features']
                for data in features:
                    property_data = data['properties']
                    matinh = int(property_data['MATINH'])

                    tentinh = property_data['TINH']
                    geometry = data['geometry']['coordinates']
                    poly = geometry[0]
                    polygons = []
                    for po in poly:
                        polygon = Polygon(po)
                        polygons.append(polygon)
                    multipolygon = MultiPolygon(polygons)

                    my_model = Province(id=matinh, name=tentinh, id_parent_id=84, geom=multipolygon)
                    my_model.save()
                    created += 1
        else:
            os.remove(file_path)
            return Response({"file not supported": f"file does not supported "}, status=400)
        os.remove(file_path)
        return Response({'message': f'Created {created} province successfully!'})

    @action(detail=False, methods=['patch'], url_path='unique')
    def unique(self, request):
        id_1 = request.data.get('id_1')
        id_2 = request.data.get('id_2')
        new_id = request.data.get('new_id', None)
        geom = request.data.get('geom', None)
        new_name = request.data.get('new_name', None)
        try:
            obj_1 = Province.objects.filter(is_active=True).get(id=id_1)
        except Province.DoesNotExist:
            raise ValidationError({"Province": f"Province does not exist with id {id_1}"})
        try:
            obj_2 = Province.objects.filter(is_active=True).get(id=id_2)
        except Province.DoesNotExist:
            raise ValidationError({"Province": f"Province does not exist with id {id_2}"})
        if new_name is None:
            new_name = obj_1.name

        if geom is None:
            geom = unique_geom(obj_1=obj_1, obj_2=obj_2)
        if new_id is None:
            new_id = id_1

        if new_id == id_1:
            District.objects.filter(id_parent=obj_2.id).update(id_parent=obj_1.id)
            new_obj = Province.objects.filter(is_active=True).get(id=new_id)

            serializer = self.get_serializer(new_obj,
                                             data={'id': new_id, 'name': new_name,
                                                   'id_parent': Country.objects.get(id=84).pk})
            if serializer.is_valid():
                serializer.validated_data['geom'] = geom

            serializer.save()

            jsondata = createjson('unique', old=obj_1, new=new_obj)
            savehistory(model=history_province, uuid=obj_1.uuid, jsondata=jsondata, geom=obj_1.geom)
            jsondata = createjson('delete', obj_2, None)
            savehistory(model=history_province, uuid=obj_2.uuid, jsondata=jsondata, geom=obj_2.geom)

            # obj_2.delete()
            obj_2.is_active = False
            obj_2.save()

            response = {'id': new_obj.id, 'name': new_obj.name, 'id_parent': new_obj.id_parent.pk,
                        'geom': json.loads(new_obj.geom.geojson)}
            return Response(response, status=status.HTTP_202_ACCEPTED)
        if new_id == id_2:
            District.objects.filter(id_parent=obj_1.id).update(id_parent=obj_2.id)
            new_obj = Province.objects.filter(is_active=True).get(id=new_id)
            serializer = self.get_serializer(new_obj,
                                             data={'id': new_id, 'name': new_name,
                                                   'id_parent': Country.objects.get(id=84)},
                                             partial=True)
            if serializer.is_valid():
                serializer.validated_data['geom'] = geom
            serializer.save()

            jsondata = createjson('unique', old=obj_2, new=new_obj)

            savehistory(model=history_province, uuid=obj_2.uuid, jsondata=jsondata, geom=obj_2.geom)
            jsondata = createjson('delete', obj_1, None)
            savehistory(model=history_province, uuid=obj_1.uuid, jsondata=jsondata, geom=obj_1.geom)
            # obj_1.delete()
            obj_1.is_active = False
            obj_1.save()
            response = {'id': obj_2.id, 'name': obj_2.name, 'id_parent': obj_2.id_parent.pk,
                        'geom': json.loads(obj_2.geom.geojson)}
            return Response(response, status=status.HTTP_202_ACCEPTED)

    def create(self, request, *args, **kwargs):

        try:
            obj = Province.objects.filter(is_active=False).get(id=request.data.get('id'))
        except Province.DoesNotExist:
            obj = None
        if obj is None:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        else:
            serializer = self.get_serializer(obj, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            obj.is_active = True
            obj.save()

        new = Province.objects.filter(is_active=True).get(id=request.data.get('id'))
        jsondata = createjson(event='create', old=None, new=new)
        savehistory(history_province, new.uuid, jsondata, new.geom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        ddobj = Province.objects.filter(is_active=True).get(id=obj.id)

        jsondata = createjson('delete', ddobj, None)
        savehistory(history_province, ddobj.uuid, jsondata, ddobj.geom)
        # obj.delete()
        obj.is_active = False
        obj.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def partial_update(self, request, *args, **kwargs):
        id = request.data.get('id', None)
        name = request.data.get('name', None)
        geom = request.data.get('geom', None)

        id_parent = request.data.get('id_parent', None)
        objold = self.get_object()
        old = Province.objects.filter(is_active=True).get(id=objold.id)
        event = 'update'
        if geom:
            k = old.geom.wkt
            if str(request.data.get('geom')) != str(k):
                event += '-map'
        if id:
            if str(id) != str(old.id):
                event += '-id'
        if name:
            if name != old.name:
                event += '-name'
        if id_parent:
            if str(id_parent) != str(old.id_parent.pk):
                event += '-id_parent'
        if id is None:
            id = objold.id
        if name is None:
            name = objold.name
        if id_parent is None:
            id_parent = Country.objects.get(id=84).pk
        else:
            id_parent = Country.objects.get(id=84).pk
        if geom is None:
            geom = objold.geom
        try:
            m = Province.objects.filter(is_active=False).get(id=id)
            m.delete()
        except Province.DoesNotExist:
            pass

        serializer = self.get_serializer(old, data={'id': id, 'name': name, 'id_parent': id_parent, 'geom': geom})
        if serializer.is_valid():
            serializer.validated_data['geom'] = geom
        serializer.is_valid(raise_exception=True)
        serializer.save()

        new = Province.objects.filter(is_active=True).get(id=id)
        jsondata = createjson(event, objold, new)
        if event != 'update':
            savehistory(history_province, new.uuid, jsondata, geom=objold.geom)
        District.objects.filter(id_parent=objold.id).update(id_parent=id)
        if request.data.get('id', None) is not None:
            if str(new.id) != str(objold.id):
                objold.is_active = False
                objold.save()
                # old.delete()

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'], url_path='import/map4d')
    def import_map4d(self, request):
        data = get_data_from_map4d(request, Province)
        try:
            obj = Province.objects.filter(is_active=False).get(id=data.get('id'))
        except Province.DoesNotExist:
            obj = None
        if obj is None:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        else:
            serializer = self.get_serializer(obj, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            obj.is_active = True
            obj.save()

        new = Province.objects.filter(is_active=True).get(id=data.get('id'))
        jsondata = createjson(event='create', old=None, new=new)
        savehistory(history_province, new.uuid, jsondata, new.geom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='export/excel')
    def exportbyId_excel(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = Province.objects.filter(id=instance.pk)
        return get_info_excel(query=query, field_query=Province, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/geojson')
    def exportbyId_geojson(self, request, pk):
        file_name = request.query_params.get('file_name', None)
        instance = self.get_object()
        if file_name is None:
            file_name = str(instance)
        query = Province.objects.filter(id=instance.pk)
        collection = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collection)

    @action(detail=True, methods=['get'], url_path='export/shp')
    def exportbyId_shp(self, request, pk):
        file_name = request.query_params.get('file_name', None)
        instance = self.get_object()
        if file_name is None:
            file_name = str(instance)
        query = Province.objects.filter(id=instance.pk)
        collection = get_data_dict(queryset=query)
        return get_file_shp(colection=collection, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/history/excel')
    def export_history_byId_excel(self, request, pk):
        instance = self.get_object()
        query = Province.objects.filter(id=instance.pk)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        file_name = request.query_params.get('file_name', None)
        if not file_name:
            file_name = 'history' + str(instance)
        return get_history_excel(query=query, history_query_model=history_province,
                                 time_check=time_check, field_query=Province, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/history/geojson')
    def export_history_byId_geojson(self, request, pk):
        file_name = request.query_params.get('file_name', None)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        instance = self.get_object()
        if file_name is None:
            file_name = 'history' + str(instance)
        query = Province.objects.filter(id=instance.pk)
        collection = get_histoy_data(queryset=query, history_query_model=history_province, time_check=time_check)

        return get_file_geojson(file_name=file_name, collection=collection)

    @action(detail=True, methods=['get'], url_path='export/history/shp')
    def export_history_byId_shp(self, request, pk):
        file_name = request.query_params.get('file_name', None)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        instance = self.get_object()
        if file_name is None:
            file_name = ' history' + str(instance)
        query = Province.objects.filter(id=instance.pk)
        collection = get_histoy_data(queryset=query, history_query_model=history_province,
                                     time_check=time_check)

        return get_file_shp(colection=collection, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/excel')
    def export_all(self, request):
        query = Province.objects.filter(is_active=True)
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'Province'
        return get_info_excel(query=query, field_query=Province, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/geojson')
    def export_geojson(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'Province'
        query = Province.objects.filter(is_active=True)
        collection = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collection)

    @action(detail=False, methods=['get'], url_path='export/shp')
    def export_shp(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'Province'
        query = Province.objects.filter(is_active=True)
        collection = get_data_dict(queryset=query)
        return get_file_shp(colection=collection, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/excel')
    def export_history_all(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'history' + 'Province'
        query = Province.objects.filter(is_active=True)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        return get_history_excel(query=query, history_query_model=history_province,
                                 time_check=time_check, field_query=Province, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/geojson')
    def export_history_geojson(self, request):
        file_name = request.query_params.get('file_name', None)

        if file_name is None:
            file_name = 'history' + 'Province'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        query = Province.objects.filter(is_active=True)
        collection = get_histoy_data(queryset=query, history_query_model=history_province, time_check=time_check)
        return get_file_geojson(file_name=file_name, collection=collection)

    @action(detail=False, methods=['get'], url_path='export/history/shp')
    def export_history_shp(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'history' + 'Province'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        query = Province.objects.filter(is_active=True)
        collection = get_histoy_data(queryset=query, history_query_model=history_province, time_check=time_check)
        return get_file_shp(colection=collection, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='compare_history')
    def compare_history(self, request, pk):
        try:
            obj_now = Province.objects.filter(is_active=True).get(id=pk)
        except Province.DoesNotExist:
            raise ValidationError({"Province": f"Province does not exist with id {pk}"})
        time_check = request.query_params.get('time')
        try:
            target = datetime.datetime.strptime(time_check, '%d/%m/%Y')
        except:
            raise ValidationError({'time': "Wrong format. Expected '%d/%m/%Y'"})
        history = history_province.objects.filter(id=Province.objects.filter(is_active=True).get(id=pk).uuid).filter(
            time__gte=target)
        if not history:
            return Response(['no data display'])
        get_obj = history[0]

        if get_obj:
            different = obj_now.geom.difference(get_obj.geom)
            return Response({'time': get_obj.time, 'map': json.loads(different.geojson)})

    @action(detail=True, methods=['get'], url_path='compare_datamap4d')
    def compare_datamap4d(self, request, pk):
        object_map4d = request.query_params.get('id')

        try:
            obj_dlhc = Province.objects.filter(is_active=True).get(id=pk)
        except Province.DoesNotExist:
            raise ValidationError({"Province": f"Province does not exist with id {pk}"})
        api_link = f'https://api-app.map4d.vn/map/place/detail/{object_map4d}'

        response = urllib.request.urlopen(api_link)
        data = response.read()
        json_str = data.decode('utf-8')
        json_dict = json.loads(json_str)
        coordinates = json_dict.get('result').get('geometry').get('coordinates')
        poly = coordinates[0]
        polygons = []
        for item in poly:
            polygon = Polygon(item)
            polygons.append(polygon)
        multipolygon = MultiPolygon(polygons)

        different = obj_dlhc.geom.difference(multipolygon)
        return Response(json.loads(different.geojson))

    @action(detail=True, methods=['get'], url_path='compare_byname')
    def compare_byname(self, request, pk):
        name = request.query_params.get('name')
        url = 'https://api-app.map4d.vn/map/autosuggest?text=' + urllib.parse.quote(name)
        json_dict = requests.get(url).json()

        try:
            compare_obj = Province.objects.filter(is_active=True).get(id=pk)
        except Province.DoesNotExist:
            raise ValidationError({"Province": f"Province does not exist with id {pk}"})
        result = None

        for item in json_dict.get('result'):

            if str(item.get('name')) == str(compare_obj.name):
                result = item

        if result:
            link_url = 'https://api-app.map4d.vn/map/place/detail/' + str(result.get('id'))
            json_dict = requests.get(link_url).json()
            if json_dict.get('code') != 'ok' and 'admin_level_2' in json_dict.get('type'):
                raise ValidationError(f'Can not get place by {name}')

            coordinates = json_dict.get('result').get('geometry').get('coordinates')

            poly = coordinates[0]
            polygons = []
            for item in poly:
                polygon = Polygon(item)
                polygons.append(polygon)
            multipolygon = MultiPolygon(polygons)

            different = compare_obj.geom.difference(multipolygon)
        else:
            return Response(['No data'])

        return Response(json.loads(different.geojson))


class DistrictViewSet(viewsets.ModelViewSet):
    pagination_class = CustomPagination

    def get_queryset(self):
        if self.action == 'list':
            queryset = District.objects.filter(is_active=True).values('id', 'name', 'name_en', 'description',
                                                                      'id_parent')
        else:
            queryset = District.objects.filter(is_active=True)
        request = self.request
        q = request.query_params.get('q')
        if q:
            list_search_name = [obj['id'] for obj in queryset if
                                re.search(no_accent_vietnamese(q).lower(),
                                          no_accent_vietnamese(obj['name']).lower())]
            list_search_en = [obj['id'] for obj in queryset if
                              re.search(no_accent_vietnamese(q).lower(),
                                        no_accent_vietnamese(obj['name_en']).lower())]
            list_search_des = [obj['id'] for obj in queryset if
                               re.search(no_accent_vietnamese(q).lower(),
                                         no_accent_vietnamese(obj['description']).lower())]
            list_search = {*list_search_name, *list_search_en, *list_search_des}
            queryset = queryset.filter(id__in=list_search)
        matinh = request.query_params.get('matinh')
        if matinh:
            queryset = queryset.filter(id_parent_id=matinh)
        return queryset

    def get_serializer_class(self):
        if self.action in ['list']:
            return None
        return DistrictDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        results = []
        for obj in queryset:
            results.append(
                {
                    'id': obj['id'],
                    'name': obj['name'],
                    'id_parent': obj['id_parent'],
                }
            )
        page = self.paginate_queryset(results)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(results)

    @action(detail=False, methods=['post'], url_path='upload-list')
    def upload_list_district(self, request):
        data = request.FILES.get('data')
        if not data:
            return Response('Expected file data!', status=400)
        file_name = default_storage.save(f'{data.name}', ContentFile(data.read()))
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        extension = data.name.split('.')[-1]
        created = 0
        if 'shp' in extension:
            return Response("Not supported yet!", status=400)

        elif 'geojson' in extension:
            with open(file_path, encoding="utf8") as f:
                data = json.load(f)
                features = data['features']
                for data in features:
                    property_data = data['properties']
                    matinh = int(property_data['MATINH'])
                    mahuyen = int(property_data['MAHUYEN'])
                    tenhuyen = property_data['HUYEN']
                    geometry = data['geometry']['coordinates']
                    poly = geometry[0]
                    polygons = []
                    for geometry in poly:
                        polygon = Polygon(geometry)
                        polygons.append(polygon)
                    multipolygon = MultiPolygon(polygons)

                    my_model = District(id=mahuyen, name=tenhuyen, id_parent_id=matinh, geom=multipolygon)
                    my_model.save()
                    created += 1
        else:
            os.remove(file_path)
            return Response({"file not supported": f"file does not supported "}, status=400)
        os.remove(file_path)
        return Response({'message': f'Created {created} province successfully!'})

    @action(detail=False, methods=['patch'], url_path='unique')
    def unique(self, request):
        id_1 = request.data.get('id_1')
        id_2 = request.data.get('id_2')
        new_id = request.data.get('new_id', None)
        geom = request.data.get('geom', None)
        new_name = request.data.get('new_name', None)
        try:
            obj_1 = District.objects.filter(is_active=True).get(id=id_1)
        except District.DoesNotExist:
            raise ValidationError({"District": f"District does not exist with id {id_1}"})
        try:
            obj_2 = District.objects.filter(is_active=True).get(id=id_2)
        except District.DoesNotExist:
            raise ValidationError({"District": f"District does not exist with id {id_2}"})
        if new_name is None:
            new_name = obj_1.name

        if geom is None:
            geom = unique_geom(obj_1=obj_1, obj_2=obj_2)
        if new_id is None:
            new_id = id_1

        if new_id == id_1:
            Commune.objects.filter(id_parent=obj_2.id).update(id_parent=obj_1.id)
            new_obj = District.objects.filter(is_active=True).get(id=new_id)

            serializer = self.get_serializer(new_obj,
                                             data={'id': new_id, 'name': new_name,
                                                   'id_parent': Province.objects.filter(is_active=True).get(
                                                       id=obj_1.id_parent.pk).pk})
            if serializer.is_valid():
                serializer.validated_data['geom'] = geom
            serializer.save()

            jsondata = createjson('unique', old=obj_1, new=new_obj)
            savehistory(model=history_district, uuid=obj_1.uuid, jsondata=jsondata, geom=obj_1.geom)
            jsondata = createjson('delete', obj_2, None)
            savehistory(model=history_district, uuid=obj_2.uuid, jsondata=jsondata, geom=obj_2.geom)

            # obj_2.delete()
            obj_2.is_active = False
            obj_2.save()

            response = {'id': obj_1.id, 'name': obj_1.name, 'id_parent': obj_1.id_parent.pk,
                        'geom': json.loads(obj_1.geom.geojson)}
            return Response(response, status=status.HTTP_202_ACCEPTED)
        if new_id == id_2:
            Commune.objects.filter(id_parent=obj_1.id).update(id_parent=obj_2.id)
            new_obj = District.objects.filter(is_active=True).get(id=new_id)
            serializer = self.get_serializer(new_obj,
                                             data={'id': new_id, 'name': new_name,
                                                   'id_parent': Province.objects.filter(is_active=True).get(
                                                       id=obj_2.id_parent.pk).pk})
            if serializer.is_valid():
                serializer.validated_data['geom'] = geom
            serializer.save()

            jsondata = createjson('unique', old=obj_2, new=new_obj)

            savehistory(model=history_district, uuid=obj_2.uuid, jsondata=jsondata, geom=obj_2.geom)
            jsondata = createjson('delete', obj_1, None)
            savehistory(model=history_district, uuid=obj_1.uuid, jsondata=jsondata, geom=obj_1.geom)
            # obj_1.delete()
            obj_1.is_active = False
            obj_1.save()
            response = {'id': obj_2.id, 'name': obj_2.name, 'id_parent': obj_2.id_parent.pk,
                        'geom': json.loads(obj_2.geom.geojson)}
            return Response(response, status=status.HTTP_202_ACCEPTED)

    def create(self, request, *args, **kwargs):
        try:
            obj = District.objects.filter(is_active=False).get(id=request.data.get('id'))
        except District.DoesNotExist:
            obj = None
        if obj is None:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        else:
            serializer = self.get_serializer(obj, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            obj.is_active = True
            obj.save()

        new = District.objects.filter(is_active=True).get(id=request.data.get('id'))
        jsondata = createjson(event='create', old=None, new=new)
        savehistory(history_district, new.uuid, jsondata, new.geom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['patch'], url_path='import/map4d')
    def import_map4d(self, request):
        data = get_data_from_map4d(request, District)
        try:
            obj = District.objects.filter(is_active=False).get(id=data.get('id'))
        except District.DoesNotExist:
            obj = None
        if obj is None:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        else:
            serializer = self.get_serializer(obj, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            obj.is_active = True
            obj.save()

        new = District.objects.filter(is_active=True).get(id=data.get('id'))
        jsondata = createjson(event='create', old=None, new=new)
        savehistory(history_district, new.uuid, jsondata, new.geom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        ddobj = District.objects.filter(is_active=True).get(id=obj.id)

        jsondata = createjson('delete', ddobj, None)
        savehistory(history_district, ddobj.uuid, jsondata, ddobj.geom)
        # obj.delete()
        obj.is_active = False
        obj.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def partial_update(self, request, *args, **kwargs):
        id = request.data.get('id', None)
        name = request.data.get('name', None)
        geom = request.data.get('geom', None)

        id_parent = request.data.get('id_parent', None)
        objold = self.get_object()
        old = District.objects.filter(is_active=True).get(id=objold.id)
        event = 'update'
        if geom:
            k = old.geom.wkt
            if str(request.data.get('geom')) != str(k):
                event += '-map'
        if id:
            if str(id) != str(old.id):
                event += '-id'
        if name:
            if name != old.name:
                event += '-name'
        if id_parent:
            if str(id_parent) != str(old.id_parent.pk):
                event += '-id_parent'
        if id is None:
            id = objold.id
        if name is None:
            name = objold.name
        if id_parent is None:
            id_parent = Province.objects.filter(is_active=True).get(id=old.id_parent.pk).pk
        else:
            id_parent = Province.objects.filter(is_active=True).get(id=id_parent).pk
        if geom is None:
            geom = objold.geom
        try:
            m = District.objects.filter(is_active=False).get(id=id)
            m.delete()
        except District.DoesNotExist:
            pass

        serializer = self.get_serializer(old, data={'id': id, 'name': name, 'id_parent': id_parent, 'geom': geom})
        if serializer.is_valid():
            serializer.validated_data['geom'] = geom
        serializer.is_valid(raise_exception=True)
        serializer.save()
        new = District.objects.filter(is_active=True).get(id=id)
        jsondata = createjson(event, old, new)
        if event != 'update':
            savehistory(history_district, new.uuid, jsondata, geom=old.geom)
        Commune.objects.filter(id_parent=old.id).update(id_parent=id)
        if request.data.get('id', None) is not None:
            if str(new.id) != str(objold.id):
                objold.is_active = False
                objold.save()
                # old.delete()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='export/excel')
    def exportbyId_excel(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = District.objects.filter(id=instance.pk)
        return get_info_excel(query=query, field_query=District, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/geojson')
    def exportbyId_geojson(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = District.objects.filter(id=instance.pk)
        collect = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=True, methods=['get'], url_path='export/shp')
    def exportbyId_shp(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = District.objects.filter(id=instance.pk)
        collect = get_data_dict(queryset=query)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/history/excel')
    def export_history_byId_excel(self, request, pk):
        instance = self.get_object()
        query = District.objects.filter(id=instance.pk)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        file_name = request.query_params.get('file_name', None)
        if not file_name:
            file_name = 'history' + str(instance)
        return get_history_excel(query=query, history_query_model=history_district,
                                 time_check=time_check, field_query=District, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/history/geojson')
    def export_history_byId_geojson(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'history' + str(instance)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        query = District.objects.filter(id=instance.pk)
        collection = get_histoy_data(queryset=query, history_query_model=history_district, time_check=time_check)
        return get_file_geojson(file_name=file_name, collection=collection)

    @action(detail=True, methods=['get'], url_path='export/history/shp')
    def export_history_byId_shp(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'history' + str(instance)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        query = District.objects.filter(id=instance.pk)
        collection = get_histoy_data(queryset=query, history_query_model=history_district, time_check=time_check)
        return get_file_shp(collection, file_name)

    @action(detail=False, methods=['get'], url_path='export/province/excel')
    def exportbyId_province_excel(self, request):
        param = request.query_params.get('id_province')
        try:
            instance = Province.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"Province": f"Provine does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance) + 'district'
        query = District.objects.filter(id_parent_id=instance.id)
        return get_info_excel(query=query, field_query=District, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/province/geojson')
    def exportbyId_province_geojson(self, request):
        param = request.query_params.get('id_province')
        try:
            instance = Province.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"Province": f"Provine does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance) + 'district'
        query = District.objects.filter(id_parent_id=instance.id)
        collect = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=False, methods=['get'], url_path='export/province/shp')
    def exportbyId_province_shp(self, request):
        param = request.query_params.get('id_province')
        try:
            instance = Province.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"Province": f"Provine does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance) + 'district'
        query = District.objects.filter(id_parent_id=instance.id)
        collect = get_data_dict(queryset=query)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/province/excel')
    def export_history_byId_province_excel(self, request):
        param = request.query_params.get('id_province')
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'timecheck': 'this field required'})
        try:
            instance = Province.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"Province": f"Provine does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + str(instance) + 'district'
        query = District.objects.filter(id_parent_id=instance.id)
        return get_history_excel(query=query, history_query_model=history_district,
                                 time_check=time_check, field_query=District, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/province/geojson')
    def export_history_byId_province_geojson(self, request, pk):
        param = request.query_params.get('id_province')
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'timecheck': 'this field required'})
        try:
            instance = Province.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"Province": f"Provine does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + str(instance) + 'district'
        query = District.objects.filter(id_parent_id=instance.id)
        collection = get_histoy_data(queryset=query, history_query_model=history_district, time_check=time_check)
        return get_file_geojson(file_name, collection)

    @action(detail=False, methods=['get'], url_path='export/history/province/shp')
    def export_history_byId_province_shp(self, request, pk):
        param = request.query_params.get('id_province')
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'timecheck': 'this field required'})
        try:
            instance = Province.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"Province": f"Provine does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + str(instance) + 'district'
        query = District.objects.filter(id_parent_id=instance.id)
        collection = get_histoy_data(queryset=query, history_query_model=history_district, time_check=time_check)
        return get_file_shp(collection, file_name)

    @action(detail=False, methods=['get'], url_path='export/excel')
    def export_all(self, request):
        query = District.objects.filter(is_active=True)
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'District'
        return get_info_excel(query=query, field_query=District, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/geojson')
    def export_geojson(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'District'
        query = District.objects.filter(is_active=True)
        collect = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=False, methods=['get'], url_path='export/shp')
    def export_shp(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'District'
        query = District.objects.filter(is_active=True)
        collect = get_data_dict(queryset=query)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/excel')
    def export_history_all(self, request):
        query = District.objects.filter(is_active=True)

        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + 'District'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        return get_history_excel(query=query, history_query_model=history_district,
                                 time_check=time_check, field_query=District, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/geojson')
    def export_history_geojson(self, request):
        query = District.objects.filter(is_active=True)

        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + 'District'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        collect = get_histoy_data(queryset=query, history_query_model=history_district, time_check=time_check)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=False, methods=['get'], url_path='export/history/shp')
    def export_history_shp(self, request):
        query = District.objects.filter(is_active=True)

        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + 'District'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        collect = get_histoy_data(queryset=query, history_query_model=history_district, time_check=time_check)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='compare_history')
    def compare_history(self, request, pk):
        try:
            obj_now = District.objects.filter(is_active=True).get(id=pk)
        except District.DoesNotExist:
            raise ValidationError({"District": f"District does not exist with id {pk}"})
        time_check = request.query_params.get('time')
        try:
            target = datetime.datetime.strptime(time_check, '%d/%m/%Y')
        except:
            raise ValidationError({'time': "Wrong format. Expected '%d/%m/%Y'"})
        history = history_district.objects.filter(id=District.objects.filter(is_active=True).get(id=pk).uuid).filter(
            time__gte=target)
        if not history:
            return Response(['no data display'])
        get_obj = history[0]

        if get_obj:
            different = obj_now.geom.difference(get_obj.geom)
            return Response({'time': get_obj.time, 'map': json.loads(different.geojson)})

    @action(detail=True, methods=['get'], url_path='compare_datamap4d')
    def compare_datamap4d(self, request, pk):
        object_map4d = request.query_params.get('id')

        try:
            obj_dlhc = District.objects.filter(is_active=True).get(id=pk)
        except District.DoesNotExist:
            raise ValidationError({"District": f"District does not exist with id {pk}"})
        api_link = f'https://api-app.map4d.vn/map/place/detail/{object_map4d}'

        response = urllib.request.urlopen(api_link)
        data = response.read()
        json_str = data.decode('utf-8')
        json_dict = json.loads(json_str)
        coordinates = json_dict.get('result').get('geometry').get('coordinates')
        poly = coordinates[0]
        polygons = []
        for item in poly:
            polygon = Polygon(item)
            polygons.append(polygon)
        multipolygon = MultiPolygon(polygons)

        different = obj_dlhc.geom.difference(multipolygon)
        return Response(json.loads(different.geojson))

    @action(detail=True, methods=['get'], url_path='compare_byname')
    def compare_byname(self, request, pk):
        name = request.query_params.get('name')
        url = 'https://api-app.map4d.vn/map/autosuggest?text=' + urllib.parse.quote(name)
        json_dict = requests.get(url).json()

        try:
            compare_obj = District.objects.filter(is_active=True).get(id=pk)
        except District.DoesNotExist:
            raise ValidationError({"District": f"District does not exist with id {pk}"})
        result = None

        for item in json_dict.get('result'):

            if str(item.get('name')) == str(compare_obj.name):
                result = item

        if result:
            link_url = 'https://api-app.map4d.vn/map/place/detail/' + str(result.get('id'))
            json_dict = requests.get(link_url).json()
            if json_dict.get('code') != 'ok' and 'admin_level_3' in json_dict.get('type'):
                raise ValidationError(f'Can not get place by {name}')

            coordinates = json_dict.get('result').get('geometry').get('coordinates')

            poly = coordinates[0]
            polygons = []
            for item in poly:
                polygon = Polygon(item)
                polygons.append(polygon)
            multipolygon = MultiPolygon(polygons)

            different = compare_obj.geom.difference(multipolygon)
        else:
            return Response(['No data'])

        return Response(json.loads(different.geojson))


class CommuneViewSet(viewsets.ModelViewSet):
    pagination_class = CustomPagination

    def get_queryset(self):
        if self.action == 'list':
            queryset = Commune.objects.filter(is_active=True).values('id', 'name', 'name_en', 'description',
                                                                     'id_parent')
        else:
            queryset = Commune.objects.filter(is_active=True)
        request = self.request
        q = request.query_params.get('q')
        if q:
            list_search_name = [obj['id'] for obj in queryset if
                                re.search(no_accent_vietnamese(q).lower(),
                                          no_accent_vietnamese(obj['name']).lower())]
            list_search_en = [obj['id'] for obj in queryset if
                              re.search(no_accent_vietnamese(q).lower(),
                                        no_accent_vietnamese(obj['name_en']).lower())]
            list_search_des = [obj['id'] for obj in queryset if
                               re.search(no_accent_vietnamese(q).lower(),
                                         no_accent_vietnamese(obj['description']).lower())]
            list_search = {*list_search_name, *list_search_en, *list_search_des}
            queryset = queryset.filter(id__in=list_search)
        mahuyen = request.query_params.get('mahuyen')
        if mahuyen:
            queryset = queryset.filter(id_parent_id=mahuyen)
        matinh = request.query_params.get('matinh')
        if matinh:
            queryset = queryset.filter(id_parent__id_parent_id=matinh)
        return queryset

    def get_serializer_class(self):
        if self.action in ['list']:
            return None
        return CommuneDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        results = []
        for obj in queryset:
            results.append(
                {
                    'id': obj['id'],
                    'name': obj['name'],
                    'id_parent': obj['id_parent'],
                }
            )
        page = self.paginate_queryset(results)
        if page is not None:
            return self.get_paginated_response(page)
        return Response(results)

    @action(detail=False, methods=['post'], url_path='upload-list')
    def upload_list_commune(self, request):
        data = request.FILES.get('data')
        if not data:
            return Response('Expected file data!', status=400)
        file_name = default_storage.save(f'{data.name}', ContentFile(data.read()))
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)
        extension = data.name.split('.')[-1]
        created = 0
        if 'shp' in extension:
            return Response("Not supported yet!", status=400)

        elif 'geojson' in extension:
            with open(file_path, encoding="utf8") as f:
                data = json.load(f)
                features = data['features']
                for data in features:
                    property_data = data['properties']
                    mahuyen = int(property_data['MAHUYEN'])
                    maxa = int(property_data['MAXA'])
                    if maxa:
                        tenxa = property_data['XA']
                        geometry = data['geometry']['coordinates']
                        poly = geometry[0]
                        polygons = []
                        for geometry in poly:
                            polygon = Polygon(geometry)
                            polygons.append(polygon)
                        multipolygon = MultiPolygon(polygons)
                        my_model = Commune(id=maxa, name=tenxa, id_parent_id=mahuyen, geom=multipolygon)
                        my_model.save()
                    created += 1
        else:
            os.remove(file_path)
            return Response({"file not supported": f"file does not supported "}, status=400)
        os.remove(file_path)
        return Response({'message': f'Created {created} province successfully!'})

    @action(detail=False, methods=['patch'], url_path='unique')
    def unique(self, request):
        id_1 = request.data.get('id_1')
        id_2 = request.data.get('id_2')
        new_id = request.data.get('new_id', None)
        geom = request.data.get('geom', None)
        new_name = request.data.get('new_name', None)
        try:
            obj_1 = Commune.objects.filter(is_active=True).get(id=id_1)
        except Commune.DoesNotExist:
            raise ValidationError({"Commune": f"Commune does not exist with id {id_1}"})
        try:
            obj_2 = Commune.objects.filter(is_active=True).get(id=id_2)
        except Commune.DoesNotExist:
            raise ValidationError({"Commune": f"Commune does not exist with id {id_2}"})
        if new_name is None:
            new_name = obj_1.name

        if geom is None:
            geom = unique_geom(obj_1, obj_2)

        if new_id is None:
            new_id = id_1

        if new_id == id_1:
            new_obj = Commune.objects.filter(is_active=True).get(id=new_id)

            serializer = self.get_serializer(new_obj,
                                             data={'id': new_id, 'name': new_name,
                                                   'id_parent': District.objects.filter(is_active=True).get(
                                                       id=obj_1.id_parent.pk).pk})
            if serializer.is_valid():
                serializer.validated_data['geom'] = geom
            serializer.save()

            jsondata = createjson('unique', old=obj_1, new=new_obj)
            savehistory(model=history_commune, uuid=obj_1.uuid, jsondata=jsondata, geom=obj_1.geom)
            jsondata = createjson('delete', obj_2, None)
            savehistory(model=history_commune, uuid=obj_2.uuid, jsondata=jsondata, geom=obj_2.geom)

            # obj_2.delete()
            obj_2.is_active = False
            obj_2.save()

            response = {'id': obj_1.id, 'name': obj_1.name, 'id_parent': obj_1.id_parent.pk,
                        'geom': json.loads(obj_1.geom.geojson)}
            return Response(response, status=status.HTTP_202_ACCEPTED)
        if new_id == id_2:
            new_obj = Commune.objects.filter(is_active=True).get(id=new_id)
            serializer = self.get_serializer(new_obj,
                                             data={'id': new_id, 'name': new_name,
                                                   'id_parent': District.objects.filter(is_active=True).get(
                                                       id=obj_2.id_parent.pk).pk})
            if serializer.is_valid():
                serializer.validated_data['geom'] = geom
            serializer.save()

            jsondata = createjson('unique', old=obj_2, new=new_obj)

            savehistory(model=history_commune, uuid=obj_2.uuid, jsondata=jsondata, geom=obj_2.geom)
            jsondata = createjson('delete', obj_1, None)
            savehistory(model=history_commune, uuid=obj_1.uuid, jsondata=jsondata, geom=obj_1.geom)
            # obj_1.delete()
            obj_1.is_active = False
            obj_1.save()
            response = {'id': obj_2.id, 'name': obj_2.name, 'id_parent': obj_2.id_parent.pk,
                        'geom': json.loads(obj_2.geom.geojson)}
            return Response(response, status=status.HTTP_202_ACCEPTED)

    def create(self, request, *args, **kwargs):
        try:
            obj = Commune.objects.filter(is_active=False).get(id=request.data.get('id'))
        except Commune.DoesNotExist:
            obj = None
        if obj is None:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        else:
            serializer = self.get_serializer(obj, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            obj.is_active = True
            obj.save()

        new = Commune.objects.filter(is_active=True).get(id=request.data.get('id'))
        jsondata = createjson(event='create', old=None, new=new)
        savehistory(history_commune, new.uuid, jsondata, new.geom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['patch'], url_path='import/map4d')
    def import_map4d(self, request):
        data = get_data_from_map4d(request, Commune)
        try:
            obj = Commune.objects.filter(is_active=False).get(id=data.get('id'))
        except Commune.DoesNotExist:
            obj = None
        if obj is None:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
        else:
            serializer = self.get_serializer(obj, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            obj.is_active = True
            obj.save()

        new = Commune.objects.filter(is_active=True).get(id=data.get('id'))
        jsondata = createjson(event='create', old=None, new=new)
        savehistory(history_commune, new.uuid, jsondata, new.geom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        ddobj = Commune.objects.filter(is_active=True).get(id=obj.id)

        jsondata = createjson('delete', ddobj, None)
        savehistory(history_commune, ddobj.uuid, jsondata, ddobj.geom)
        # obj.delete()
        obj.is_active = False
        obj.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def partial_update(self, request, *args, **kwargs):
        id = request.data.get('id', None)
        name = request.data.get('name', None)
        geom = request.data.get('geom', None)

        id_parent = request.data.get('id_parent', None)
        objold = self.get_object()
        old = Commune.objects.filter(is_active=True).get(id=objold.id)
        event = 'update'
        if geom:
            k = old.geom.wkt
            if str(request.data.get('geom')) != str(k):
                event += '-map'
        if id:
            if str(id) != str(old.id):
                event += '-id'
        if name:
            if name != old.name:
                event += '-name'
        if id_parent:
            if str(id_parent) != str(old.id_parent.pk):
                event += '-id_parent'
        if id is None:
            id = objold.id
        if name is None:
            name = objold.name
        if id_parent is None:
            id_parent = District.objects.filter(is_active=True).get(id=old.id_parent.pk).pk
        else:
            id_parent = District.objects.filter(is_active=True).get(id=id_parent).pk
        if geom is None:
            geom = objold.geom
        try:
            m = Commune.objects.filter(is_active=False).get(id=id)
            m.delete()
        except Commune.DoesNotExist:
            pass

        serializer = self.get_serializer(old, data={'id': id, 'name': name, 'id_parent': id_parent, 'geom': geom})
        if serializer.is_valid():
            serializer.validated_data['geom'] = geom
        serializer.is_valid(raise_exception=True)
        serializer.save()
        new = Commune.objects.filter(is_active=True).get(id=id)
        jsondata = createjson(event, old, new)
        if event != 'update':
            savehistory(history_commune, new.uuid, jsondata, geom=old.geom)

        if request.data.get('id', None) is not None:
            if str(new.id) != str(objold.id):
                objold.is_active = False
                objold.save()
                # old.delete()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='export/excel')
    def exportbyId_excel(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = Commune.objects.filter(id=instance.pk)
        return get_info_excel(query=query, field_query=Commune, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/geojson')
    def exportbyId_geojson(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = Commune.objects.filter(id=instance.pk)
        collect = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=True, methods=['get'], url_path='export/shp')
    def exportbyId_shp(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance)
        query = Commune.objects.filter(id=instance.pk)
        collect = get_data_dict(queryset=query)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/history/excel')
    def export_history_byId_excel(self, request, pk):
        instance = self.get_object()
        query = Commune.objects.filter(id=instance.pk)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        file_name = request.query_params.get('file_name', None)
        if not file_name:
            file_name = 'history' + str(instance)
        return get_history_excel(query=query, history_query_model=history_commune,
                                 time_check=time_check, field_query=Commune, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='export/history/geojson')
    def export_history_byId_geojson(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'history' + str(instance)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        query = Commune.objects.filter(id=instance.pk)
        collection = get_histoy_data(queryset=query, history_query_model=history_commune, time_check=time_check)
        return get_file_geojson(file_name=file_name, collection=collection)

    @action(detail=True, methods=['get'], url_path='export/history/shp')
    def export_history_byId_shp(self, request, pk):
        instance = self.get_object()
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'history' + str(instance)
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        query = Commune.objects.filter(id=instance.pk)
        collection = get_histoy_data(queryset=query, history_query_model=history_commune, time_check=time_check)
        return get_file_shp(collection, file_name)

    @action(detail=False, methods=['get'], url_path='export/district/excel')
    def exportbyId_district_excel(self, request):
        param = request.query_params.get('id_district')
        try:
            instance = District.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"District": f"District does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance) + 'commune'
        query = Commune.objects.filter(id_parent_id=instance.id)
        return get_info_excel(query=query, field_query=Commune, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/district/geojson')
    def exportbyId_district_geojson(self, request):
        param = request.query_params.get('id_district')
        try:
            instance = District.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"District": f"District does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance) + 'commune'
        query = Commune.objects.filter(id_parent_id=instance.id)
        collect = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=False, methods=['get'], url_path='export/district/shp')
    def exportbyId_District_shp(self, request):
        param = request.query_params.get('id_district')
        try:
            instance = District.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"District": f"District does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = str(instance) + 'commune'
        query = Commune.objects.filter(id_parent_id=instance.id)
        collect = get_data_dict(queryset=query)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/district/excel')
    def export_history_byId_district_excel(self, request):
        param = request.query_params.get('id_province')
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'timecheck': 'this field required'})
        try:
            instance = District.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"District": f"District does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + str(instance) + 'district'
        query = Commune.objects.filter(id_parent_id=instance.id)
        return get_history_excel(query=query, history_query_model=history_commune,
                                 time_check=time_check, field_query=Commune, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/district/geojson')
    def export_history_byId_district_geojson(self, request, pk):
        param = request.query_params.get('id_province')
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'timecheck': 'this field required'})
        try:
            instance = District.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"district": f"district does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + str(instance) + 'district'
        query = Commune.objects.filter(id_parent_id=instance.id)
        collection = get_histoy_data(queryset=query, history_query_model=history_commune, time_check=time_check)
        return get_file_geojson(file_name, collection)

    @action(detail=False, methods=['get'], url_path='export/history/district/shp')
    def export_history_byId_district_shp(self, request, pk):
        param = request.query_params.get('id_province')
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'timecheck': 'this field required'})
        try:
            instance = District.objects.filter(is_active=True).get(id=param)
        except:
            raise ValidationError({"District": f"District does not exist with id {param}"})
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + str(instance) + 'district'
        query = Commune.objects.filter(id_parent_id=instance.id)
        collection = get_histoy_data(queryset=query, history_query_model=history_commune, time_check=time_check)
        return get_file_shp(collection, file_name)

    @action(detail=False, methods=['get'], url_path='export/excel')
    def export_excel_all(self, request):
        query = Commune.objects.filter(is_active=True)
        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'commune'
        return get_info_excel(query=query, field_query=Commune, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/geojson')
    def export_geojson(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'Commune'
        query = Commune.objects.filter(is_active=True)
        collect = get_data_dict(queryset=query)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=False, methods=['get'], url_path='export/shp')
    def export_shp(self, request):
        file_name = request.query_params.get('file_name', None)
        if file_name is None:
            file_name = 'Commune'
        query = Commune.objects.filter(is_active=True)
        collect = get_data_dict(queryset=query)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/excel')
    def export_history_all(self, request):
        query = Commune.objects.filter(is_active=True)

        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + 'District'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        return get_history_excel(query=query, history_query_model=history_commune,
                                 time_check=time_check, field_query=Commune, file_name=file_name)

    @action(detail=False, methods=['get'], url_path='export/history/geojson')
    def export_history_geojson(self, request):
        query = Commune.objects.filter(is_active=True)

        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + 'Commune'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        collect = get_histoy_data(queryset=query, history_query_model=history_commune, time_check=time_check)
        return get_file_geojson(file_name=file_name, collection=collect)

    @action(detail=False, methods=['get'], url_path='export/history/shp')
    def export_history_shp(self, request):
        query = Commune.objects.filter(is_active=True)

        file_name = request.query_params.get('file_name')
        if file_name is None:
            file_name = 'history' + 'Commune'
        time_check = request.query_params.get('time_check', None)
        if time_check is None:
            raise ValidationError({'time_check': 'time_check required'})
        collect = get_histoy_data(queryset=query, history_query_model=history_commune, time_check=time_check)
        return get_file_shp(colection=collect, file_name=file_name)

    @action(detail=True, methods=['get'], url_path='compare_history')
    def compare_history(self, request, pk):
        time_check = request.query_params.get('time')
        try:
            obj_now = Commune.objects.filter(is_active=True).get(id=pk)
        except Commune.DoesNotExist:
            raise ValidationError({"Commune": f"Commune does not exist with id {pk}"})
        try:
            target = datetime.datetime.strptime(time_check, '%d/%m/%Y')
        except:
            raise ValidationError({'time': "Wrong format. Expected '%d/%m/%Y'"})
        history = history_commune.objects.filter(id=Commune.objects.filter(is_active=True).get(id=pk).uuid).filter(
            time__gte=target)
        if not history:
            return Response(['no data display'])
        get_obj = history[0]

        if get_obj:
            different = obj_now.geom.difference(get_obj.geom)
            return Response({'time': get_obj.time, 'map': json.loads(different.geojson)})

    @action(detail=True, methods=['get'], url_path='compare_datamap4d')
    def compare_datamap4d(self, request, pk):
        object_map4d = request.query_params.get('id')

        try:
            obj_dlhc = Commune.objects.filter(is_active=True).get(id=pk)
        except Commune.DoesNotExist:
            raise ValidationError({"Commune": f"Commune does not exist with id {pk}"})
        api_link = f'https://api-app.map4d.vn/map/place/detail/{object_map4d}'

        response = urllib.request.urlopen(api_link)
        data = response.read()
        json_str = data.decode('utf-8')
        json_dict = json.loads(json_str)
        coordinates = json_dict.get('result').get('geometry').get('coordinates')
        poly = coordinates[0]
        polygons = []
        for item in poly:
            polygon = Polygon(item)
            polygons.append(polygon)
        multipolygon = MultiPolygon(polygons)

        different = obj_dlhc.geom.difference(multipolygon)
        return Response(json.loads(different.geojson))

    @action(detail=True, methods=['get'], url_path='compare_byname')
    def compare_byname(self, request, pk):
        name = request.query_params.get('name')
        url = 'https://api-app.map4d.vn/map/autosuggest?text=' + urllib.parse.quote(name)
        json_dict = requests.get(url).json()

        try:
            compare_obj = Commune.objects.filter(is_active=True).get(id=pk)
        except Commune.DoesNotExist:
            raise ValidationError({"Commune": f"Commune does not exist with id {pk}"})
        result = None

        for item in json_dict.get('result'):

            if str(item.get('name')) == str(compare_obj.name):
                result = item

        if result:
            link_url = 'https://api-app.map4d.vn/map/place/detail/' + str(result.get('id'))
            json_dict = requests.get(link_url).json()
            if json_dict.get('code') != 'ok' and 'admin_level_4' in json_dict.get('type'):
                raise ValidationError(f'Can not get place by {name}')

            coordinates = json_dict.get('result').get('geometry').get('coordinates')

            poly = coordinates[0]
            polygons = []
            for item in poly:
                polygon = Polygon(item)
                polygons.append(polygon)
            multipolygon = MultiPolygon(polygons)

            different = compare_obj.geom.difference(multipolygon)
        else:
            return Response(['No data'])

        return Response(json.loads(different.geojson))
