from flask import Flask,send_file,request,url_for,render_template_string
from shapely.geometry import Point,Polygon
from folium.plugins import Draw
from shapely.validation import make_valid
import folium
import io
import re
import os
import logging
import tempfile
import json
import shutil
import geopandas as gpd
import zipfile

app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=50*1024*1024
logging.basicConfig(level=logging.INFO)
def pembersihan_nama_kolom(kolom_nama):
    cleaned= re.sub(r'[^a-zA-Z0-9_]','',kolom_nama)
    return cleaned[:10].upper()
@app.route('/info')
def info():
    try:
        image_url = url_for('static', filename = 'Gambar/201874045.jpg', _external = True)
    except RuntimeError:
        image_url = '/static/Gambar/201874045.jpg'
    html_web= f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title> informasi detail </title>
        </head>
        <body>
            <h2 style = "color:red;font-family:Arial;">Kawasan Rawan Covid-19</h2>
            <p> Kawasan ini memiliki informasi sebagai berikut: </p>
            <ul>
                <li> Bangunan : 311 </li>
                <li> Masyarakat : 727 Jiwa </li>
                <li> Kendaraan : 188 </li>
            </ul>
            <img src = '{image_url}' width = '250'>
            <br>
            <a href="/">kembali ke peta</a>
        </body>
        </html>
    '''
    return render_template_string(html_web)

@app.route('/')
def index():
    kordinat_awal = -3.675, 128.220
    folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)

    point_single= [-3.704364, 128.173894]
    folium.Marker(
        location= point_single,
        tooltip= 'point single',
        icon= folium.Icon(icon='star', color='black')
    ).add_to(folium_peta)

    x_titik_group = 128.222795, 128.156195,128.255609,128.150965,128.202479
    y_titik_group = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
    kordinat_point = [Point(lon,lat) for lon,lat in zip(x_titik_group,y_titik_group)]
    gdp_group_point= gpd.GeoDataFrame({'ID':range(len(kordinat_point))}, crs='EPSG:4326', geometry=kordinat_point)
    folium.GeoJson(
        gdp_group_point.to_json(),
        tooltip= 'Group Point',
        marker=folium.Marker(icon=folium.Icon(icon='star', color='blue'))
    ).add_to(folium_peta)

    titik_single_radius = [-3.680890, 128.217204]
    folium.Circle(
        location=titik_single_radius,
        tooltip='Radius Single',
        color= 'black',
        fill_color = 'blue',
        fill_opacity= 0.4,
        radius= 550,
    ).add_to(folium_peta)

    x_radius_group = 128.095588, 128.233062,128.337584,128.260028
    y_radius_group = -3.666394, -3.569149, -3.598937, -3.689211
    coord_group_radius = [Point(lon,lat) for lon,lat in zip(x_radius_group,y_radius_group)]
    gdp_radius_group = gpd.GeoDataFrame({'ID':range(len(coord_group_radius))}, geometry=coord_group_radius,crs='EPSG:4326')
    folium.GeoJson(
        gdp_radius_group.to_json(),
        tooltip='Group Radius',
        marker=folium.Circle(
            color = 'blue',
            fill_color = 'red',
            fill_opacity = 0.5,
            radius= 300
        )
    ).add_to(folium_peta)

    x_polygon = 128.195721,128.205291,128.220405,128.203678
    y_polygon = -3.593362,-3.607210, -3.599055, -3.581638
    kordinat_polygon = list(zip(x_polygon,y_polygon))
    polygon_tampil = Polygon(kordinat_polygon)
    gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_tampil], crs='EPSG:4326')
    folium.GeoJson(
        gdp_polygon.to_json(),
        tooltip='Polygon Non-Popup',
        style_function= lambda x:{
            'color' : 'black',
            'fillColor' : 'purple',
            'fillOpacity' : 0.6
        }
    ).add_to(folium_peta)    

    x_polygon_popup= 128.199513,128.187740,128.188359,128.200797
    y_polygon_popup = -3.677841,-3.678988,-3.690433,-3.687038
    coord_polygon = list(zip(x_polygon_popup,y_polygon_popup))
    Polygon_popup = Polygon(coord_polygon)
    gdp_polygon_popup = gpd.GeoDataFrame(geometry=[Polygon_popup], crs='EPSG:4326')

    html_polygon = f'''
        <!DOCTYPE html>
        <html>
        <body>
            <p> Untuk informasi selengkapnya : <a href="/info" target='_blank'>Klik Disini</a></p>
        </body>
        </html> 
    '''      
    Polygon_layer = folium.GeoJson(
        gdp_polygon_popup.to_json(),
        tooltip='Group Radius',
        style_function= lambda x:{
            'color' : 'black',
            'fillColor' : 'red',
            'fillOpacity' : 0.4,
        }
    ).add_to(folium_peta)
    Polygon_layer.add_child(folium.Popup(html_polygon,max_width=300))
    
    drawn_items = folium.FeatureGroup('drawnItems')
    drawn_items_name= drawn_items.get_name()
    Draw(
        export= False,
        draw_options={
            'polyline' : {'repeatMode' : True},
            'marker' : {'repeatMode' : True},
            'circle' : {'repeatMode' : True},
            'rectangle' : {'repeatMode' : True},
            'polygon' : {'repeatMode' : True}
        }
    ).add_to(folium_peta)

    html_radius = f'''
        <!DOCTYPE html>
        <html>
        <body>
            <h2 style = "color:black; font-family:Arial;">Kawasan bebas narkoba</h2>
                <p> dilarang mengedarkan </p>
                    <ol type='I'>
                        <li> Ganja</li>
                        <li> Sinte </li>
                        <li> Dan segala jenis narkotika lainnya</li>
                    </ol>
        </body>
        </html>
    '''
    html_js = f"""
        .menu-bar{{
            position:absolute;
            display:flex;
            background-color:white;
            border-radius = 3px;
            font-family = Arial;
            top:0px;
            left:0px;
            right:0px;
            z-index:1000;
            padding:4px;
        }}
        .menu-item{{
            position:relative;
            color:white;
            user-select:none;
            cursor:pointer;
            font-size:12px;
        }}
        .menu-item:hover{{
            background-color:red;
            border-radius: 3px;
        }}
        .dropdown-content{{
            display:none;
            position:absolute;
            font-size:12px;
            background-color:white;
            border-radius:2px;
            min-width:150px;
            padding:3px;
            top:100%;
            left:0;
            z-index:2;
        }}
        .dropdown-content button, .dropdown-content .submenu-item{{
            display:block;
            background:none;
            border:none;
            color:black;
            font-size:12px;
            width:100%;
            text-decoration:none;
            text-align:left;
            padding:3px;
            cursor:pointer;
        }}
        .dropdown-content button:hover, .dropdown-content .submenu-item:hover{{
            background-color:red;
            color:black;
        }}
        .show-dropdown{{
            display:block;
        }}
        .submenu-item:after{{
            content: '►';
            float:right;
            margin-left:5px;
            font-size:12px;
        }}
        .dropdown-content{{
            display:none;
            position:absolute;
            background-color:white;
            padding:4px;
            border-radius:3px;
            min-width:150px;
            top:0;
            left:100%;
            z-index:3;            
        }}
        .submenu-item:hover .submenu-content{{
            display:block;
        }}
        .leaflet-top.leaflet-left{{
            left:auto;
            right:5px !important;
            top: 30px !important;
        }}
        .leaflet-top.leaflet-right{{
            top: 120px !important;
            transform:translateX(5px);
        }}
        .leaflet-bottom.leaflet-right{{
            transform:translateX(5px;)
        }}
    </style>
    <div id = 'menuBar' class='menu-bar' style="display:block;">
        <div class = 'menu-item' onclick = "toggleMenu('file)">file</div>
        <div id = 'fileDropdown' class='dropdown-content'>
            <div class = 'submenu submenu-item' onmouseover="showSubmenu('exportSubmenu') onmouseput="hideSubmenu('exportSubmenu')">
                Export
                <div id = 'exportSubmenu' class='submenu-content'>
                    <button onclick="performExport('shp')">Shapefile(.zip)</button>
                    <button onclick="performExport('geojson')">GeoJSON(.geojson)</button>
                </div>
            </div>
            <button disabled style = "color:grey;">Simpan Gambar</button>
        </div>
        <div class='menu-item' onclick="toggleMenu('edit')">Sunting</div>
        <div id='editDropdown' class='dropdown-content'>
            <button disabled style= "color:grey;">Undo</button>
            <button disabled style = "color:grey;">Redo</button>
        </div>
        <div class='menu-item' onclick = "toggleMenu('view')">Lihat</div>
        <div id = 'viewDropdown' class='dropdown-content'>
            <button disabled style="color:grey;">toolbar</button>
        </div>
    </div>
    <script>
        const menuItems = [
            {{id = 'fileDropdown', parentId = 'file'}},
            {{id = 'editDropdown', parentId = 'edit'}},
            {{id = 'viewDropdown', parentId = 'view'}},
        ];
        function closeAllMenus(exceptId){{
            for(let i=0; i<menuItems.length; i++){{
                const item = menuItems[i];
                if(item.id !== exceptId){{
                    document.getElementById(item)
                }}
            }}
        }}

    """

    return folium_peta._repr_html_()
if __name__ == '__main__':
    app.run(debug= True)
    

#tiles google earth
# 'https://mt{0-3}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
# '►'
# tiles= 'https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
# attr='Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',

#     tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#     attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',

# tiles= 'OpenStreetMap',
# attr= '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

# turf_js = "https://unpkg.com/@turf/turf@6/turf.min.js"

#     koordinat_mulai =  -3.675, 128.220
#     longitude_polygon = 128.199513,128.187740,128.188359,128.200797
#     latitude_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     longitude_radius = 128.180946
#     latitude_radius = -3.698711

# x radius popup = 128.221471
# y radius popup =  -3.731109

# radius_non_popup = -3.680890, 128.217204

# Polygon Popup
# x polygon popup = 128.195721,128.205291,128.220405,128.203678
# y polygon popup =  -3.593362,-3.607210, -3.599055, -3.581638


# Point tanpa popup(Group)
# x marker = 128.222795, 128.156195,128.255609,128.150965,128.202479
# y marker =  -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 

# Point tanpa popup(single)
# x marker = -3.704364, 128.173894

#group radius 
#x group radius = 128.095588, 128.233062,128.337584,128.260028
#y group radius =  -3.666394, -3.569149, -3.598937, -3.689211



# from flask import Flask,send_file,url_for,request
# from shapely.validation import make_valid
# from shapely.geometry import Point, Polygon
# from folium.plugins import Draw
# import folium
# import io
# import shutil
# import re
# import logging
# import json
# import os
# import zipfile
# import tempfile 
# import geopandas as gpd

# app = Flask(__name__)
# app.config['MAX_CONTENT_LENGTH'] = 50*1024*1024
# logging.basicConfig(level=logging.INFO)
# def pembersihan_kolom_nama(kolom_nama):
#     cleaned = re.sub(r'[^a-zA-Z0-9_]', '', kolom_nama)
#     return cleaned[:10].upper()
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)

#     x_polygon = 128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     coord_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(coord_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')



#     x_radius = 128.180946
#     y_radius = -3.698711
#     titik_radius = Point(x_radius,y_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[titik_radius], crs='EPSG:4326')

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         name= 'Satelite ESRI',
#         overlay= False,
#         control= True
#     ).add_to(folium_peta)

#     folium.TileLayer(
#         tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#         overlay= False,
#         control= True
#     ).add_to(folium_peta)
#     try:
#         img_url = url_for('static', filename = 'Gambar/201874045.jpg',_external = True)
#     except RuntimeError:
#         img_url = '/static/Gambar/201874045.jpg'

#     #point Group
#     x_group = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_group = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
#     point_group = [Point(lon,lat) for lon,lat in zip(x_group, y_group)]
#     gdp_titik_group = gpd.GeoDataFrame(
#         {'ID' : range(len(point_group))},
#         geometry= point_group,
#         crs= 'EPSG:4326'
#     )    
#     folium.GeoJson(
#         gdp_titik_group.to_json(),
#         name= 'Point',        
#     ).add_to(folium_peta)
    

#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body<
#             <h2 style = "color: red; font-family: Times New Roman;">Kawasan Bebas Covid-19</h2>
#                 <p> <cite> Presiden</cite> : <q> Anda Memasuki Kawasan Bebas Corona, Aturan yang Wajib diikuti </q></p>
#                     <ul>
#                         <li> <mark> Cuci Tangan </mark> </li>
#                         <li> <mark> Dilarang Bersentuhan </mark> </li>
#                         <li> <mark> Pakai Masker </mark> </li>
#                     </ul>
#             <img src = "{img_url}", width = '250'>
#             </body>
#             </html>
#     '''
#     html_radius = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "color:blue; font-family: Arial;">Kawasan Rawan Covid-19</h2>
#                 <p> <abbr title = "restat lessy">Res</abbr> : Kawasan ini Memiliki atribute Lokasi sebagai berikut </p>
#                     <ol type = "I">
#                         <a href = 'https://www.restatlessy.com'>
#                             <li> Bangunan : 317 </li>
#                             <li> Masyarakat : 588 Jiwa </li>
#                             <li> Kendaraan : 177 </li>
#                     </ol>
#         </body>
#         </html>
#     '''
#     frame_polygon = folium.IFrame(html=html_polygon, width= 300, height= 250)
#     popup_polygon = folium.Popup(frame_polygon, max_width= 2650)
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         popup= popup_polygon,
#         style_function=lambda x:{
#             'color' : 'red',
#             'fillColor' : 'blue',
#             'fillOpacity' : 0.4
#         }
#     ).add_to(folium_peta)

