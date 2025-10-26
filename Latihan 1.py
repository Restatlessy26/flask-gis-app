# from flask import Flask,url_for,send_file,request
# from shapely.geometry import Point,Polygon
# from folium.plugins import Draw
# import folium
# import io
# import json
# import zipfile
# import geopandas as gpd

# app = Flask(__name__)
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15)

#     x_polygon = 128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     zip_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(zip_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir],crs='EPSG:4326')

#     x_radius = 128.180946
#     y_radius = -3.698711
#     titik_radius = Point(x_radius,y_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[titik_radius],crs='EPSG:4326')

#     try: 
#         img_url = url_for('static', filename = 'Gambar/201874045.jpg',_external = True)
#     except RuntimeError:
#         img_url = '/static/Gambar/201874045.jpg'
    
#     folium.TileLayer(
#         tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#         name= 'TopoMap',
#         overlay= False,
#         control= True
#     ).add_to(folium_peta)

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         overlay= False,
#         name= 'ESRI Satelite',
#         control= True
#     ).add_to(folium_peta)

#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "color:red; font-family: Arial">Kawasan Bebas Kejahatan</h3>
#                 <p> <cite> Pak Lurah </cite> : <q> Dilarang keras melakukan </q> </p>
#                     <ul>
#                         <li> <mark> Kekerasan fisik dan Seksual </mark></li>
#                         <li> <mark> Pengunaan dan Transaksi Narkoba </mark></li>
#                         <li><mark> Perundungan dan tindak kejahatan lainnya </mark></li>
#                     </ul>
#             <img src = "{img_url}", width = '250'
#         </body>
#         </html>
#     '''

#     html_radius = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "color:black; font-family:Times New Roman;">Kawasan Rawan Covid-19</h3>
#                 <p> <abbr title = "Restat Lessy">Res</abbr> : Kawasan ini memiliki atribute sebagai berikut </p>
#                 <ol type = 'I'>
#                     <a href = "https://restatlessy.com">
#                         <li> Bangunan = 312 </li>
#                     <a href = "https://restatlessy.com">
#                         <li> Masyarakat = 559 Jiwa </li>
#                     <a href = "https://restatlessy.com">
#                         <li> Kendaraan = 271 </li>
#                 </ol>
#             <p> Untuk informasi selengkapnya :<a href "https://www.restatlessy.com">Klik Disini</a></p>
#         </body>
#         </html>
#         '''
    
#     frame_polygon = folium.IFrame(html=html_polygon, width=300, height=250)
#     popup_polygon = folium.Popup(frame_polygon,max_width=2650)
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         popup=popup_polygon,
#         style_function=lambda x:{
#             'color' : 'red',
#             'fillColor' : 'blue',
#             'fillOpacity' : 0.2
#         }
#     ).add_to(folium_peta)

#     frame_radius = folium.IFrame(html=html_radius, width= 300, height=250)
#     popup_radius = folium.Popup(frame_radius, max_width=2650)
#     folium.GeoJson(
#         gdp_radius.to_json(),
#         popup=popup_radius,
#         marker= folium.Circle(
#             fill_color = 'red',
#             color = 'black',
#             fill_opacity = 0.5,
#             radius= 450
#         ) 
#     ).add_to(folium_peta)

#     Draw(
#         export=True,
#         draw_options={
#             'polyline' : {'repeatMode' : True},
#             'marker' : {'repeatMode' : True},
#             'circle' : {'repeatMode' : True},
#             'rectangle' : {'repeatMode' : True},
#             'polygon' :{
#                 'allowIntersection' : False,
#                 'drawError' : {'color' : 'red', 'message' : 'error123'},
#                 'shapeOptions' : {'color' : 'orange'}
#             }
#         },
#         edit_options= {'edit' : True, 'remove' : True}
#     ).add_to(folium_peta)

#     html_js = f'''
#         <form id = 'exportForm' action = "{url_for('export_to_shp')}" style = "position : absolute; top:10px; right:100px; z-index: 1000px;">
#             <input type = 'hidden' name = 'geojson_data; id='geojson_input'>
#             <button type = 'submit' style = "color:red; background-color: blue; padding:8px 15px; cursor:pointer; border:none; border-radius: 4px; font-weight:bold;">
#             </button>
#         </form>
#         <script>
#             const mapId = "{folium_peta.get_name()}";
#             const map = document.getElementById(mapId)._leaflet_map;
#             let drawnItems = null;
#             map.eachControl(function(control){{
#                 if(control.options.edit&&control.options.edit.featureGroup){{
#                     drawnItems = control.options.edit.featureGroup
#                 }}
#             }})
#             if(drawnItems){{
#                 document.getElementById('exportForm').onsubmit = function(){{
#                     const geojson = drawnItems.toGeoJSON();
#                     document.getElementById('geojson_input').value = JSON.stringify(geojson);
#                     return true;
#                 }}
#             }}
#         </script> 
#     '''
#     css_style = '''
#         <style>
#             .leaflet-right.leaflet-bottom(transform = translateY(-70px))
#         </style>
#     '''
#     folium_peta.get_root().html.get_child(folium.Element(css_style))

# @app.route('/export_to_shp', methods = ['POST'])
# def export_to_shp():
#     geojson_str = request.form.get(geojson_data)
#     if not geojson_str:
#         geojson_str = "{'type':'featureCollection', 'features' :[]}"
#     try:
#         geojson_data = json.loads(geojson_str)
#         if not geojson_data.get('features'):
#             return "tidak ada data yang ditampilkan", 200
    
#         gdp_data = gpd.GeoDataFrame.from_features(geojson_data['features'], crs= 'EPSG:4326')
#         zip_buffer = io.BytesIO()
#         gdp_data.to_file(geojson_data, driver='ESRI Shapefile',encoding= 'utf-8', compression = 'zip')

#         folium.LayerControl(position='bottomright').add_to(folium_peta)
#         return folium_peta._repr_html_()
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

#tanpa popup
# x marker = 128.222795, 128.156195,128.255609,128.150965,128.202479
# y marker =  -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 

#tanpa popup(single)
# x marker = 128.173894
#  Y marker = -3.704364

# 📥 EKSPOR KE SHP










# from flask import Flask, url_for, send_file, request
# from shapely.geometry import Polygon, Point, shape
# from folium.plugins import Draw
# import folium
# import geopandas as gpd
# import json
# import io
# import zipfile
# import os
# import tempfile
# import shutil
# from shapely.validation import make_valid
# import logging
# import re

# app = Flask(__name__)
# # MENAIKKAN BATAS UKURAN PAYLOAD POST (50 MB)
# app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# # Konfigurasi logging
# logging.basicConfig(level=logging.INFO)

# # Fungsi pembersihan nama kolom untuk Shapefile (max 10 karakter, alfanumerik)
# def clean_column_name(col_name):
#     """Batasi panjang kolom dan hapus karakter ilegal untuk Shapefile (DBF)."""
#     cleaned = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
#     # Batasi hingga 10 karakter
#     return cleaned[:10].upper() # Gunakan huruf besar untuk kompatibilitas SHP

# # ====================================================================
# # FUNGSI INDEX (MAP INITIALIZATION)
# # ====================================================================
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     # Pastikan zoom control aktif
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15, zoom_control=True) 
#     map_name = folium_peta.get_name()

#     # --- Data Statis (Marker, Polygon, TileLayer) ---
#     x_polygon = 128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     kordinat_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(kordinat_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')

#     x_marker = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_marker = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
#     kordinat_marker = list(zip(x_marker,y_marker))
#     for x_marker,y_marker in kordinat_marker:
#         folium.Marker(
#             location=[y_marker, x_marker],
#             tooltip= 'Marker',
#             icon= folium.Icon(color = 'green', icon= 'star')
#         ).add_to(folium_peta)

#     x_radius = 128.180946
#     y_radius = -3.698711
#     kordinat_radius = Point(x_radius,y_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[kordinat_radius],crs='EPSG:4326')

#     folium.TileLayer(
#         tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkante, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#         overlay= False,
#         name= 'TopoMap',
#         control= True
#     ).add_to(folium_peta)

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         overlay= False,
#         name= 'ESRI Satelite',
#         control= True
#     ).add_to(folium_peta)
    
#     try:
#         # Menggunakan file '217.jpg' yang diunggah
#         # Pastikan gambar ini ada di folder 'static/Gambar/217.jpg'
#         gambar = url_for('static', filename = 'Gambar/217.jpg',_external=True) 
#     except RuntimeError:
#         gambar = 'static/Gambar/217.jpg'


#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h2 style = "color:black;font-family:Arial;">Kawasan Bebas Kejahatan</h2>
#             ... (konten popup lainnya) ...
#             <img src = "{gambar}" width = '250'>
#         </body>
#         </html>
#         '''
    
#     html_radius = '''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "color:red;font-family:Arial;">Kawasan Rawan Covid-19</h3>
#             ... (konten popup lainnya) ...
#         </body>
#         </html>
#         '''
#     frame_polygon = folium.IFrame(html=html_polygon, width= 300, height=250)
#     popup_polygon = folium.Popup(frame_polygon, max_width=2650)
#     folium.GeoJson(gdp_polygon.to_json(), popup=popup_polygon, style_function=lambda x:{'fillColor' : 'Blue', 'color' : 'red', 'fillOpacity' : 0.3}).add_to(folium_peta)

