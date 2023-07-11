import datetime
import json
import shutil
import urllib.request
import urllib.parse
from urllib.parse import quote

from django.contrib.gis.gdal import DataSource
from django.http import HttpResponse
from geojson import Feature, FeatureCollection
from shapely import wkt
import geopandas as gpd
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.exceptions import ValidationError
import fiona
from shapely.geometry import mapping
from fiona import Env
import os
import pandas as pd
import geojson
from .models import Province, District, Commune, Country
from django.contrib.gis.geos import MultiPolygon, Polygon


def get_info_excel(query, field_query, file_name):
    for item in query:
        stt = 1
        board = []
        for user in query:
            if field_query == Province:

                row = {'STT': stt, 'ma tinh': user.id, 'ten tinh': user.name,
                       'ma quoc gia': item.id_parent, 'ban do': user.geom}
            elif field_query == District:
                row = {'STT': stt, 'ma huyen': user.id, 'ten huyen': user.name,
                       'ma tinh': item.id_parent, 'ban do': user.geom}
            elif field_query == Commune:
                row = {'STT': stt, 'ma xa': user.id, 'ten xa': user.name,
                       'ma huyen': item.id_parent, 'ban do': user.geom}
            else:
                return ValidationError({'field query': f'{field_query} is not accepted'})
            board.append(row)
            stt = stt + 1
        df = pd.DataFrame(board)

        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename={}'.format(quote(file_name + '.xlsx'))
        df.to_excel(response, index=False)
        return response


def get_history_excel(query, history_query_model, time_check, field_query, file_name):
    stt = 1
    board = []
    for user in query:
        try:
            target = datetime.datetime.strptime(time_check, '%d/%m/%Y')
        except:
            raise ValidationError({'time': "Wrong format. Expected '%d/%m/%Y'"})
        history = history_query_model.objects.filter(id=user.uuid).filter(time__gte=target)
        if history:
            get_obj = history[0]
            if get_obj:

                if not get_obj.geom:
                    get_obj.geom = None
                for item in history:
                    data = {'%s' % (item.time): item.info}
                    if field_query == Province:
                        row = {'STT': stt, 'ma tinh': user.id, 'ten tinh': user.name,
                               'ma quoc gia': user.id_parent, 'ban do hien tai': user.geom,
                               f'ban do vao {time_check}': get_obj.geom, 'lich su chinh sua': data}
                    elif field_query == District:
                        row = {'STT': stt, 'ma huyen': user.id, 'ten huyen': user.name,
                               'ma tinh': user.id_parent, 'ban do hien tai': user.geom,
                               f'ban do vao {time_check}': get_obj.geom, 'lich su chinh sua': data}
                    elif field_query == Commune:
                        row = {'STT': stt, 'ma xa': user.id, 'ten xa': user.name,
                               'ma huyen': user.id_parent, 'ban do hien tai': user.geom,
                               f'ban do vao {time_check}': get_obj.geom, 'lich su chinh sua': data}
                    else:
                        return ValidationError({'field query': f'{field_query} is not accepted'})
            else:
                row = None
                return ValidationError({'field query': f'{field_query} is not accepted'})

        else:
            data = '- no data -'
            if field_query == Province:
                row = {'STT': stt, 'ma tinh': user.id, 'ten tinh': user.name,
                       'ma quoc gia': user.id_parent, 'ban do hien tai': user.geom,
                       f'ban do vao {time_check}': data, 'lich su chinh sua': data}
            elif field_query == District:
                row = {'STT': stt, 'ma huyen': user.id, 'ten huyen': user.name,
                       'ma tinh': user.id_parent, 'ban do hien tai': user.geom,
                       f'ban do vao {time_check}': data, 'lich su chinh sua': data}
            elif field_query == Commune:
                row = {'STT': stt, 'ma xa': user.id, 'ten xa': user.name,
                       'ma huyen': user.id_parent, 'ban do hien tai': user.geom,
                       f'ban do vao {time_check}': data, 'lich su chinh sua': data}
            else:
                row = None
                return ValidationError({'field query': f'{field_query} is not accepted'})
        board.append(row)
        stt = stt + 1
    df = pd.DataFrame(board)
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename={}'.format(quote(file_name + '.xlsx'))
    df.to_excel(response, index=False)
    return response


def get_data_dict(queryset):
    features = []
    for item in queryset:
        try:
            k = geojson.loads(item.geom.geojson)
        except:
            continue
        obj = wkt.loads(item.geom.wkt)
        features.append(Feature(geometry=obj, properties={'id': item.id,
                                                          'name': item.name,
                                                          'id_parent': item.id_parent.id}))
    feature_collection = FeatureCollection(features)
    feature_collection.crs = {
        "type": "name",
        "properties": {
            "name": "epsg:4326"
        }
    }
    return feature_collection


