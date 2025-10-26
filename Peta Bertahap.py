#Tahapan Peta Bertahap 
# 1. Menampilkan peta dengan sederhana bawaan folium
# 2. Menampilkan peta sederhana dengan tambahan sebuah Point yang memunculkan nama marker secara otomatis ketika dipiih
# 3. menambahkan group point, ubah bentuk sinngle point dengan Icon 
# 4. Men




#Menampilkan peta dengan sederhana bawaan folium

# from flask import Flask
# import folium

# app = Flask(__name__)
# @app.route('/')
# def ragil():
#     kordinat_awal = -3.675, 128.220
#     folium_restat = folium.Map(location=kordinat_awal, zoom_start=10)    
#     return folium_restat._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)

#Menampilkan peta sederhana dengan tambahan sebuah Point yang memunculkan nama marker secara otomatis ketika dipiih
# from flask import Flask
# import folium
# app = Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)
#     single_point =  -3.704364,128.173894
   
#     folium.Marker(
#         location= single_point,
#         tooltip= 'res' #menambah marker ketika di pilih        
#     ).add_to(folium_peta)
#     return folium_peta._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)


#menambahkan group point, ubah bentuk sinngle point dengan Icon 
# from flask import Flask
# from shapely.geometry import Point
# import folium
# import geopandas as gpd

# app = Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)

#     single_point =  -3.704364,128.173894
   
#     folium.Marker(
#         location= single_point,
#         tooltip= 'res', #menambah marker ketika di pilih   
#         icon= folium.Icon(icon= 'star', color= 'red')          
#     ).add_to(folium_peta)

#     #baris untuk menambah group point
#     x_group_point = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_group_point = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145
#     point_group = [Point(lon,lat) for lon,lat in zip(x_group_point,y_group_point)]

#     gdp_point_group = gpd.GeoDataFrame({'ID' : range(len(point_group))}, geometry= point_group, crs= 'EPSG:4326')
#     folium.GeoJson(
#         gdp_point_group.to_json(),
#         tooltip='titik group'
#     ).add_to(folium_peta)

#     return folium_peta._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)



#Menambahkan Single Radius
# from flask import Flask
# from shapely.geometry import Point
# import folium
# import geopandas as gpd

# app = Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)

#     single_point =  -3.704364,128.173894
   
#     folium.Marker(
#         location= single_point,
#         tooltip= 'res', #menambah marker ketika di pilih           
#         icon= folium.Icon(icon= 'star', color= 'red')          
#     ).add_to(folium_peta)

#     #baris untuk menambah group point
#     x_group_point = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_group_point = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145
#     point_group = [Point(lon,lat) for lon,lat in zip(x_group_point,y_group_point)]

#     gdp_point_group = gpd.GeoDataFrame({'ID' : range(len(point_group))}, geometry= point_group, crs= 'EPSG:4326')
#     folium.GeoJson(
#         gdp_point_group.to_json(),
#         tooltip='titik group'
#     ).add_to(folium_peta)

#     #Baris untuk menambahkan single radius tanpa popup   
#     titik_single_center = [-3.698711, 128.18094]

#     folium.Circle(
#         location=titik_single_center,
#         tooltip= 'radius_single',
#         fill_color = 'blue',
#         color = 'red',
#         fill_opacity = 0.4,
#         radius= 300,
#     ).add_to(folium_peta)

#     return folium_peta._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)


#menambahkan group radius 
# from flask import Flask
# from shapely.geometry import Point
# import folium
# import geopandas as gpd

# app = Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)

#     single_point =  -3.704364,128.173894
   
#     folium.Marker(
#         location= single_point,
#         tooltip= 'res', #menambah marker ketika di pilih           
#         icon= folium.Icon(icon= 'star', color= 'red')          
#     ).add_to(folium_peta)

#     #baris untuk menambah group point
#     x_group_point = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_group_point = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145
#     point_group = [Point(lon,lat) for lon,lat in zip(x_group_point,y_group_point)]

#     gdp_point_group = gpd.GeoDataFrame({'ID' : range(len(point_group))}, geometry= point_group, crs= 'EPSG:4326')
#     folium.GeoJson(
#         gdp_point_group.to_json(),
#         tooltip='titik group'
#     ).add_to(folium_peta)

#     #Baris untuk menambahkan single radius tanpa popup   
#     titik_single_center = [-3.698711, 128.18094]

#     folium.Circle(
#         location=titik_single_center,
#         tooltip= 'radius_single',
#         fill_color = 'blue',
#         color = 'red',
#         fill_opacity = 0.4,
#         radius= 300,
#     ).add_to(folium_peta)