#     frame_radius = folium.IFrame(html= html_radius, width= 300, height= 250)
#     popup_radius = folium.Popup(frame_radius, max_width=2650)
#     folium.GeoJson(gdp_radius.to_json(), popup=popup_radius, marker= folium.Circle(color = 'Black', fillColor = 'Blue', fillOpacity = 0.4, radius= 250)).add_to(folium_peta)

#     # FeatureGroup untuk menyimpan hasil gambar pengguna
#     drawn_items = folium.FeatureGroup(name="Drawn Items").add_to(folium_peta)
#     drawn_items_name = drawn_items.get_name()
    
#     # Draw Control di kanan atas
#     Draw(
#         export= False, 
#         feature_group=drawn_items, 
#         position='topright', 
#         draw_options={
#             'polyline' : {'repeatMode' :True},
#             'rectangle' : {'repeatMode' : True},
#             'circle' : {'repeatMode' : True},
#             'marker' : {'repeatMode' : True},
#             'polygon' : {'allowIntersection' : False, 'drawError' : {'color' : 'red', 'message' : 'Error123'}, 'shapeOptions' : {'color' : 'red'}, 'repeatMode' : True}
#         },
#         edit_options={'edit' : True, 'remove' : True}
#     ).add_to(folium_peta)
    
#     # --- Penambahan Library Turf.js (Perhitungan Geometri) ---
#     turf_js_cdn = '<script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>'
#     folium_peta.get_root().header.add_child(folium.Element(turf_js_cdn))
    
#     # 🔥 SOLUSI UTAMA: Pre-render URL Flask SEBELUM f-string
#     export_shp_url = url_for('export_to_shp')
#     export_geojson_url = url_for('export_to_geojson')


#     # 🌟 IMPLEMENTASI MENU ALA GOOGLE EARTH PRO (HTML/CSS/JS)
#     # Menggunakan variabel Python yang sudah di-render: {export_shp_url} dan {export_geojson_url}
#     html_js = f"""
#     <style>
#     /* Container untuk seluruh menu */
#     .menu-bar {{ 
#         position: absolute; 
#         top: 10px; 
#         left: 10px; 
#         z-index: 1000; 
#         font-family: Arial, sans-serif;
#         display: flex;
#         background-color: #f9f9f9;
#         border-radius: 4px;
#         box-shadow: 0 2px 5px rgba(0,0,0,0.2);
#         padding: 2px;
#     }}
#     .menu-item {{
#         position: relative;
#         padding: 5px 10px;
#         cursor: pointer;
#         font-size: 14px;
#         color: #333;
#         user-select: none;
#     }}
#     .menu-item:hover {{
#         background-color: #ddd;
#         border-radius: 2px;
#     }}

#     /* Konten Dropdown */
#     .dropdown-content {{
#         display: none;
#         position: absolute;
#         top: 100%;
#         left: 0;
#         background-color: #f9f9f9;
#         min-width: 150px;
#         box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
#         z-index: 2;
#         border-radius: 4px;
#         padding: 5px 0;
#     }}
#     .dropdown-content button, .dropdown-content .submenu-item {{
#         color: black;
#         padding: 8px 15px;
#         text-decoration: none;
#         display: block;
#         border: none;
#         background: none;
#         cursor: pointer;
#         width: 100%;
#         text-align: left;
#         font-size: 14px;
#     }}
#     .dropdown-content button:hover, .dropdown-content .submenu-item:hover {{
#         background-color: #007bff;
#         color: white;
#     }}
#     .show-dropdown {{
#         display: block;
#     }}

#     /* Submenu Container */
#     .submenu-item::after {{
#         content: '►';
#         float: right;
#         margin-left: 10px;
#         font-size: 10px;
#     }}
#     .submenu-content {{
#         display: none;
#         position: absolute;
#         top: 0;
#         left: 100%;
#         background-color: #f9f9f9;
#         min-width: 160px;
#         box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
#         z-index: 3;
#         border-radius: 4px;
#         padding: 5px 0;
#     }}
#     .submenu-item:hover .submenu-content {{
#         display: block;
#     }}
    
#     /* SOLUSI PENEMPATAN KONTROL ZOOM (TOP-RIGHT) */
#     .leaflet-top.leaflet-left {{
#         left: auto !important; 
#         right: 10px !important; 
#     }}
#     .leaflet-top.leaflet-right {{
#         top: 80px !important; 
#     }}
    
#     </style>

#     <div id='menuBar' class='menu-bar' style="display: none;">
        
#         <div class='menu-item' onclick="toggleMenu('file')">File</div>
#         <div id='fileDropdown' class='dropdown-content'>
            
#             <div class='submenu submenu-item' onmouseover="showSubmenu('exportSubmenu')" onmouseout="hideSubmenu('exportSubmenu')">
#                 Export 
#                 <div id='exportSubmenu' class='submenu-content'>
#                     <button onclick="performExport('shp')">Shapefile (.zip)</button>
#                     <button onclick="performExport('geojson')">GeoJSON (.geojson)</button>
#                 </div>
#             </div>
            
#             <button disabled style="color: #888;">Simpan Gambar...</button>
#         </div>

#         <div class='menu-item' onclick="toggleMenu('edit')">Sunting</div>
#         <div id='editDropdown' class='dropdown-content'>
#             <button disabled style="color: #888;">Undo</button>
#             <button disabled style="color: #888;">Redo</button>
#         </div>
        
#         <div class='menu-item' onclick="toggleMenu('view')">Lihat</div>
#         <div id='viewDropdown' class='dropdown-content'>
#                     <button disabled style="color: #888;">Toolbar</button>
#         </div>

#     </div>

#     <script>
#         // Menggunakan kurung kurawal ganda ({{}}) agar tidak bentrok dengan f-string Python
#         var menuItems = [
#             {{id: 'fileDropdown', parentId: 'file'}},
#             {{id: 'editDropdown', parentId: 'edit'}},
#             {{id: 'viewDropdown', parentId: 'view'}}
#         ];

#         function closeAllMenus(exceptId) {{
#             for (var i = 0; i < menuItems.length; i++) {{
#                 var item = menuItems[i];
#                 if (item.id !== exceptId) {{
#                     document.getElementById(item.id).classList.remove('show-dropdown');
#                 }}
#             }}
#         }}
        
#         function closeAllSubmenus() {{
#             var submenus = document.getElementsByClassName('submenu-content');
#             for (var i = 0; i < submenus.length; i++) {{
#                 submenus[i].style.display = 'none';
#             }}
#         }}

#         function toggleMenu(menuName) {{
#             var id = menuName + 'Dropdown';
#             var dropdown = document.getElementById(id);
            
#             if (dropdown.classList.contains('show-dropdown')) {{
#                 dropdown.classList.remove('show-dropdown');
#                 closeAllSubmenus();
#             }} else {{
#                 closeAllMenus(id);
#                 dropdown.classList.add('show-dropdown');
#             }}
#         }}
        
#         function showSubmenu(id) {{
#             document.getElementById(id).style.display = 'block';
#         }}
        
#         function hideSubmenu(id) {{
#               setTimeout(function() {{
#                   var submenu = document.getElementById(id);
#                   if (submenu && !submenu.matches(':hover') && !submenu.parentElement.matches(':hover')) {{
#                       submenu.style.display = 'none';
#                   }}
#               }}, 50);
#         }}

#         window.onclick = function(event) {{
#             var menuBar = document.getElementById('menuBar');
#             if (menuBar && !menuBar.contains(event.target)) {{
#                 closeAllMenus(null);
#                 closeAllSubmenus();
#             }}
#         }}
        
#         function getDrawnItems() {{
#             var drawnItemsName = "{drawn_items_name}"; // Placeholder Flask/Jinja2
#             var drawnItems = window[drawnItemsName];
            
#             if (!drawnItems) {{
#                 var mapName = "{map_name}"; // Placeholder Flask/Jinja2
#                 var mapElement = document.getElementById(mapName);
#                 if (mapElement && mapElement._leaflet_map) {{
#                     var leafletMap = mapElement._leaflet_map;
#                     leafletMap.eachControl(function(control) {{
#                         if(control.options && control.options.edit && control.options.edit.featureGroup){{
#                             drawnItems = control.options.edit.featureGroup;
#                         }}
#                     }});
#                 }}
#             }}
#             return drawnItems;
#         }}
        
#         function performExport(format) {{
#             var drawnItems = getDrawnItems();
#             closeAllMenus(null);

#             if (!drawnItems || drawnItems.getLayers().length === 0) {{
#                 alert("Harap gambar setidaknya satu fitur untuk diekspor.");
#                 return;
#             }}
            
#             try {{
#                 var geojson = drawnItems.toGeoJSON();
                
#                 var form = document.createElement('form');
#                 form.method = 'POST';
                
#                 if (format === 'shp') {{
#                     form.action = "{export_shp_url}"; // Menggunakan URL yang sudah di-render
#                 }} else if (format === 'geojson') {{
#                     form.action = "{export_geojson_url}"; // Menggunakan URL yang sudah di-render
#                 }} else {{
#                     alert("Format export tidak valid.");
#                     return;
#                 }}
                
#                 var input = document.createElement('input');
#                 input.type = 'hidden';
#                 input.name = 'geojson_data';
#                 input.value = JSON.stringify(geojson);
#                 form.appendChild(input);

#                 document.body.appendChild(form);
#                 form.submit();
#                 document.body.removeChild(form);
                
#             }} catch (error) {{
#                 console.error("Error creating GeoJSON:", error);
#                 alert("Error membuat data export: " + error.message);
#             }}
#         }}

#         window.onload = function() {{
#             var mapName = "{map_name}"; // Placeholder Flask/Jinja2
#             var mapElement = document.getElementById(mapName);
            