#     frame_radius = folium.IFrame(html=html_radius,width=300,height=250)
#     popup_radius = folium.Popup(frame_radius, max_width=2650)
#     folium.GeoJson(
#         gdp_radius.to_json(),
#         popup=popup_radius,
#         marker= folium.Circle(
#             color = 'green',
#             fill_color = 'Blue',
#             fill_opacity = 0.5,
#             radius= 350
#         )
#     ).add_to(folium_peta)

#     Draw(
#         export= True,
#         draw_options={            
#             'polyline' : {'repeatMode' : True},
#             'circle' : {'repeatMode' : True},
#             'rectangle' : {'repeatMode' : True},
#             'marker' : {'repeatMode' : True},
#             'polygon' : {
#                 'allowIntersection' : False,
#                 'drawError' : {'color' : 'red', 'message' : 'error123'},
#                 'shapeOptions' : {'color' : 'blue'},
#                 'repeatMode' : True
#                 }
#         },
#         edit_options={'edit' : True, 'remove' : True}
#     ).add_to(folium_peta)

#     css_style = '''
#         <style>
#             .leaflet-right.leaflet-bottom{transform : translateY(-70px)}
#         </style>
#     '''
#     folium_peta.get_root().html.add_child(folium.Element(css_style))
#     folium.LayerControl(position='bottomright').add_to(folium_peta)    
#     return folium_peta._repr_html_()
# if __name__ == '__main__':
#     app.run(debug=True)