#     #menambahkan group radius = 
#     x_group_radius = 128.095588, 128.233062,128.337584,128.260028
#     y_group_radius = -3.666394, -3.569149, -3.598937, -3.689211
#     titik_group_radius = [Point(lon,lat) for lon,lat in zip(x_group_radius,y_group_radius)]
#     gdp_group_radius = gpd.GeoDataFrame({'ID':range(len(titik_group_radius))}, geometry=titik_group_radius, crs= 'EPSG:4326')
#     folium.GeoJson(
#         gdp_group_radius.to_json(),
#         tooltip= 'group radius',
#         marker= folium.Circle(
#             fill_color = 'red',
#             color = 'black',
#             fill_opacity = 0.7,
#             radius= 400
#         )
#     ).add_to(folium_peta)
    

#     return folium_peta._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)

#menambahkan polygon tanpa popup
# from shapely.geometry import Polygon, Point
# from flask import Flask
# import folium
# import geopandas as gpd

# app=Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal,zoom_start=15)

#     titik_point_single = [-3.704364, 128.173894]
#     folium.Marker(
#         location=titik_point_single,
#         tooltip='titik single',
#         icon= folium.Icon(icon= 'star', color= 'red')
#     ).add_to(folium_peta)

#     x_point_group = 128.156195,128.255609,128.150965,128.202479
#     y_point_group = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
#     titik_point_group = [Point(lon,lat) for lon,lat in zip(x_point_group,y_point_group)]
#     gdp_point_group = gpd.GeoDataFrame({'ID':range(len(titik_point_group))}, geometry=titik_point_group, crs= 'EPSG:4326')
#     folium.GeoJson(
#         gdp_point_group.to_json(),
#         tooltip= 'Point Group'
#     ).add_to(folium_peta)

#     titik_single_radius = [-3.680890, 128.217204]
#     folium.Circle(
#         location=titik_single_radius,
#         tooltip='Radis Single',
#         radius= 350,
#         fill_color = 'red',
#         color = 'blue',
#         fill_opacity = 0.5
#     ).add_to(folium_peta)

#     x_group_radius = 128.095588, 128.233062,128.337584,128.260028
#     y_group_radius =  -3.666394, -3.569149, -3.598937, -3.689211
#     titik_group_radius = [Point(lon,lat) for lon,lat in zip(x_group_radius,y_group_radius)]
#     gdp_group_radius = gpd.GeoDataFrame({'ID':range(len(titik_group_radius))}, geometry=titik_group_radius, crs='EPSG:4326')
#     folium.GeoJson(
#         gdp_group_radius.to_json(),
#         tooltip='Group Radius',
#         marker= folium.Circle(
#             fill_color = 'blue',
#             color = 'green',
#             fill_opacity = 0.4,
#             radius= 300
            
#         )
#     ).add_to(folium_peta)

#     x_polygon = 128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     coord_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(coord_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         tooltip='Polygon Non Popup'
#     ).add_to(folium_peta)

#     return folium_peta._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)

#Menambah Polygon dengan Popup 
from flask import Flask,url_for
import geopandas as gpd
from shapely.geometry import Point,Polygon
import folium
import flask_sqlalchemy
import sys
import subprocess

app = Flask(__name__)
@app.route('/')
def index():
    kordinat awal = 

#Versi Lengkap Kurang Draw
# from shapely.geometry import Point,Polygon
# from flask import Flask,url_for
# import folium
# import geopandas as gpd

# app=Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_map = folium.Map(location=kordinat_awal)

#     titik_single_point= -3.704364, 128.173894
#     folium.Marker(
#         location=titik_single_point,
#         tooltip= 'Titik Single',
#         icon= folium.Icon(icon='star', color= 'blue')
#     ).add_to(folium_map)

#     x_point_group = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_point_group = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
#     titik_point_group = [Point(lon,lat) for lon,lat in zip(x_point_group,y_point_group)]
#     gdp_point_group = gpd.GeoDataFrame({'ID':range(len(titik_point_group))}, crs='EPSG:4326', geometry=titik_point_group)
#     folium.GeoJson(
#         gdp_point_group.to_json(),
#         tooltip='Group Point',
#         marker= folium.Marker(icon=folium.Icon(icon='star',color='red'))
#     ).add_to(folium_map)

#     kordinat__single_radius = [-3.680890, 128.217204]
#     folium.Circle(
#         location=kordinat__single_radius,
#         tooltip='single radius',
#         radius= 450,
#         color = 'blue',
#         fill_color = 'orange',
#         fill_opacity = 0.4
#     ).add_to(folium_map)