#             if (!mapElement || !mapElement._leaflet_map) {{
#                 console.error("Leaflet map element not found or initialized.");
#                 return;
#             }}

#             var map = mapElement._leaflet_map;
            
#             setTimeout(function() {{
#                 if (getDrawnItems()) {{
#                     document.getElementById('menuBar').style.display = 'flex';
#                 }} else {{
#                     console.error("Drawn Items FeatureGroup is NOT accessible. Export dinonaktifkan.");
#                 }}
#             }}, 500); 

#             // =========================================================
#             // LOGIKA PERHITUNGAN PANJANG DENGAN TURF.JS
#             // =========================================================
#             map.on(L.Draw.Event.CREATED, function (e) {{
#                 var layer = e.layer;
#                 var type = String(e.layerType || '').toLowerCase(); 
                
#                 if (!type) {{
#                     getDrawnItems().addLayer(layer);
#                     return;
#                 }}

#                 var popupContent = '<h4>Hasil Pengukuran</h4>';
                
#                 try {{
#                     var geojsonFeature = layer.toGeoJSON();

#                     if (type === 'polyline') {{
#                         // Pengecekan Turf.js
#                         if (typeof turf !== 'undefined' && turf.length) {{
#                              var lengthKm = turf.length(geojsonFeature, {{units: 'kilometers'}}); // Kurung kurawal ganda pada objek JS
#                              var lengthM = lengthKm * 1000;
                             
#                              popupContent += '<p>Tipe: Garis</p>';
#                              popupContent += '<p>Panjang: <b>' + formatNumber(lengthM) + '</b> meter</p>';
#                              popupContent += '<p>Panjang: <b>' + formatNumber(lengthKm) + '</b> km</p>';
#                         }} else {{
#                              popupContent += '<p>Tipe: Garis</p><p>Hasil pengukuran tidak tersedia. (Turf.js tidak dimuat)</p>';
#                         }}

#                     }} else if (type === 'circle') {{
#                         var radiusM = layer.getRadius();
#                         var radiusKm = radiusM / 1000;
                        
#                         popupContent += '<p>Tipe: Circle</p>';
#                         popupContent += '<p>Radius: <b>' + formatNumber(radiusM) + '</b> meter</p>';
#                         popupContent += '<p>Radius: <b>' + formatNumber(radiusKm) + '</b> km</p>';

#                     }} else if (type === 'marker') {{
#                         popupContent += '<p>Tipe: Titik</p><p>Koordinat: ' + layer.getLatLng().lat.toFixed(6) + ', ' + layer.getLatLng().lng.toFixed(6) + '</p>';
#                     }} else {{
#                         var displayType = type.charAt(0).toUpperCase() + type.slice(1);
#                         popupContent += '<p>Tipe: ' + displayType + '</p>';
#                     }}

#                     // Tambahkan popup ke layer
#                     layer.bindPopup(popupContent).openPopup();

#                 }} catch (e) {{
#                     console.error("Error calculating geometry or binding popup:", e);
#                     layer.bindPopup('Error saat menghitung geometri: ' + e.message).openPopup();
#                 }}
                
#                 // Tambahkan layer ke FeatureGroup yang dapat diekspor
#                 getDrawnItems().addLayer(layer);
#             }});
            
#             // Fungsi format angka JS (memformat ke format Indonesia: desimal koma, ribuan titik)
#             function formatNumber(num) {{
#                 if (typeof num !== 'number') return 'N/A';
#                 return num.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, ".");
#             }}

#         }};
#     </script>
#     """
    
#     try:
#         folium_peta.get_root().html.add_child(folium.Element(html_js))
#         folium.LayerControl(position='bottomright').add_to(folium_peta) 

#         return folium_peta.get_root().render()

#     except Exception as e:
#         logging.error(f"Error creating map:{str(e)}")
#         return f"Error creating map : {str(e)}"

# # --------------------------------------------------------------------------------------
# ## Endpoint Export GeoJSON
# # --------------------------------------------------------------------------------------
# @app.route('/export_to_geojson', methods = ['POST'])
# def export_to_geojson():
#     logging.info({"=== Mulai Proses Export GeoJSON ==="})
#     geojson_str = request.form.get('geojson_data')
    
#     if not geojson_str:
#         return "Tidak ada data GeoJSON yang diterima.", 400 
    
#     geojson_buffer = io.BytesIO(geojson_str.encode('utf-8'))
#     geojson_buffer.seek(0)
    
#     return send_file(
#         geojson_buffer,
#         download_name='peta_digambar.geojson',
#         mimetype='application/json',
#         as_attachment=True
#     )

# # --------------------------------------------------------------------------------------
# ## Endpoint Export SHP
# # --------------------------------------------------------------------------------------
# @app.route('/export_to_shp', methods = ['POST'])
# def export_to_shp():
#     logging.info({"=== Mulai Proses Export SHP ==="})
#     geojson_str = request.form.get('geojson_data')

#     if not geojson_str:
#         logging.error("tidak ada data GeoJSON yang diterima")
#         return "Tidak ada data GeoJSON yang diterima. Pastikan data tidak terlalu besar atau coba gambar ulang.", 400 
    
#     temp_dir = tempfile.mkdtemp()
    
#     try:
#         geojson_data = json.loads(geojson_str)
        
#         if not geojson_data.get('features'):
#             return " Tidak ada data fitur untuk diekspor.", 400

#         valid_features = []
#         for i, feature in enumerate(geojson_data['features']):
#             try:
#                 if not feature.get('geometry'):
#                     continue
                    
#                 original_props = feature.get('properties', {})
#                 geom_shape = shape(feature['geometry'])
                
#                 # Cek jika ini adalah Folium Circle 
#                 is_folium_circle = 'radius' in original_props and geom_shape.geom_type == 'Polygon'
                
#                 if is_folium_circle:
#                     # Circle dikonversi menjadi Point + Radius untuk Shapefile
#                     centroid = geom_shape.centroid
                    
#                     new_feature = {
#                         "type": "Feature",
#                         "geometry": centroid.__geo_interface__,
#                         "properties": original_props.copy() 
#                     }
                    
#                     new_feature['properties']['RADIUS'] = new_feature['properties'].pop('radius')
#                     new_feature['properties']['TIPE_GEOM'] = 'Point' 
#                     new_feature['properties']['TIPE_ASAL'] = 'Circle'
                    
#                     new_feature['properties'].pop('shape', None)
#                     new_feature['properties'].pop('_leaflet_id', None)

#                     valid_features.append(new_feature)

#                 else:
#                     # Fitur Normal (Point, Line, Polygon)
#                     geom = geom_shape
                    
#                     if not geom.is_valid:
#                         geom = make_valid(geom)
                    
#                     if geom.geom_type == 'GeometryCollection':
#                         continue

#                     if 'properties' not in feature or feature['properties'] is None:
#                         feature['properties'] = {}
                    
#                     feature['properties']['TIPE_GEOM'] = geom.geom_type 
#                     feature['properties']['TIPE_ASAL'] = feature['properties'].pop('shape', 'Draw') 
#                     feature['properties'].pop('_leaflet_id', None)

#                     feature['geometry'] = geom.__geo_interface__
#                     valid_features.append(feature)
                
#                 # Tambahkan properti wajib ID
#                 valid_features[-1]['properties']['ID_FITUR'] = i + 1 
                
#             except Exception as e:
#                 logging.error(f"Error processing feature {i}: {str(e)}")
#                 continue

#         if not valid_features:
#             return " Tidak ada geometri valid yang dapat diekspor.", 400
        
#         gdf_all = gpd.GeoDataFrame.from_features(valid_features, crs='EPSG:4326')
        
#         # Terapkan pembersihan nama kolom untuk semua kolom
#         cleaned_columns = {col: clean_column_name(col) for col in gdf_all.columns}
#         gdf_all.rename(columns=cleaned_columns, inplace=True)
        
#         # Pisahkan GeoDataFrame berdasarkan tipe geometri untuk ekspor SHP yang terpisah
#         gdf_points = gdf_all[gdf_all.geometry.type.isin(['Point'])]
#         gdf_lines = gdf_all[gdf_all.geometry.type.isin(['LineString', 'MultiLineString'])]
#         gdf_polygons = gdf_all[gdf_all.geometry.type.isin(['Polygon', 'MultiPolygon'])]

#         files_created = []
        
#         # Tulis ke Shapefile
#         if not gdf_points.empty:
#             points_path = os.path.join(temp_dir, 'titik_digambar.shp')
#             gdf_points.to_file(points_path, driver='ESRI Shapefile', encoding='utf-8')
#             files_created.append('titik_digambar')

#         if not gdf_lines.empty:
#             lines_path = os.path.join(temp_dir, 'garis_digambar.shp')
#             gdf_lines.to_file(lines_path, driver='ESRI Shapefile', encoding='utf-8')
#             files_created.append('garis_digambar')

#         if not gdf_polygons.empty:
#             polygons_path = os.path.join(temp_dir, 'poligon_digambar.shp')
#             gdf_polygons.to_file(polygons_path, driver='ESRI Shapefile', encoding='utf-8')
#             files_created.append('poligon_digambar')

#         if not files_created:
#             return " Tidak ada data yang dapat diekspor ke Shapefile.", 400

#         # Zip file
#         zip_buffer = io.BytesIO()
#         with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
#             for root, dirs, files in os.walk(temp_dir):
#                 for file in files:
#                     # Hanya sertakan file SHP, SHX, DBF, PRJ, CPG
#                     if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
#                         file_path = os.path.join(root, file)
#                         arcname = os.path.relpath(file_path, temp_dir)
#                         zf.write(file_path, arcname)