# tiles= 'https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#attr='Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',

    # tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    # attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',

# tiles= 'OpenStreetMap',
# attr= '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'


    # koordinat_mulai =  -3.675, 128.220
    # longitude_polygon = 128.199513,128.187740,128.188359,128.200797
    # latitude_polygon = -3.677841,-3.678988,-3.690433,-3.687038
    # longitude_radius = 128.180946
    # latitude_radius = -3.698711

#tanpa popup(Group)
# x marker = 128.222795, 128.156195,128.255609,128.150965,128.202479
# y marker =  -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 

#tanpa popup(single)
# x marker = 128.173894
#  Y marker = -3.704364

#polygon popup
# x polygon popup = 128.275347,128.276797,128.294114
# y polygon popup =  -3.610981,-3.622426,-3.615038


# from flask import Flask,url_for,send_file,request
# from shapely.geometry import Point,Polygon
# from shapely.validation import make_valid
# from folium.plugins import Draw
# import folium
# import re
# import os
# import logging
# import tempfile
# import shutil
# import zipfile
# import geopandas as gpd
# import json
# import io

# app=Flask(__name__)
# app.config['MAX_CONTENT_LENGTH']= 50*11024*1024
# logging.basicConfig(level=logging.INFO)
# def pembersihan_kolom_nama(kolom_nama):
#     cleaned = re.sub(r'[^a-zA-Z0-9_]', '', kolom_nama)
#     return cleaned[:10].upper()
# @app.route('/')
# def index():
#     titik_awal = -3.675, 128.220
#     folium_map = folium.Map(location=titik_awal, zoom_start= 15)