def get_file_geojson(file_name, collection):
    geo = json.dumps(collection, ensure_ascii=False).encode('utf8')
    response = HttpResponse(geo, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename={}'.format(quote(file_name + '.geojson'))
    return response


def get_file_shp(colection, file_name):
    gdf = gpd.GeoDataFrame.from_features(colection['features'])
    temp_dir = f'{settings.MEDIA_ROOT}/shpfile/{file_name}'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    gdf.to_file(temp_dir, driver='ESRI Shapefile', encoding='utf-8')
    shutil.make_archive(temp_dir, 'zip', temp_dir)
    zip_file = os.path.join(f'{settings.MEDIA_ROOT}/shpfile', f'{file_name}.zip')

    with open(zip_file, 'rb') as f:
        response_data = f.read()
    response = HttpResponse(response_data, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename={}'.format(quote(file_name + '.zip'))
    shutil.rmtree(f'{settings.MEDIA_ROOT}/shpfile')
    return response


def get_histoy_data(queryset, history_query_model, time_check):
    history_layer = []
    for item in queryset:
        try:
            target = datetime.datetime.strptime(time_check, '%d/%m/%Y')
        except:
            raise ValidationError({'time': "Wrong format. Expected '%d/%m/%Y'"})
        history = history_query_model.objects.filter(id=item.uuid).filter(time__gte=target)

        if history:
            get_obj = history[0]
            if get_obj:

                try:
                    history_layer.append(Feature(geometry=wkt.loads(get_obj.geom.wkt),
                                                 properties={'ma tinh': item.id,
                                                             'thoi gian': str(get_obj.time),
                                                             'info': get_obj.info.get('info')}))
                except:
                    history_layer.append(Feature(geometry=None,
                                                 properties={'ma tinh': item.id,
                                                             'thoi gian': str(get_obj.time),
                                                             'info': get_obj.info.get('info')}
                                                 ))
    history_collection = FeatureCollection(history_layer)
    history_collection.crs = {
        "type": "name",
        "properties": {
            "name": "epsg:4326"
        }
    }
    return history_collection


def savehistory(model, uuid, jsondata, geom):
    my_model = model.objects.create(
        id=uuid,
        info=jsondata,
        geom=geom,
    )


def createjson(event, old, new):
    if old is not None and new is not None:
        jsondata = {
            'info': {
                'event': event,
                'old_data': {
                    'id': old.id,
                    'name': old.name,
                    'id_parent': old.id_parent.id,
                },
                'new_data': {
                    'id': new.id,
                    'name': new.name,
                    'id_parent': new.id_parent.id,
                }
            }
        }
    elif new is None and old is not None:
        jsondata = {
            'info': {
                'event': event,
                'old_data': {
                    'id': old.id,
                    'name': old.name,
                    'id_parent': old.id_parent.id,
                },
            }
        }
    elif new is not None and old is None:
        jsondata = {

            'info': {
                'event': event,
                'new_data': {
                    'id': new.id,
                    'name': new.name,
                    'id_parent': new.id_parent.id,
                }
            }
        }
    else:
        jsondata = {}

    return jsondata


def mapdata(request):
    try:
        myfile = request.FILES['geom']
    except:
        return False, None
    file_name = myfile.name
    path = default_storage.save(f'{file_name}', ContentFile(myfile.read()))
    tmp_file = os.path.join(settings.MEDIA_ROOT, path)
    extension = file_name.split('.')[-1]
    if 'shp' in extension:
        with Env(SHAPE_RESTORE_SHX='YES'):
            with fiona.open(tmp_file) as src:
                polygons = []
                try:
                    for record in src:
                        coordinates = record['geometry']['coordinates'][0]
                        polygon = Polygon(coordinates)
                        polygons.append(polygon)
                except:
                    pass
                multipolygon1 = MultiPolygon(polygons)
    elif 'geojson' in extension:
        with open(tmp_file) as f:
            data1 = json.load(f)
            features = data1.get('features')
            for data in features:
                geometry = data['geometry']['coordinates']
                polygons = []
                for po in geometry:
                    polygon = Polygon(po)
                    polygons.append(polygon)
                multipolygon1 = MultiPolygon(polygons)
    else:
        return ValidationError({"file not supported": f"{file_name}file does not supported "})
    os.remove(tmp_file)
    return True, multipolygon1


def load_file(request):
    try:
        myfile = request.FILES['geom']
    except:
        return False, None
    file_name = myfile.name
    path = default_storage.save(f'{file_name}', ContentFile(myfile.read()))
    tmp_file = os.path.join(settings.MEDIA_ROOT, path)
    extension = file_name.split('.')[-1]
    if 'shp' in extension:
        with Env(SHAPE_RESTORE_SHX='YES'):
            with fiona.open(tmp_file) as src:
                for record in src:
                    geometry = mapping(record['geometry'])
                    features = record['properties']

    elif 'geojson' in extension:
        with open(tmp_file) as f:
            data1 = json.load(f)
            features = data1.get('features')
            for data in features:
                geometry = data['geometry']['coordinates']
    else:
        return ValidationError({"file not supported": f"file does not supported "})
    return geometry


def get_diff(query_1, query_2):
    pass


def get_data_from_map4d(request, field):
    map4d_id = request.data.get('id_map4D', None)
    id = request.data.get('id', None)
    if map4d_id is None:
        return ValidationError({"map4d_id": 'this field required'})
    if id is None:
        return ValidationError({"id": 'this field required'})

    api_link = f'https://api-app.map4d.vn/map/place/detail/{map4d_id}'
    response = urllib.request.urlopen(api_link)
    data = response.read()
    json_str = data.decode('utf-8')
    json_dict = json.loads(json_str)
    if json_dict.get('code') == 'id_not_found':
        return ValidationError({f'{map4d_id}': 'map4d_id not valid'})
    geometry = json_dict.get('result').get('geometry')
    geom = get_data_from_json(geometry)
    name = json_dict.get('result').get("name")
    item = json_dict.get('result').get('addressComponents')
    parent_name = None

    if field == Province:
        for i in item:
            if i.get('types')[0] == 'admin_level_1':
                parent_name = i.get('name')
        parent = Country.objects.get(name=parent_name)
    elif field == District:
        for i in item:
            if i.get('types')[0] == 'admin_level_2':
                parent_name = i.get('name')
        parent = Province.objects.get(name=parent_name)

    else:
        for i in item:
            if i.get('types')[0] == 'admin_level_3':
                parent_name = i.get('name')
        parent = District.objects.get(name=parent_name)
    data = {'id': id, 'name': name, 'id_parent': parent.id, 'geom': geom}
    return data


def get_data_from_json(geometry):
    if geometry.get('type') == 'MultiPolygon':
        geom = geometry.get('coordinates')

    else:
        coordinates = geometry.get('coordinates')
        poly = coordinates[0]
        polygons = []
        for item in poly:
            polygon = Polygon(item)
            polygons.append(polygon)
        geom = MultiPolygon(polygons)
    return geom


def get_data_from_file(request, field):
    id = request.data.get('id', None)
    if id is None:
        return ValidationError({"id": 'this field required'})
    try:
        myfile = request.FILES['geom']
    except:
        return False, None
    file_name = myfile.name
    path = default_storage.save(f'{file_name}', ContentFile(myfile.read()))
    tmp_file = os.path.join(settings.MEDIA_ROOT, path)
    extension = file_name.split('.')[-1]

    if 'geojson' in extension:
        with open(tmp_file) as f:
            data1 = json.load(f)
            features = data1.get('features')
            for data in features:
                geometry = data['geometry']['coordinates']
                property_data = data['properties']
                name = property_data['name']
                id_parent = property_data['id_parent']
    else:
        return ValidationError({"file not supported": f"file does not supported "})
    geom = get_data_from_json(geometry)
    if field == Province:
        parent = Country.objects.get(id=id_parent)
    elif field == District:
        parent = Province.objects.get(id=id_parent)
    else:
        parent = District.objects.get(id=id_parent)
    return {'id': id, 'name': name, 'id_parent': parent.id, 'geom': geom}


def get_dimensions(lst):
    if isinstance(lst, list):
        return 1 + max(get_dimensions(item) for item in lst)
    else:
        return 0


def unique_geom(obj_1, obj_2):
    merged_poly1 = obj_1.geom[0]
    for poly in obj_1.geom[1:]:
        merged_poly1 = merged_poly1.union(poly)
    merged_poly2 = obj_2.geom[0]
    for poly in obj_2.geom[1:]:
        merged_poly2 = merged_poly2.union(poly)
    s = merged_poly1.union(merged_poly2)
    geom = s.unary_union
    json_type = geom.geojson
    json_dict = json.loads(json_type)
    if json_dict.get('type') == 'MultiPolygon':
        return geom
    else:
        return MultiPolygon(geom)


def get_file_name(obj):
    return str(obj.name)