#         zip_buffer.seek(0)

#         # Kirim file ZIP
#         return send_file(
#             zip_buffer,
#             download_name='peta_digambar.zip',
#             mimetype='application/zip',
#             as_attachment=True
#         )

#     except json.JSONDecodeError as e:
#         return f" Error dalam format data GeoJSON: {str(e)}", 400
        
#     except Exception as e:
#         logging.error(f"Fatal error during SHP export: {str(e)}", exc_info=True)
#         return f" Terjadi kesalahan fatal saat memproses file: {str(e)}", 500
        
#     finally:
#         # Cleanup direktori temporer
#         if os.path.exists(temp_dir):
#             shutil.rmtree(temp_dir)

# if __name__ == '__main__':
#     logging.info("Aplikasi Flask dimulai...")
#     # Pastikan Anda menginstal: pip install flask folium shapely geopandas
#     # Untuk menjalankan di lokal: Buat folder 'static/Gambar' dan letakkan '217.jpg' di dalamnya.
#     app.run(debug=True, host='0.0.0.0', port=5000)




    
# from flask import Flask, url_for, send_file, request
# from shapely.geometry import Polygon, Point, shape
# from folium.plugins import Draw
# import folium
# import geopandas as gpd
# import json
# import io
# import zipfile
# import os
# import tempfile
# import shutil
# from shapely.validation import make_valid
# import logging
# import re

# app = Flask(__name__)
# # MENAIKKAN BATAS UKURAN PAYLOAD POST (50 MB)
# app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# # Konfigurasi logging
# logging.basicConfig(level=logging.INFO)

# # Fungsi pembersihan nama kolom untuk Shapefile (max 10 karakter, alfanumerik)
# def clean_column_name(col_name):
#     """Batasi panjang kolom dan hapus karakter ilegal untuk Shapefile (DBF)."""
#     cleaned = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
#     # Batasi hingga 10 karakter
#     return cleaned[:10].upper() # Gunakan huruf besar untuk kompatibilitas SHP

# # ====================================================================
# # FUNGSI INDEX (MAP INITIALIZATION)
# # ====================================================================
# @app.route('/')
# def index():
#     kordinat_awal = -3.675, 128.220
#     # Pastikan zoom control aktif
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15, zoom_control=True) 
#     map_name = folium_peta.get_name()

#     # --- Data Statis (Marker, Polygon, TileLayer) ---
#     x_polygon = 128.199513,128.187740,128.188359,128.200797
#     y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     kordinat_polygon = list(zip(x_polygon,y_polygon))
#     polygon_akhir = Polygon(kordinat_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')

#     x_marker = 128.222795, 128.156195,128.255609,128.150965,128.202479
#     y_marker = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
#     kordinat_marker = list(zip(x_marker,y_marker))
#     for x_marker,y_marker in kordinat_marker:
#         folium.Marker(
#             location=[y_marker, x_marker],
#             tooltip= 'Marker',
#             icon= folium.Icon(color = 'green', icon= 'star')
#         ).add_to(folium_peta)

#     x_radius = 128.180946
#     y_radius = -3.698711
#     kordinat_radius = Point(x_radius,y_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[kordinat_radius],crs='EPSG:4326')

#     folium.TileLayer(
#         tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkante, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#         overlay= False,
#         name= 'TopoMap',
#         control= True
#     ).add_to(folium_peta)

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         overlay= False,
#         name= 'ESRI Satelite',
#         control= True
#     ).add_to(folium_peta)
    
#     try:
#         # Menggunakan file '217.jpg' yang diunggah
#         # Pastikan gambar ini ada di folder 'static/Gambar/217.jpg'
#         gambar = url_for('static', filename = 'Gambar/217.jpg',_external=True) 
#     except RuntimeError:
#         gambar = 'static/Gambar/217.jpg'


#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h2 style = "color:black;font-family:Arial;">Kawasan Bebas Kejahatan</h2>
#             ... (konten popup lainnya) ...
#             <img src = "{gambar}" width = '250'>
#         </body>
#         </html>
#         '''
    
#     html_radius = '''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = "color:red;font-family:Arial;">Kawasan Rawan Covid-19</h3>
#             ... (konten popup lainnya) ...
#         </body>
#         </html>
#         '''
#     frame_polygon = folium.IFrame(html=html_polygon, width= 300, height=250)
#     popup_polygon = folium.Popup(frame_polygon, max_width=2650)
#     folium.GeoJson(gdp_polygon.to_json(), popup=popup_polygon, style_function=lambda x:{'fillColor' : 'Blue', 'color' : 'red', 'fillOpacity' : 0.3}).add_to(folium_peta)

#     frame_radius = folium.IFrame(html= html_radius, width= 300, height= 250)
#     popup_radius = folium.Popup(frame_radius, max_width=2650)
#     folium.GeoJson(gdp_radius.to_json(), popup=popup_radius, marker= folium.Circle(color = 'Black', fillColor = 'Blue', fillOpacity = 0.4, radius= 250)).add_to(folium_peta)

#     # FeatureGroup untuk menyimpan hasil gambar pengguna
#     drawn_items = folium.FeatureGroup(name="Drawn Items").add_to(folium_peta)
#     drawn_items_name = drawn_items.get_name()
    
#     # Draw Control di kanan atas
#     Draw(
#         export= False, 
#         feature_group=drawn_items, 
#         position='topright', 
#         draw_options={
#             'polyline' : {'repeatMode' :True},
#             'rectangle' : {'repeatMode' : True},
#             'circle' : {'repeatMode' : True},
#             'marker' : {'repeatMode' : True},
#             'polygon' : {'allowIntersection' : False, 'drawError' : {'color' : 'red', 'message' : 'Error123'}, 'shapeOptions' : {'color' : 'red'}, 'repeatMode' : True}
#         },
#         edit_options={'edit' : True, 'remove' : True}
#     ).add_to(folium_peta)
    
#     # --- Penambahan Library Turf.js (Perhitungan Geometri) ---
#     turf_js_cdn = '<script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>'
#     folium_peta.get_root().header.add_child(folium.Element(turf_js_cdn))

#     # 🌟 IMPLEMENTASI MENU ALA GOOGLE EARTH PRO (HTML/CSS/JS)
#     # WAJIB menggunakan f"""...""" untuk f-string multi-baris yang besar
#     html_js = f"""
#     <style>
#         /* Container untuk seluruh menu */
#         .menu-bar {{ 
#             position: absolute; 
#             top: 10px; 
#             left: 10px; 
#             z-index: 1000; 
#             font-family: Arial, sans-serif;
#             display: flex;
#             background-color: #f9f9f9;
#             border-radius: 4px;
#             box-shadow: 0 2px 5px rgba(0,0,0,0.2);
#             padding: 2px;
#         }}
#         .menu-item {{
#             position: relative;
#             padding: 5px 10px;
#             cursor: pointer;
#             font-size: 14px;
#             color: #333;
#             user-select: none;
#         }}
#         .menu-item:hover {{
#             background-color: #ddd;
#             border-radius: 2px;
#         }}

#         /* Konten Dropdown */
#         .dropdown-content {{
#             display: none;
#             position: absolute;
#             top: 100%;
#             left: 0;
#             background-color: #f9f9f9;
#             min-width: 150px;
#             box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
#             z-index: 2;
#             border-radius: 4px;
#             padding: 5px 0;
#         }}
#         .dropdown-content button, .dropdown-content .submenu-item {{
#             color: black;
#             padding: 8px 15px;
#             text-decoration: none;
#             display: block;
#             border: none;
#             background: none;
#             cursor: pointer;
#             width: 100%;
#             text-align: left;
#             font-size: 14px;
#         }}
#         .dropdown-content button:hover, .dropdown-content .submenu-item:hover {{
#             background-color: #007bff;
#             color: white;
#         }}
#         .show-dropdown {{
#             display: block;
#         }}

#         /* Submenu Container */
#         .submenu-item::after {{
#             content: '►';
#             float: right;
#             margin-left: 10px;
#             font-size: 10px;
#         }}
#         .submenu-content {{
#             display: none;
#             position: absolute;
#             top: 0;
#             left: 100%;
#             background-color: #f9f9f9;
#             min-width: 160px;
#             box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
#             z-index: 3;
#             border-radius: 4px;
#             padding: 5px 0;
#         }}
#         .submenu-item:hover .submenu-content {{
#             display: block;
#         }}
        
#         /* 🏆 SOLUSI FINAL UNTUK PENEMPATAN KONTROL ZOOM (TOP-RIGHT) */
#         /* Memindahkan Zoom Control dari kiri atas ke kanan atas */
#         .leaflet-top.leaflet-left {{
#             left: auto !important; 
#             right: 10px !important; 
#         }}
#         /* Mendorong Draw Control ke bawah agar berada di bawah Zoom Control */
#         .leaflet-top.leaflet-right {{
#             top: 80px !important; 
#         }}
        
#     </style>

#     <div id='menuBar' class='menu-bar' style="display: none;">
        
#         <div class='menu-item' onclick="toggleMenu('file')">File</div>
#         <div id='fileDropdown' class='dropdown-content'>
            
#             <div class='submenu submenu-item' onmouseover="showSubmenu('exportSubmenu')" onmouseout="hideSubmenu('exportSubmenu')">
#                 Export 
#                 <div id='exportSubmenu' class='submenu-content'>
#                     <button onclick="performExport('shp')">Shapefile (.zip)</button>
#                     <button onclick="performExport('geojson')">GeoJSON (.geojson)</button>
#                 </div>
#             </div>
            