#     single_point = [-3.704364, 128.173894]
#     folium.Marker(
#         location=single_point,
#         tooltip= 'Single Point',
#         icon= folium.Icon(icon='star', color='red')
#     ).add_to(folium_map)

#     x_group_point = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_group_point = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
#     group_point = [Point(lon,lat) for lon,lat in zip(x_group_point,y_group_point)]
#     gdp_group_point = gpd.GeoDataFrame({'ID' : range(len(group_point))}, geometry= group_point, crs='EPSG:4326')
#     folium.GeoJson(
#         gdp_group_point.to_json(),
#         tooltip= 'Group Point'
#     ).add_to(folium_map)

#     single_radius = [-3.680890, 128.217204]
#     folium.Circle(
#         location=single_radius,
#         tooltip= 'Single Radius',
#         fill_color = 'red',
#         radius= 450,
#         color = 'blue',
#         fill_opacity = 0.4
#     ).add_to(folium_map)

#     x_group_radius = 128.095588, 128.233062,128.337584,128.260028
#     y_group_radius = -3.666394, -3.569149, -3.598937, -3.689211
#     group_radius = [Point(lon,lat) for lon,lat in zip(x_group_radius, y_group_radius)]
#     gdp_group_radius = gpd.GeoDataFrame({'ID':range(len(group_radius))}, geometry=group_radius, crs='EPSG:4326')
#     folium.GeoJson(
#         gdp_group_radius.to_json(),
#         tooltip='Group Radius',
#         marker= folium.Circle(
#             fill_color = 'red',
#             color = 'blue',
#             fill_opacity = 0.4,
#             radius= 450
#         )
#     ).add_to(folium_map)

