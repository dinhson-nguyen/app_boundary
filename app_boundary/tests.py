from django.contrib.gis.geos import MultiPolygon, Polygon, MultiLineString, GeometryCollection
import json
from .models import Country, Province, District, Commune, history_district, history_province, history_commune

country = Country(id=84, name=' Viet Nam')
country.save()
print('start')
with open('app_boundary/data_tinh1.geojson', encoding="utf8") as f:
    data1 = json.load(f)
    features = data1['features']
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

print('1')

with open('app_boundary/data_huyen1.geojson', encoding="utf8") as f:
    data2 = json.load(f)
features = data2['features']

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

print('2')

with open('app_boundary/data_xa1.geojson', encoding="utf8") as f:
    data3 = json.load(f)
features = data3['features']
for data in features:
    property_data = data['properties']
    mahuyen = int(property_data['MAHUYEN'])
    maxa = int(property_data['MAXA'])
    if maxa:
        print(maxa)
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
print('3')