#             <button disabled style="color: #888;">Simpan Gambar...</button>
#         </div>

#         <div class='menu-item' onclick="toggleMenu('edit')">Sunting</div>
#         <div id='editDropdown' class='dropdown-content'>
#             <button disabled style="color: #888;">Undo</button>
#             <button disabled style="color: #888;">Redo</button>
#         </div>
        
#         <div class='menu-item' onclick="toggleMenu('view')">Lihat</div>
#         <div id='viewDropdown' class='dropdown-content'>
#                <button disabled style="color: #888;">Toolbar</button>
#         </div>

#     </div>

#     <script>
#         const menuItems = [
#             {{id: 'fileDropdown', parentId: 'file'}},
#             {{id: 'editDropdown', parentId: 'edit'}},
#             {{id: 'viewDropdown', parentId: 'view'}}
#         ];

#         function closeAllMenus(exceptId) {{
#             // ⭐ PERBAIKAN: Menggunakan for loop untuk menghindari konflik f-string pada "=> {{"
#             for (let i = 0; i < menuItems.length; i++) {{
#                 const item = menuItems[i];
#                 if (item.id !== exceptId) {{
#                     document.getElementById(item.id).classList.remove('show-dropdown');
#                 }}
#             }}
#         }}
        
#         function closeAllSubmenus() {{
#             const submenus = document.getElementsByClassName('submenu-content');
#             for (let i = 0; i < submenus.length; i++) {{
#                 submenus[i].style.display = 'none';
#             }}
#         }}

#         function toggleMenu(menuName) {{
#             const id = menuName + 'Dropdown';
#             const dropdown = document.getElementById(id);
            
#             if (dropdown.classList.contains('show-dropdown')) {{
#                 dropdown.classList.remove('show-dropdown');
#                 closeAllSubmenus();
#             }} else {{
#                 closeAllMenus(id);
#                 dropdown.classList.add('show-dropdown');
#             }}
#         }}
        
#         function showSubmenu(id) {{
#             document.getElementById(id).style.display = 'block';
#         }}
        
#         function hideSubmenu(id) {{
#              setTimeout(() => {{ 
#                  const submenu = document.getElementById(id);
#                  if (!submenu.matches(':hover') && !submenu.parentElement.matches(':hover')) {{
#                      submenu.style.display = 'none';
#                  }}
#              }}, 50);
#         }}

#         window.onclick = function(event) {{
#             const menuBar = document.getElementById('menuBar');
#             if (!menuBar.contains(event.target)) {{
#                 closeAllMenus(null);
#                 closeAllSubmenus();
#             }}
#         }}
        
#         function getDrawnItems() {{
#             const drawnItemsName = "{drawn_items_name}";
#             let drawnItems = window[drawnItemsName];
            
#             if (!drawnItems) {{
#                 const mapName = "{map_name}";
#                 const mapElement = document.getElementById(mapName);
#                 if (mapElement && mapElement._leaflet_map) {{
#                     const leafletMap = mapElement._leaflet_map;
#                     leafletMap.eachControl(function(control) {{
#                         if(control.options && control.options.edit && control.options.edit.featureGroup){{
#                             drawnItems = control.options.edit.featureGroup;
#                         }}
#                     }});
#                 }}
#             }}
#             return drawnItems;
#         }}
        
#         function performExport(format) {{
#             const drawnItems = getDrawnItems();
#             closeAllMenus(null);

#             if (!drawnItems || drawnItems.getLayers().length === 0) {{
#                 alert("Harap gambar setidaknya satu fitur untuk diekspor.");
#                 return;
#             }}
            
#             try {{
#                 const geojson = drawnItems.toGeoJSON();
                
#                 const form = document.createElement('form');
#                 form.method = 'POST';
                
#                 if (format === 'shp') {{
#                     form.action = "{url_for('export_to_shp')}";
#                 }} else if (format === 'geojson') {{
#                     form.action = "{url_for('export_to_geojson')}";
#                 }} else {{
#                     alert("Format export tidak valid.");
#                     return;
#                 }}
                
#                 const input = document.createElement('input');
#                 input.type = 'hidden';
#                 input.name = 'geojson_data';
#                 input.value = JSON.stringify(geojson);
#                 form.appendChild(input);

#                 document.body.appendChild(form);
#                 form.submit();
#                 document.body.removeChild(form);
                
#             }} catch (error) {{
#                 console.error("Error creating GeoJSON:", error);
#                 alert("Error membuat data export: " + error.message);
#             }}
#         }}

#         window.onload = function() {{
#             const mapName = "{map_name}";
#             const map = document.getElementById(mapName)._leaflet_map;
            
#             setTimeout(function() {{ 
#                 if (getDrawnItems()) {{
#                     document.getElementById('menuBar').style.display = 'flex';
#                 }} else {{
#                     console.error("Drawn Items FeatureGroup is NOT accessible. Export dinonaktifkan.");
#                 }}
#             }}, 500); 

#             // =========================================================
#             // ⭐ LOGIKA PERHITUNGAN LUAS/PANJANG DENGAN TURF.JS
#             // =========================================================
#             map.on(L.Draw.Event.CREATED, function (e) {{
#                 const layer = e.layer;
#                 // ⭐ PERBAIKAN KRITIS: Pastikan layerType adalah string yang valid dan lowercase.
#                 const type = String(e.layerType || '').toLowerCase(); 
                
#                 if (!type) {{
#                     getDrawnItems().addLayer(layer);
#                     return;
#                 }}

#                 let popupContent = '<h4>Hasil Pengukuran</h4>';
                
#                 try {{
#                     const geojsonFeature = layer.toGeoJSON();

#                     if (type === 'polygon' || type === 'rectangle' || type === 'circle') {{
#                         // Perhitungan Luas (Area)
                        
#                         let featureToCalculate = geojsonFeature;
#                         if(type === 'circle') {{
#                              const center = [layer.getLatLng().lng, layer.getLatLng().lat];
#                              const radiusKm = layer.getRadius() / 1000;
#                              // Konversi circle ke poligon yang dapat dihitung areanya oleh Turf
#                              featureToCalculate = turf.circle(center, radiusKm, {{steps: 32, units: 'kilometers'}});
#                         }}

#                         if (typeof turf.area !== 'function') {{
#                             throw new Error("Turf.js belum dimuat atau error.");
#                         }}

#                         const areaSqM = turf.area(featureToCalculate); 
                        
#                         let areaKm = areaSqM / 1000000; 
#                         let areaHektar = areaSqM / 10000; 
                        
#                         // Capitalize hanya huruf pertama untuk display yang rapi
#                         const displayType = type.charAt(0).toUpperCase() + type.slice(1);

#                         popupContent += `
#                             <p>Tipe: <b>${{displayType}}</b></p>
#                             <p>Luas: <b>${{formatNumber(areaSqM)}}</b> m²</p>
#                             <p>Luas: <b>${{formatNumber(areaHektar)}}</b> Ha</p>
#                             <p>Luas: <b>${{formatNumber(areaKm)}}</b> km²</p>
#                         `;

#                     }} else if (type === 'polyline') {{
#                         // Perhitungan Panjang (Length)
#                         // Menggunakan turf.length untuk perhitungan yang akurat
#                         const lengthKm = turf.length(geojsonFeature, {{units: 'kilometers'}});
#                         const lengthM = lengthKm * 1000;

#                         popupContent += `
#                             <p>Tipe: Garis</p>
#                             <p>Panjang: <b>${{formatNumber(lengthM)}}</b> meter</p>
#                             <p>Panjang: <b>${{formatNumber(lengthKm)}}</b> km</p>
#                         `;
#                     }} else if (type === 'marker') {{
#                         popupContent += `<p>Tipe: Titik</p><p>Koordinat: ${{layer.getLatLng().lat.toFixed(6)}}, ${{layer.getLatLng().lng.toFixed(6)}}</p>`;
#                     }}

#                     // Tambahkan popup ke layer
#                     layer.bindPopup(popupContent).openPopup();

#                 }} catch (e) {{
#                     console.error("Error calculating geometry or binding popup:", e);
#                     layer.bindPopup('Error saat menghitung geometri: ' + e.message).openPopup();
#                 }}
                
#                 // Tambahkan layer ke FeatureGroup yang dapat diekspor
#                 getDrawnItems().addLayer(layer);
#             }});
            
#             // Fungsi format angka JS (memformat ke format Indonesia: desimal koma, ribuan titik)
#             function formatNumber(num) {{
#                 return num.toFixed(2).replace('.', ',').replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ".");
#             }}

#         }};
#     </script>
#     """ # Penutup f-string multi-baris
    
#     try:
#         folium_peta.get_root().html.add_child(folium.Element(html_js))
#         folium.LayerControl(position='bottomright').add_to(folium_peta) 

#         return folium_peta.get_root().render()

#     except Exception as e:
#         logging.error(f"Error creating map:{str(e)}")
#         return f"Error creating map : {str(e)}"

# # --------------------------------------------------------------------------------------
# ## Endpoint Export GeoJSON
# # --------------------------------------------------------------------------------------
# @app.route('/export_to_geojson', methods = ['POST'])
# def export_to_geojson():
#     logging.info({"=== Mulai Proses Export GeoJSON ==="})
#     geojson_str = request.form.get('geojson_data')
    
#     if not geojson_str:
#         return "Tidak ada data GeoJSON yang diterima.", 400 
    