#     x_polygon = 128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     coord_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(coord_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         tooltip='Polygon Single'
#     ).add_to(folium_map)

#     x_polygon_popup = 128.195721,128.205291,128.220405,128.203678
#     y_polygon_popup = -3.593362,-3.607210, -3.599055, -3.581638
#     coord_polygon_popup = list(zip(x_polygon_popup,y_polygon_popup))
#     polygon_popup_akhir = Polygon(coord_polygon_popup)
#     gdp_polygon_popup = gpd.GeoDataFrame(geometry=[polygon_popup_akhir], crs='EPSG:4326')

#     html_polygon = f'''
#         <DOCTYPE html>
#         <html>
#         <body>
#             <h2 style = "color:red; font-family:Arial;">Kawasan Bebas Kejahatan</h2>
#                 <p> <cite> Pak Lurah</cite> : <q> Dilarang keras melakukan tindakan</q></p>
#                     <ul> 
#                         <li> Melakukan Kekerasan Fisik dan Seksual</li>
#                         <li> Transaksi dan Penggunaan Narkoba</li>
#                         <li> Segala Bentuk Kejahatan Lainnya </li>
#                     <ul>
#                 <a href = "https://www.restatlessy.com">Informasi Selengkapanya Klik Disini</a>
#         </body>
#         </html>
#     '''
#     frame_polygon = folium.IFrame(html=html_polygon, width=300, height=250)
#     popup_polygon = folium.Popup(frame_polygon, max_width=2650)
#     folium.GeoJson(
#         gdp_polygon_popup.to_json(),
#         popup=popup_polygon,
#         tooltip='Polygon Popup',
#         style_function= lambda x:{
#             'fillColor' : 'Orange',
#             'fillOpacity' : 0.4,
#             'color' : 'red',
#         }
#     ).add_to(folium_map)

#     try:
#         image_url = url_for('static',filename='Gambar/201874045.jpg',_external= True)
#     except RuntimeError:
#         image_url = '/static/Gambar/201874045.jpg'

#     folium.TileLayer(
#         tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr='Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#         name= 'TopoMap',
#         overlay= False,
#         control= True
#     ).add_to(folium_map)

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         name= 'Satelite ESRI',
#         overlay= False,
#         control= True
#     ).add_to(folium_map)    

#     x_radius = 128.221471
#     y_radius =  -3.731109
#     titik_radius = Point(x_radius,y_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[titik_radius], crs= 'EPSG:4326')

#     html_radius = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "font-family:Arial; color: blue;">Kawasan Rawan Covid-19</h3>
#                 <p> <abbr title = "Restat Lessy">Res</abbr> : <mark> Kawasan ini Memiliki Atribute Lokasi Sebagai Berikut </mark></p>
#                     <ol type = 'I'>
#                         <a href = "https://www.restatlessy.com">
#                             <li> Bangunan:321 </li>
#                             <li> Masyarakat :662 Jiwa</li>
#                             <li> Kendaraan : 117 </li>
#                     </ol>
#             <img src = '{image_url}', width = '250'>
#         </body>
#         </html>
#     '''
#     frame_radius =  folium.IFrame(html=html_radius, width=300, height= 250)
#     popup_radius = folium.Popup(frame_radius, max_width= 2650)
#     folium.GeoJson(
#         gdp_radius.to_json(),
#         popup=popup_radius,
#         tooltip= 'Popup Radius',
#         marker= folium.Circle(
#             fill_color = 'blue',
#             color = 'red',
#             fill_opacity = 0.5,
#             radius= 500,
#         )
#     ).add_to(folium_map)
#     Draw(
#         export= False,        
#         draw_options={
#             'polyline' : {'repeatMode' : True},
#             'marker' : {'repeatMode' : True},
#             'circle' : {'repeatMode' : True},
#             'rectangle' : {'repeatMode' : True},
#             'polygon' : {
#                 'allowIntersection' : False,
#                 'drawError' : {'color' : 'red', 'message' : 'error123'},
#                 'shapeOptions' : {'color' : 'blue'},
#                 'repeatMode' : True},
#         },
#         edit_options={'edit' : True, 'remove' : True}
#     ).add_to(folium_map)
#     folium.LayerControl(position='bottomright').add_to(folium_map)
#     return folium_map._repr_html_()
# if __name__ =='__main__':
#     app.run(debug= True)

   