#     x_group_radius = 128.095588, 128.233062,128.337584,128.260028
#     y_group_radius = -3.666394, -3.569149, -3.598937, -3.689211
#     titik_group_radius = [Point(lon,lat) for lon,lat in zip(x_group_radius,y_group_radius)]
#     gdp_group_radius = gpd.GeoDataFrame({'ID':range(len(titik_group_radius))}, crs='EPSG:4326', geometry=titik_group_radius)
#     folium.GeoJson(
#         gdp_group_radius.to_json(),
#         tooltip='Group Radius',
#         marker= folium.Circle(
#             color = 'green',
#             fill_color = 'red',
#             fill_opacity = 0.4,
#             radius= 450,
#         )
#     ).add_to(folium_map)

#     x_polygon=128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     titik_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(titik_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         tooltip='Polygon Single',
#         style_function= lambda x:{
#             'color' : 'orange',
#             'fillColor' : 'Blue',
#             'fillOpacity' : '0.6' 
#         }
#     ).add_to(folium_map)

#     x_radius_popup = 128.221471
#     y_radius_popup = -3.731109
#     radius_popup = Point(x_radius_popup,y_radius_popup)
#     gdp_radius_popup = gpd.GeoDataFrame(geometry=[radius_popup], crs='EPSG:4326')
#     html_radius = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h2 style = "color:red; font-family:Arial;">Kawasan Rawan Covid-19</h2>
#                 <p> <cite> Kepala Desa</cite> : <q> Kawasan ini memiliki atribute lokasi sebagai berikut</q></p>
#                     <ol type = 'I'>
#                         <a href = "https://www.restatlessy.com">
#                             <li> Bangunan : 313 </li>
#                             <li> Masyarakat : 712 Jiwa </li>
#                             <li> Kendaraan : 221 </li>
#                     </ol>
#                 <a href  = "https://www.restatlessy.com">Klik Disini, untuk informasi selengkapnya</a>
#         </body>
#         </html>
#     '''
#     frame_radius = folium.IFrame(html=html_radius, width=300, height=250)
#     popup_radius = folium.Popup(frame_radius, max_width=2650)
#     folium.GeoJson(
#         gdp_radius_popup.to_json(),
#         popup=popup_radius,
#         tooltip= 'Polygon',
#         marker= folium.Circle(
#             color = 'black',
#             fill_color = 'red',
#             fill_opacity = 0.4,
#             radius= 500
#         )
#     ).add_to(folium_map)

#     try:
#         image_url = url_for('static', filename= 'Gambar/201874045.jpg',_external = True)
#     except RuntimeError:
#         image_url = '/static/Gambar/201874045.jpg'

#     x_polygon_popup = 128.275347,128.276797,128.294114
#     y_polygon_popup = -3.610981,-3.622426,-3.615038
#     coord_polygon_popup = list(zip(x_polygon_popup,y_polygon_popup))
#     polygon_popup = Polygon(coord_polygon_popup)
#     gdp_polygon_popup = gpd.GeoDataFrame(geometry=[polygon_popup], crs='EPSG:4326')
#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "color:blue; font-family:Arial;">Kawasan Bebas Kejahatan</h3>
#                 <p> <abbr title = "Restat Lessy">Res</abbr> : kawasan bebas kejahatan </p>
#                     <ul>
#                         <li> <mark>Dilarang Miras dan Narkoba</mark> </li>
#                         <li> <mark>Dilarang Pergaulan Bebas dan Kekerasan</mark> </li>
#                         <li> <mark>Dilarang Segala Bentuk tindak Kejahatan</mark> </li>
#                     </ul>
#             <img src = '{image_url}' width ='250'>
#         </body>
#         </html>
#     '''
#     frame_polygon = folium.IFrame(html=html_polygon, width=300, height=250)
#     popup_polygon = folium.Popup(frame_polygon, max_width=2650)
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         popup= popup_polygon,
#         tooltip='Polygon Popup',
#         style_function= lambda x:{
#             'color' : 'blue',
#             'fillColor' : 'green',
#             'fillOpacity' : 0.4
#         }
#     ).add_to(folium_map)
    
#     folium.TileLayer(
#         tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#         name= 'Topo Map',
#         control= True,
#         overlay= False,
#     ).add_to(folium_map)

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         overlay= False,
#         name='Satelite ESRI',
#         control= True
#     ).add_to(folium_map)

#     css_style = '''
#         <style>
#             .leaflet-bottom.leaflet-right{transform:translateY(-80px)}
#             .leaflet-top.leaflet-left{left:auto !important; right:5px !important}
#         </style>
#     '''
#     folium_map.get_root().html.add_child(folium.Element(css_style))
#     folium.LayerControl(position='bottomright').add_to(folium_map)
#     return folium_map._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)