#     geojson_buffer = io.BytesIO(geojson_str.encode('utf-8'))
#     geojson_buffer.seek(0)
    
#     return send_file(
#         geojson_buffer,
#         download_name='peta_digambar.geojson',
#         mimetype='application/json',
#         as_attachment=True
#     )

# # --------------------------------------------------------------------------------------
# ## Endpoint Export SHP
# # --------------------------------------------------------------------------------------
# @app.route('/export_to_shp', methods = ['POST'])
# def export_to_shp():
#     logging.info({"=== Mulai Proses Export SHP ==="})
#     geojson_str = request.form.get('geojson_data')

#     if not geojson_str:
#         logging.error("tidak ada data GeoJSON yang diterima")
#         return "Tidak ada data GeoJSON yang diterima. Pastikan data tidak terlalu besar atau coba gambar ulang.", 400 
    
#     temp_dir = tempfile.mkdtemp()
    
#     try:
#         geojson_data = json.loads(geojson_str)
        
#         if not geojson_data.get('features'):
#             return " Tidak ada data fitur untuk diekspor.", 400

#         valid_features = []
#         for i, feature in enumerate(geojson_data['features']):
#             try:
#                 if not feature.get('geometry'):
#                     continue
                    
#                 original_props = feature.get('properties', {})
#                 geom_shape = shape(feature['geometry'])
                
#                 # Cek jika ini adalah Folium Circle 
#                 is_folium_circle = 'radius' in original_props and geom_shape.geom_type == 'Polygon'
                
#                 if is_folium_circle:
#                     # Circle dikonversi menjadi Point + Radius untuk Shapefile
#                     centroid = geom_shape.centroid
                    
#                     new_feature = {
#                         "type": "Feature",
#                         "geometry": centroid.__geo_interface__,
#                         "properties": original_props.copy() 
#                     }
                    
#                     new_feature['properties']['RADIUS'] = new_feature['properties'].pop('radius')
#                     new_feature['properties']['TIPE_GEOM'] = 'Point' 
#                     new_feature['properties']['TIPE_ASAL'] = 'Circle'
                    
#                     new_feature['properties'].pop('shape', None)
#                     new_feature['properties'].pop('_leaflet_id', None)

#                     valid_features.append(new_feature)

#                 else:
#                     # Fitur Normal (Point, Line, Polygon)
#                     geom = geom_shape
                    
#                     if not geom.is_valid:
#                         geom = make_valid(geom)
                    
#                     if geom.geom_type == 'GeometryCollection':
#                         continue

#                     if 'properties' not in feature or feature['properties'] is None:
#                         feature['properties'] = {}
                    
#                     feature['properties']['TIPE_GEOM'] = geom.geom_type 
#                     feature['properties']['TIPE_ASAL'] = feature['properties'].pop('shape', 'Draw') 
#                     feature['properties'].pop('_leaflet_id', None)

#                     feature['geometry'] = geom.__geo_interface__
#                     valid_features.append(feature)
                
#                 # Tambahkan properti wajib ID
#                 valid_features[-1]['properties']['ID_FITUR'] = i + 1 
                
#             except Exception as e:
#                 logging.error(f"Error processing feature {i}: {str(e)}")
#                 continue

#         if not valid_features:
#             return " Tidak ada geometri valid yang dapat diekspor.", 400
        
#         gdf_all = gpd.GeoDataFrame.from_features(valid_features, crs='EPSG:4326')
        
#         # Terapkan pembersihan nama kolom untuk semua kolom
#         cleaned_columns = {col: clean_column_name(col) for col in gdf_all.columns}
#         gdf_all.rename(columns=cleaned_columns, inplace=True)
        
#         # Pisahkan GeoDataFrame berdasarkan tipe geometri untuk ekspor SHP yang terpisah
#         gdf_points = gdf_all[gdf_all.geometry.type.isin(['Point'])]
#         gdf_lines = gdf_all[gdf_all.geometry.type.isin(['LineString', 'MultiLineString'])]
#         gdf_polygons = gdf_all[gdf_all.geometry.type.isin(['Polygon', 'MultiPolygon'])]

#         files_created = []
        
#         # Tulis ke Shapefile
#         if not gdf_points.empty:
#             points_path = os.path.join(temp_dir, 'titik_digambar.shp')
#             gdf_points.to_file(points_path, driver='ESRI Shapefile', encoding='utf-8')
#             files_created.append('titik_digambar')

#         if not gdf_lines.empty:
#             lines_path = os.path.join(temp_dir, 'garis_digambar.shp')
#             gdf_lines.to_file(lines_path, driver='ESRI Shapefile', encoding='utf-8')
#             files_created.append('garis_digambar')

#         if not gdf_polygons.empty:
#             polygons_path = os.path.join(temp_dir, 'poligon_digambar.shp')
#             gdf_polygons.to_file(polygons_path, driver='ESRI Shapefile', encoding='utf-8')
#             files_created.append('poligon_digambar')

#         if not files_created:
#             return " Tidak ada data yang dapat diekspor ke Shapefile.", 400

#         # Zip file
#         zip_buffer = io.BytesIO()
#         with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
#             for root, dirs, files in os.walk(temp_dir):
#                 for file in files:
#                     # Hanya sertakan file SHP, SHX, DBF, PRJ, CPG
#                     if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
#                         file_path = os.path.join(root, file)
#                         arcname = os.path.relpath(file_path, temp_dir)
#                         zf.write(file_path, arcname)

#         zip_buffer.seek(0)

#         # Kirim file ZIP
#         return send_file(
#             zip_buffer,
#             download_name='peta_digambar.zip',
#             mimetype='application/zip',
#             as_attachment=True
#         )

#     except json.JSONDecodeError as e:
#         return f" Error dalam format data GeoJSON: {str(e)}", 400
        
#     except Exception as e:
#         logging.error(f"Fatal error during SHP export: {str(e)}", exc_info=True)
#         return f" Terjadi kesalahan fatal saat memproses file: {str(e)}", 500
        
#     finally:
#         # Cleanup direktori temporer
#         if os.path.exists(temp_dir):
#             shutil.rmtree(temp_dir)

# if __name__ == '__main__':
#     logging.info("Aplikasi Flask dimulai...")
#     # Pastikan Anda menginstal: pip install flask folium shapely geopandas
#     # Untuk menjalankan di lokal: Buat folder 'static/Gambar' dan letakkan '217.jpg' di dalamnya.
#     app.run(debug=True, host='0.0.0.0', port=5000)

# from flask import Flask, url_for, send_file, request
# from shapely.geometry import Polygon,Point
# from folium.plugins import Draw
# import folium
# import geopandas as gpd
# import json
# import io
# import zipfile

# app = Flask(__name__)
# @app.route('/')

# def index():
#     kordinat_awal = -3.675, 128.220
#     folium_peta = folium.Map(location=kordinat_awal,zoom_start=14)

#     folium.TileLayer(
#         tiles= 'OpenStreetMap',
#         name= 'Peta OSM',
#         overlay= False,
#         control= True
#     ).add_to(folium_peta)

#     folium.TileLayer(
#         tiles= 'https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr='Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         name= 'Esri World Imagery',
#         overlay= False,
#         control= True).add_to(folium_peta)
    
#     folium.TileLayer(
#     tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#     attr='Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
#     name='OpenTopoMap',
#     overlay=False,
#     control=True
# ).add_to(folium_peta)
    
#     polygon_group = folium.FeatureGroup(name='Standard').add_to(folium_peta)

#     longitude_polygon = 128.199513,128.187740,128.188359,128.200797
#     latitude_polygon = -3.677841,-3.678988,-3.690433,-3.687038
#     kordinat_polygon = list(zip(longitude_polygon,latitude_polygon))
#     polygon_akhir = Polygon(kordinat_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')

#     try : 
#         img_url = url_for('static', filename= '/Gambar/201874045.jpg',_external= True)
#     except RuntimeError:
#         img_url = 'static/Gambar/201874045.jpg'

#     longitude_radius = 128.180946
#     latitude_radius = -3.698711
#     titik_radius = Point(longitude_radius,latitude_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[titik_radius], crs='EPSG:4326')

#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style = 'color: black; font-family: Arial'>Kawasan Res</h3>
#                 <p> dilarang keras melakukan </p>
#                     <ul>
#                         <li> Mabuk mabukan </li>
#                         <li> Transaksi Narkoba </li>
#                         <li> Seks Bebas </li>
#                     </ul>
#             <img src = '{img_url}' width = '250'>
#         </body>
#         </html>
#         '''
    
#     html_radius = f'''
#         <!DOCTYPE>
#         <html>
#         <body>
#             <h4 style = 'color:blue; font-family: Times New Roman> Kawasan Covid-19'</h4>
#                 <p> Memiliki atribut kawasan sebagai berikut </p>
#                     <ol>
#                         <li> Bangunan : 221 </li>
#                         <li> Masyarakat : 312 Jiwa </li>
#                         <li> Kendaraan : 121 </li>
#                     </ol>
#         </body>
#         </html>
#         '''
    
#     frame_polygon = folium.IFrame(html=html_polygon, width= 300, height=250)
#     popup_polygon = folium.Popup(frame_polygon,max_width=2650)
#     folium.GeoJson(
#         gdp_polygon.to_json(),
#         popup= popup_polygon,
#         style_function=lambda x : {
#             'fillColor' : 'blue',
#             'color' : 'red',
#             'fillOpacity' : 0.6 
#         }
#     ).add_to(polygon_group)

#     frame_radius = folium.IFrame(html=html_radius,width=300,height=250)
#     popup_radius = folium.Popup(frame_radius, max_width= 2650)
#     folium.GeoJson(
#         gdp_radius.to_json(),
#         popup= popup_radius,
#         marker= folium.Circle(
#             radius = 500,
#             fill_color = 'green',
#             color = 'red',
#             fill_opacity = 0.6
#         )
#     ).add_to(polygon_group)

#     Draw(
#         export= True,
#         position= 'topleft',
#         draw_options={
#             'polyline' : True,
#             'circle' :True,
#             'rectangle' : True,
#             'polygon' : {
#                 'allowIntersection' : False,
#                 'errorDraw' : {'color' : 'red', 'message' : 'error123'},
#                 'shapeOptions' : {'color' : 'blue'},
#             }
#         },
#         edit_options= {'edit' : True, 'remove' : True}
#     ).add_to(folium_peta)

#     export_html_js = f"""
#         <form id="exportForm" action="{url_for('export_to_shp')}" method="POST" style="position: absolute; top: 10px; right: 100px; z-index: 1000;">   
#             <input type="hidden" name="geojson_data" id="geojson_input">
#             <button type="submit" style="padding: 8px 15px; background-color: #ff9900; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
#                 📥 EKSPOR KE SHP
#             </button>
#         </form>
#         <script>
#             // Variabel Leaflet.Draw di Folium disimpan di property 'draw' dari peta
#             const mapId = '{folium_peta.get_name()}';
#             const map = document.getElementById(mapId)._leaflet_map;
            
#             // Cari instance L.Control.Draw yang memiliki drawnItems
#             let drawnItems = null;
#             map.eachControl(function(control) {{
#                 if (control.options.edit && control.options.edit.featureGroup) {{
#                     drawnItems = control.options.edit.featureGroup;
#                 }}
#             }});
            
#             if (drawnItems) {{
#                 document.getElementById('exportForm').onsubmit = function() {{
#                     // Dapatkan semua fitur yang digambar/diedit
#                     const geojson = drawnItems.toGeoJSON();
                    
#                     // Masukkan GeoJSON ke input tersembunyi
#                     document.getElementById('geojson_input').value = JSON.stringify(geojson);
                    
#                     return true; // Lanjutkan proses pengiriman form
#                 }};
#             }}
#         </script>
#     """
#     folium_peta.get_root().html.add_child(folium.Element(export_html_js))

#     css_shift = """
#     <style>
#         /* Target wadah di kanan bawah */
#         .leaflet-right.leaflet-bottom {
#             /* Geser ke atas sejauh 20px. Ubah nilai -20px untuk jarak yang berbeda. */
#             transform: translateY(-70px); 
#         }
#     </style>
#     """
#     folium_peta.get_root().html.add_child(folium.Element(css_shift))

#     folium.LayerControl(position='bottomright').add_to(folium_peta)
#     return folium_peta.get_root().render()

# @app.route('/export_to_shp', methods= ['POST'])
# def export_to_shp():
#     geojson_str = request.form.get('geojson_data')
#     if not geojson_str:
#         geojson_str= '{"type": "FeatureCollection", "features": []}'
#     try:
#         geojson_data = json.loads(geojson_str)
#         if not geojson_data.get('features'):
#             return "tidak ada fitu yang digambar untuk diekspor.", 200
        
#         gpd_data = gpd.GeoDataFrame.from_features(geojson_data['features'], crs='EPSG:4326')
#         zip_buffer = io.BytesIO()
#         gpd_data.to_file(zip_buffer,driver='ESRI Shapefile',encoding='utf-8',compression = 'zip', index=False)
#         zip_buffer.seek(0)
#         return send_file(
#             zip_buffer,
#             download_name = 'data_peta_interaktif.zip',
#             mimetype = 'application/zip',
#             as_attachment = True
#         )
#     except Exception as e:        
#         return f"terjadi kesalah saat memproses geojson menjadi shp : {e}", 500
# if __name__ == '__main__':
#     app.run(debug=True)






from flask import Flask, url_for, send_file, request
from shapely.geometry import Polygon,Point,shape
from folium.plugins import Draw
import folium
import geopandas as gpd
import json
import io
import zipfile
import os
import tempfile
import shutil
from shapely.validation import make_valid
import logging

app = Flask(__name__)
# MENAIKKAN BATAS UKURAN PAYLOAD POST
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    # --- Kode fungsi index() tidak perlu diubah.
    # --- Tetap gunakan kode index() Anda yang sudah ada di pertanyaan.

    kordinat_awal = -3.675, 128.220
    folium_peta = folium.Map(location=kordinat_awal,zoom_start=15)

    map_name = folium_peta.get_name()

    # --- Data Statis (Marker, Polygon, TileLayer) ---
    x_polygon = 128.199513,128.187740,128.188359,128.200797
    y_polygon = -3.677841,-3.678988,-3.690433,-3.687038
    kordinat_polygon = list(zip(x_polygon,y_polygon))
    polygon_akhir = Polygon(kordinat_polygon)
    gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')

    x_marker = 128.222795, 128.156195,128.255609,128.150965,128.202479
    y_marker = -3.626639, -3.622669,-3.657574, -3.649438, -3.595145 
    kordinat_marker = list(zip(x_marker,y_marker))
    for x_marker,y_marker in kordinat_marker:
        folium.Marker(
            location=[y_marker, x_marker],
            tooltip= 'Marker',
            icon= folium.Icon(color = 'green', icon= 'star')
        ).add_to(folium_peta)

    x_single_marker = 128.173894
    y_single_marker = -3.704364
    folium.Marker(
        location=[y_single_marker,x_single_marker],
        tooltip= 'Single',
        icon = folium.Icon(color = 'red', icon ='info-sign'),
    ).add_to(folium_peta)

    x_radius = 128.180946
    y_radius = -3.698711
    kordinat_radius = Point(x_radius,y_radius)
    gdp_radius = gpd.GeoDataFrame(geometry=[kordinat_radius],crs='EPSG:4326')

    folium.TileLayer(
        tiles= 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr= 'Kartendaten: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkante, <a href="http://viewfinderpanoramas.org">SRTM</a> | Kartendarstellung: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
        overlay= False,
        name= 'TopoMap',
        control= True
    ).add_to(folium_peta)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr= 'Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
        overlay= False,
        name= 'ESRI Satelite',
        control= True
    ).add_to(folium_peta)
    
    try:
        gambar = url_for('static', filename = 'Gambar/201874045.jpg',_external=True)
    except RuntimeError:
        gambar = 'static/Gambar/201874045.jpg'


    html_polygon = f'''
        <!DOCTYPE html>
        <html>
        <body>
            <h2 style = "color:black;font-family:Arial;">Kawasan Bebas Kejahatan</h2>
                <p> <cite>PakLurah</cite> : <q> Dilarang Keras Melakukan </q></p>
                    <ul>
                        <li> <mark> Transaksi dan Penggunaan Narkoba</mark></li> 
                        <li> <mark> Kekerasan Fisik dan Pelecehan Seksual </mark></li> 
                        <li> <mark> Segala Jenis Kejahatan Lainnya </mark></li> 
                    </ul>
                <img src = "{gambar}" width = '250'>
        </body>
        </html>
        '''
    
    html_radius = '''
        <!DOCTYPE html>
        <html>
        <body>
            <h3 style = "color:red;font-family:Arial;">Kawasan Rawan Covid-19</h3>
                <p> <abbr title = "Restat Lessy">Res</abbr> Berpendapat Bahwa kawasan ini memiliki atribute lokasi sebagai berikut </p>
                    <ol type = 'I'>
                        
                        <li><a href = "https://www.restatlessy.com"> Bangunan </a> </li>
                        
                        <li> <a href = "https://www.restatlessy.com"> Masyarakat </a> </li>
                        
                        <li> <a href = "https://www.restatlessy.com">  Kendaraan </a> </li>
                    </ol>
        </body>
        </html>
        '''
    frame_polygon = folium.IFrame(html=html_polygon, width= 300, height=250)
    popup_polygon = folium.Popup(frame_polygon, max_width=2650)
    folium.GeoJson(
        gdp_polygon.to_json(),
        popup=popup_polygon,
        style_function=lambda x:{
            'fillColor' : 'Blue',
            'color' : 'red',
            'fillOpacity' : 0.3
        }
    ).add_to(folium_peta)

    frame_radius = folium.IFrame(html= html_radius, width= 300, height= 250)
    popup_radius = folium.Popup(frame_radius, max_width=2650)
    folium.GeoJson(
        gdp_radius.to_json(),
        popup=popup_radius,
        marker= folium.Circle(
            color = 'Black',
            fillColor = 'Blue',
            fillOpacity = 0.4,
            radius= 250
        )
    ).add_to(folium_peta)

    # FeatureGroup untuk menyimpan hasil gambar pengguna
    drawn_items = folium.FeatureGroup(name="Drawn Items").add_to(folium_peta)
    drawn_items_name = drawn_items.get_name()
    
    Draw(
        export= True,
        feature_group=drawn_items, 
        draw_options={
            'polyline' : {'repeatMode' :True},
            'rectangle' : {'repeatMode' : True},
            'circle' : {'repeatMode' : True},
            'marker' : {'repeatMode' : True},
            'polygon' : {
                'allowIntersection' : False,
                'drawError' : {'color' : 'red', 'message' : 'Error123'},
                'shapeOptions' : {'color' : 'red'},
                'repeatMode' : True
            }
        },
        edit_options={'edit' : True, 'remove' : True}
    ).add_to(folium_peta)
    
    # 🛠️ PERBAIKAN JAVASCRIPT: Logika pencarian FeatureGroup yang lebih handal
    html_js = f'''
    <form id = 'exportForm' action = "{url_for('export_to_shp')}" method = 'POST' style = "position : absolute; top:10px; right:100px; z-index:1000; display: none;">
        <input type = 'hidden' name = 'geojson_data' id = 'geojson_input'>
        <button type = 'submit' style = "color:red; background-color:blue; padding: 8px 15px; cursor:pointer; border:none; border-radius:4px; font-weight:bold;"> 📥 EKSPOR KE SHP
        </button>
    </form>
    <script>
        console.log("script export loaded");
        
        // Penundaan yang sedikit lebih lama (750ms) untuk memastikan semua aset Leaflet dimuat
        setTimeout(function() {{ 
            const mapName = "{map_name}";
            const drawnItemsName = "{drawn_items_name}";

            let drawnItems = null;
            const mapElement = document.getElementById(mapName);
            
            if (!mapElement) {{
                console.error("Map element (div) not found with ID: " + mapName);
                return;
            }}

            // 1. Coba ambil FeatureGroup dari objek global Folium/Python
            if (window[drawnItemsName] && window[drawnItemsName].getLayers) {{
                drawnItems = window[drawnItemsName];
                console.log("Draw FeatureGroup found via Folium's global name.");
            }} 
            // 2. Fallback: Coba ambil dari Leaflet Draw Control (Metode bawaan)
            else if (mapElement._leaflet_map) {{
                const leafletMap = mapElement._leaflet_map;
                leafletMap.eachControl(function(control) {{
                    if(control.options && control.options.edit && control.options.edit.featureGroup){{
                        drawnItems = control.options.edit.featureGroup;
                        console.log("Draw FeatureGroup found via Leaflet Draw Control.");
                    }}
                }});
            }}


            if (drawnItems) {{
                // 💚 SUKSES: Tampilkan tombol
                document.getElementById('exportForm').style.display = 'block';

                document.getElementById('exportForm').onsubmit = function(e){{
                    e.preventDefault(); 
                    
                    if(drawnItems.getLayers().length === 0){{
                        alert("Harap gambar setidaknya satu fitur (titik, garis, atau poligon) untuk diekspor.");
                        return false;
                    }}

                    try {{
                        const geojson = drawnItems.toGeoJSON();
                        
                        if (!geojson || geojson.features.length === 0) {{
                             alert("Gagal membuat GeoJSON yang valid atau GeoJSON kosong. Coba gambar ulang fitur.");
                             console.error("Generated GeoJSON is empty or invalid:", geojson);
                             return false;
                        }}

                        document.getElementById('geojson_input').value = JSON.stringify(geojson);
                        
                        console.log("Submitting GeoJSON data, features count:", geojson.features.length);
                        
                        this.submit(); 
                    }}
                    catch (error){{
                        console.error("Error creating GeoJSON:", error);
                        alert("Error membuat data export: " + error.message);
                    }}
                }};
            }} else {{
                // 🔴 GAGAL: Nonaktifkan dan beri tahu pengguna
                console.error("Drawn Items FeatureGroup is NOT accessible. Export will not work.");
                const exportButton = document.getElementById('exportForm').querySelector('button');
                exportButton.disabled = true;
                exportButton.textContent = "❌ EXPORT DINONAKTIFKAN";
                exportButton.style.backgroundColor = '#888';
                document.getElementById('exportForm').style.display = 'block'; // Tampilkan tombol disabled
                alert("Kesalahan: Drawn Items tidak dapat diakses. Fungsi Export dinonaktifkan.");
            }}
        }}, 750); // Tunda 750ms
    </script>
    '''
    
    try:
        folium_peta.get_root().html.add_child(folium.Element(html_js))
        css_style = '''
            <style>
                .leaflet-right.leaflet-bottom{transform : translateY(-70px)}
            </style>
        '''
        folium_peta.get_root().html.add_child(folium.Element(css_style))
        folium.LayerControl(position='bottomright').add_to(folium_peta)

        return folium_peta.get_root().render()

    except Exception as e:
        logging.error(f"Error creating map:{str(e)}")
        return f"Error creating map : {str(e)}"

# --------------------------------------------------------------------------------------
@app.route('/export_to_shp', methods = ['POST'])
def export_to_shp():
    logging.info({"=== Mulai Proses Export SHP ==="})
    geojson_str = request.form.get('geojson_data')

    if not geojson_str:
        logging.error("tidak ada data GeoJSON yang diterima")
        return "Tidak ada data GeoJSON yang diterima. Pastikan data tidak terlalu besar atau coba gambar ulang.", 400 
    
    logging.info(f"Data GeoJSON diterima, panjang: {len(geojson_str)} karakter")
    
    temp_dir = tempfile.mkdtemp()
    logging.info(f"Direktori temporer dibuat: {temp_dir}")
    
    try:
        # Parse GeoJSON
        geojson_data = json.loads(geojson_str)
        
        if not geojson_data.get('features'):
            shutil.rmtree(temp_dir)
            logging.error("Tidak ada features dalam GeoJSON")
            return " Tidak ada data fitur untuk diekspor.", 400

        valid_features = []
        for i, feature in enumerate(geojson_data['features']):
            try:
                if not feature.get('geometry'):
                    continue
                    
                geom = shape(feature['geometry'])
                
                # Perbaikan validitas geometri
                if not geom.is_valid:
                    geom = make_valid(geom)
                
                # Skip GeometryCollection karena Shapefile tidak mendukungnya
                if geom.geom_type == 'GeometryCollection':
                    continue

                # 🚀 PERBAIKAN FINAL: Memastikan objek 'properties' ada dan konsisten
                # Ini adalah kunci untuk mencegah GeoPandas/Fiona gagal membuat skema
                if 'properties' not in feature or feature['properties'] is None:
                    feature['properties'] = {}
                
                # Tambahkan properti wajib untuk Shapefile
                feature['properties']['id_fitur'] = i + 1  # Mulai dari 1
                feature['properties']['tipe_geom'] = geom.geom_type # Tipe geometri Shapely
                
                # Khusus untuk Circle yang dikonversi menjadi Polygon di GeoJSON, 
                # kita pertahankan informasi bahwa itu adalah Circle (Opsional)
                if feature.get('properties', {}).get('shape') == 'Circle':
                    feature['properties']['tipe_asal'] = 'Circle'
                else:
                    feature['properties']['tipe_asal'] = 'Draw'


                feature['geometry'] = geom.__geo_interface__
                valid_features.append(feature)
                
            except Exception as e:
                logging.error(f"Error processing feature {i}: {str(e)}")
                continue

        if not valid_features:
            shutil.rmtree(temp_dir)
            logging.error("Tidak ada features yang valid setelah processing")
            return " Tidak ada geometri valid yang dapat diekspor.", 400
        
        gdf_all = gpd.GeoDataFrame.from_features(valid_features, crs='EPSG:4326')
        
        # Pisahkan GeoDataFrame berdasarkan tipe geometri untuk Shapefile terpisah
        # GeoPandas akan mengelompokkan LineString dan MultiLineString, serta Polygon dan MultiPolygon, secara alami
        gdf_points = gdf_all[gdf_all.geometry.type.isin(['Point'])]
        gdf_lines = gdf_all[gdf_all.geometry.type.isin(['LineString', 'MultiLineString'])]
        gdf_polygons = gdf_all[gdf_all.geometry.type.isin(['Polygon', 'MultiPolygon'])]

        files_created = []
        
        # Tulis ke Shapefile
        if not gdf_points.empty:
            points_path = os.path.join(temp_dir, 'titik_digambar.shp')
            # GeoPandas secara implisit akan memilih skema yang sesuai dari kolom gdf_all
            gdf_points.to_file(points_path, driver='ESRI Shapefile', encoding='utf-8')
            files_created.append('titik_digambar')

        if not gdf_lines.empty:
            lines_path = os.path.join(temp_dir, 'garis_digambar.shp')
            gdf_lines.to_file(lines_path, driver='ESRI Shapefile', encoding='utf-8')
            files_created.append('garis_digambar')

        if not gdf_polygons.empty:
            polygons_path = os.path.join(temp_dir, 'poligon_digambar.shp')
            gdf_polygons.to_file(polygons_path, driver='ESRI Shapefile', encoding='utf-8')
            files_created.append('poligon_digambar')

        if not files_created:
            shutil.rmtree(temp_dir)
            return " Tidak ada data yang dapat diekspor ke Shapefile.", 400

        # Zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Pastikan semua file pendukung SHP ikut ter-zip
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
                         file_path = os.path.join(root, file)
                         arcname = os.path.relpath(file_path, temp_dir)
                         zf.write(file_path, arcname)

        zip_buffer.seek(0)

        # Cleanup
        shutil.rmtree(temp_dir)

        # Kirim file ZIP
        return send_file(
            zip_buffer,
            download_name='peta_digambar.zip',
            mimetype='application/zip',
            as_attachment=True
        )

    except json.JSONDecodeError as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return f" Error dalam format data GeoJSON: {str(e)}", 400
        
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        logging.error(f"Fatal error during SHP export: {str(e)}", exc_info=True)
        return f" Terjadi kesalahan fatal saat memproses file: {str(e)}", 500

if __name__ == '__main__':
    logging.info("Aplikasi Flask dimulai...")
    app.run(debug=True, host='0.0.0.0', port=5000)
