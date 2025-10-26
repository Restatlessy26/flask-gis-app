from flask import Flask, url_for, send_file, request
from shapely.geometry import Polygon, Point, shape
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
import re

app = Flask(__name__)
# MENAIKKAN BATAS UKURAN PAYLOAD POST (50 MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)

# Fungsi pembersihan nama kolom untuk Shapefile (max 10 karakter, alfanumerik)
def clean_column_name(col_name):
    """Batasi panjang kolom dan hapus karakter ilegal untuk Shapefile (DBF)."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
    # Batasi hingga 10 karakter
    return cleaned[:10].upper() # Gunakan huruf besar untuk kompatibilitas SHP

# ====================================================================
# FUNGSI INDEX (MAP INITIALIZATION)
# ====================================================================
@app.route('/')
def index():
    kordinat_awal = -3.675, 128.220
    # Pastikan zoom control aktif
    folium_peta = folium.Map(location=kordinat_awal, zoom_start=15, zoom_control=True) 
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
        # Menggunakan file '217.jpg' yang diunggah
        # Pastikan gambar ini ada di folder 'static/Gambar/217.jpg'
        gambar = url_for('static', filename = 'Gambar/217.jpg',_external=True) 
    except RuntimeError:
        gambar = 'static/Gambar/217.jpg'


    html_polygon = f'''
        <!DOCTYPE html>
        <html>
        <body>
            <h2 style = "color:black;font-family:Arial;">Kawasan Bebas Kejahatan</h2>
            ... (konten popup lainnya) ...
            <img src = "{gambar}" width = '250'>
        </body>
        </html>
        '''
    
    html_radius = '''
        <!DOCTYPE html>
        <html>
        <body>
            <h3 style = "color:red;font-family:Arial;">Kawasan Rawan Covid-19</h3>
            ... (konten popup lainnya) ...
        </body>
        </html>
        '''
    frame_polygon = folium.IFrame(html=html_polygon, width= 300, height=250)
    popup_polygon = folium.Popup(frame_polygon, max_width=2650)
    folium.GeoJson(gdp_polygon.to_json(), popup=popup_polygon, style_function=lambda x:{'fillColor' : 'Blue', 'color' : 'red', 'fillOpacity' : 0.3}).add_to(folium_peta)

    frame_radius = folium.IFrame(html= html_radius, width= 300, height= 250)
    popup_radius = folium.Popup(frame_radius, max_width=2650)
    folium.GeoJson(gdp_radius.to_json(), popup=popup_radius, marker= folium.Circle(color = 'Black', fillColor = 'Blue', fillOpacity = 0.4, radius= 250)).add_to(folium_peta)

    # FeatureGroup untuk menyimpan hasil gambar pengguna
    drawn_items = folium.FeatureGroup(name="Drawn Items").add_to(folium_peta)
    drawn_items_name = drawn_items.get_name()
    
    # Draw Control di kanan atas
    Draw(
        export= False, 
        feature_group=drawn_items, 
        position='topright', 
        draw_options={
            'polyline' : {'repeatMode' :True},
            'rectangle' : {'repeatMode' : True},
            'circle' : {'repeatMode' : True},
            'marker' : {'repeatMode' : True},
            'polygon' : {'allowIntersection' : False, 'drawError' : {'color' : 'red', 'message' : 'Error123'}, 'shapeOptions' : {'color' : 'red'}, 'repeatMode' : True}
        },
        edit_options={'edit' : True, 'remove' : True}
    ).add_to(folium_peta)
    
    # --- Penambahan Library Turf.js (Perhitungan Geometri) ---
    turf_js_cdn = '<script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>'
    folium_peta.get_root().header.add_child(folium.Element(turf_js_cdn))

    # 🌟 IMPLEMENTASI MENU ALA GOOGLE EARTH PRO (HTML/CSS/JS)
    html_js = f"""
    <style>
        /* Container untuk seluruh menu */
        .menu-bar {{ 
            position: absolute; 
            top: 0px; 
            left: 0px;
            right:0px; 
            z-index: 1000; 
            font-family: Arial, sans-serif;
            display: flex;
            background-color: #f9f9f9;
            border-radius: 4px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            padding: 2px;
        }}
        .menu-item {{
            position: relative;
            padding: 5px 10px;
            cursor: pointer;
            font-size: 14px;
            color: #333;
            user-select: none;
        }}
        .menu-item:hover {{
            background-color: #ddd;
            border-radius: 2px;
        }}

        /* Konten Dropdown */
        .dropdown-content {{
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            background-color: #f9f9f9;
            min-width: 150px;
            box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
            z-index: 2;
            border-radius: 4px;
            padding: 5px 0;
        }}
        .dropdown-content button, .dropdown-content .submenu-item {{
            color: black;
            padding: 8px 15px;
            text-decoration: none;
            display: block;
            border: none;
            background: none;
            cursor: pointer;
            width: 100%;
            text-align: left;
            font-size: 14px;
        }}
        .dropdown-content button:hover, .dropdown-content .submenu-item:hover {{
            background-color: #007bff;
            color: white;
        }}
        .show-dropdown {{
            display: block;
        }}

        /* Submenu Container */
        .submenu-item::after {{
            content: '►';
            float: right;
            margin-left: 10px;
            font-size: 10px;
        }}
        .submenu-content {{
            display: none;
            position: absolute;
            top: 0;
            left: 100%;
            background-color: #f9f9f9;
            min-width: 160px;
            box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
            z-index: 3;
            border-radius: 4px;
            padding: 5px 0;
        }}
        .submenu-item:hover .submenu-content {{
            display: block;
        }}
        
        /* 🏆 SOLUSI FINAL UNTUK PENEMPATAN KONTROL ZOOM (TOP-RIGHT) */
        /* Memindahkan Zoom Control dari kiri atas ke kanan atas */
        .leaflet-top.leaflet-left {{
            left: auto !important; 
            right: 5px !important; 
            top: 30px !important;
        }}
        /* Mendorong Draw Control ke bawah agar berada di bawah Zoom Control */
        .leaflet-top.leaflet-right {{
            top: 120px !important; 
            transform:translateX(5px);
        }}        
    </style>

    <div id='menuBar' class='menu-bar' style="display: none;">
        
        <div class='menu-item' onclick="toggleMenu('file')">File</div>
        <div id='fileDropdown' class='dropdown-content'>
            
            <div class='submenu submenu-item' onmouseover="showSubmenu('exportSubmenu')" onmouseout="hideSubmenu('exportSubmenu')">
                Export 
                <div id='exportSubmenu' class='submenu-content'>
                    <button onclick="performExport('shp')">Shapefile (.zip)</button>
                    <button onclick="performExport('geojson')">GeoJSON (.geojson)</button>
                </div>
            </div>
            
            <button disabled style="color: #888;">Simpan Gambar...</button>
        </div>

        <div class='menu-item' onclick="toggleMenu('edit')">Sunting</div>
        <div id='editDropdown' class='dropdown-content'>
            <button disabled style="color: #888;">Undo</button>
            <button disabled style="color: #888;">Redo</button>
        </div>
        
        <div class='menu-item' onclick="toggleMenu('view')">Lihat</div>
        <div id='viewDropdown' class='dropdown-content'>
               <button disabled style="color: #888;">Toolbar</button>
        </div>

    </div>

    <script>
        const menuItems = [
            {{id: 'fileDropdown', parentId: 'file'}},
            {{id: 'editDropdown', parentId: 'edit'}},
            {{id: 'viewDropdown', parentId: 'view'}}
        ];

        function closeAllMenus(exceptId) {{
            for (let i = 0; i < menuItems.length; i++) {{
                const item = menuItems[i];
                if (item.id !== exceptId) {{
                    document.getElementById(item.id).classList.remove('show-dropdown');
                }}
            }}
        }}
        
        function closeAllSubmenus() {{
            const submenus = document.getElementsByClassName('submenu-content');
            for (let i = 0; i < submenus.length; i++) {{
                submenus[i].style.display = 'none';
            }}
        }}

        function toggleMenu(menuName) {{
            const id = menuName + 'Dropdown';
            const dropdown = document.getElementById(id);
            
            if (dropdown.classList.contains('show-dropdown')) {{
                dropdown.classList.remove('show-dropdown');
                closeAllSubmenus();
            }} else {{
                closeAllMenus(id);
                dropdown.classList.add('show-dropdown');
            }}
        }}
        
        function showSubmenu(id) {{
            document.getElementById(id).style.display = 'block';
        }}
        
        function hideSubmenu(id) {{
             setTimeout(() => {{ 
                 const submenu = document.getElementById(id);
                 if (!submenu.matches(':hover') && !submenu.parentElement.matches(':hover')) {{
                     submenu.style.display = 'none';
                 }}
             }}, 50);
        }}

        window.onclick = function(event) {{
            const menuBar = document.getElementById('menuBar');
            if (!menuBar.contains(event.target)) {{
                closeAllMenus(null);
                closeAllSubmenus();
            }}
        }}
        
        function getDrawnItems() {{
            const drawnItemsName = "{drawn_items_name}";
            let drawnItems = window[drawnItemsName];
            
            if (!drawnItems) {{
                const mapName = "{map_name}";
                const mapElement = document.getElementById(mapName);
                if (mapElement && mapElement._leaflet_map) {{
                    const leafletMap = mapElement._leaflet_map;
                    leafletMap.eachControl(function(control) {{
                        if(control.options && control.options.edit && control.options.edit.featureGroup){{
                            drawnItems = control.options.edit.featureGroup;
                        }}
                    }});
                }}
            }}
            return drawnItems;
        }}
        
        function performExport(format) {{
            const drawnItems = getDrawnItems();
            closeAllMenus(null);

            if (!drawnItems || drawnItems.getLayers().length === 0) {{
                alert("Harap gambar setidaknya satu fitur untuk diekspor.");
                return;
            }}
            
            try {{
                const geojson = drawnItems.toGeoJSON();
                
                const form = document.createElement('form');
                form.method = 'POST';
                
                if (format === 'shp') {{
                    form.action = "{url_for('export_to_shp')}";
                }} else if (format === 'geojson') {{
                    form.action = "{url_for('export_to_geojson')}";
                }} else {{
                    alert("Format export tidak valid.");
                    return;
                }}
                
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'geojson_data';
                input.value = JSON.stringify(geojson);
                form.appendChild(input);

                document.body.appendChild(form);
                form.submit();
                document.body.removeChild(form);
                
            }} catch (error) {{
                console.error("Error creating GeoJSON:", error);
                alert("Error membuat data export: " + error.message);
            }}
        }}

        window.onload = function() {{
            const mapName = "{map_name}";
            const map = document.getElementById(mapName)._leaflet_map;
            
            setTimeout(function() {{ 
                if (getDrawnItems()) {{
                    document.getElementById('menuBar').style.display = 'flex';
                }} else {{
                    console.error("Drawn Items FeatureGroup is NOT accessible. Export dinonaktifkan.");
                }}
            }}, 500); 

            // =========================================================
            // LOGIKA PERHITUNGAN PANJANG DENGAN TURF.JS (HANYA UNTUK POLYLINE)
            // DAN RADIUS UNTUK CIRCLE
            // =========================================================
            map.on(L.Draw.Event.CREATED, function (e) {{
                const layer = e.layer;
                const type = String(e.layerType || '').toLowerCase(); 
                
                if (!type) {{
                    getDrawnItems().addLayer(layer);
                    return;
                }}

                let popupContent = '<h4>Hasil Pengukuran</h4>';
                
                try {{
                    const geojsonFeature = layer.toGeoJSON();

                    if (type === 'polyline') {{
                        // Perhitungan Panjang (Length)
                        // Menggunakan turf.length untuk perhitungan yang akurat
                        const lengthKm = turf.length(geojsonFeature, {{units: 'kilometers'}});
                        const lengthM = lengthKm * 1000;

                        popupContent += `
                            <p>Tipe: Garis</p>
                            <p>Panjang: <b>${{formatNumber(lengthM)}}</b> meter</p>
                            <p>Panjang: <b>${{formatNumber(lengthKm)}}</b> km</p>
                        `;
                    }} else if (type === 'circle') {{
                        // Hanya menampilkan radius untuk circle
                        const radiusM = layer.getRadius();
                        const radiusKm = radiusM / 1000;
                        
                        popupContent += `
                            <p>Tipe: Circle</p>
                            <p>Radius: <b>${{formatNumber(radiusM)}}</b> meter</p>
                            <p>Radius: <b>${{formatNumber(radiusKm)}}</b> km</p>
                        `;
                    }} else if (type === 'marker') {{
                        popupContent += `<p>Tipe: Titik</p><p>Koordinat: ${{layer.getLatLng().lat.toFixed(6)}}, ${{layer.getLatLng().lng.toFixed(6)}}</p>`;
                    }} else {{
                        // Untuk tipe lain (polygon, rectangle), hanya tampilkan tipe
                        const displayType = type.charAt(0).toUpperCase() + type.slice(1);
                        popupContent += `<p>Tipe: ${{displayType}}</p>`;
                    }}

                    // Tambahkan popup ke layer
                    layer.bindPopup(popupContent).openPopup();

                }} catch (e) {{
                    console.error("Error calculating geometry or binding popup:", e);
                    layer.bindPopup('Error saat menghitung geometri: ' + e.message).openPopup();
                }}
                
                // Tambahkan layer ke FeatureGroup yang dapat diekspor
                getDrawnItems().addLayer(layer);
            }});
            
            // Fungsi format angka JS (memformat ke format Indonesia: desimal koma, ribuan titik)
            function formatNumber(num) {{
                return num.toFixed(2).replace('.', ',').replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ".");
            }}

        }};
    </script>
    """
    
    try:
        folium_peta.get_root().html.add_child(folium.Element(html_js))
        folium.LayerControl(position='bottomright').add_to(folium_peta) 

        return folium_peta.get_root().render()

    except Exception as e:
        logging.error(f"Error creating map:{str(e)}")
        return f"Error creating map : {str(e)}"

# --------------------------------------------------------------------------------------
## Endpoint Export GeoJSON
# --------------------------------------------------------------------------------------
@app.route('/export_to_geojson', methods = ['POST'])
def export_to_geojson():
    logging.info({"=== Mulai Proses Export GeoJSON ==="})
    geojson_str = request.form.get('geojson_data')
    
    if not geojson_str:
        return "Tidak ada data GeoJSON yang diterima.", 400 
    
    geojson_buffer = io.BytesIO(geojson_str.encode('utf-8'))
    geojson_buffer.seek(0)
    
    return send_file(
        geojson_buffer,
        download_name='peta_digambar.geojson',
        mimetype='application/json',
        as_attachment=True
    )

# --------------------------------------------------------------------------------------
## Endpoint Export SHP (DIPERBAIKI)
# --------------------------------------------------------------------------------------
@app.route('/export_to_shp', methods = ['POST'])
def export_to_shp():
    logging.info("=== Mulai Proses Export SHP ===")
    geojson_str = request.form.get('geojson_data')

    if not geojson_str:
        logging.error("tidak ada data GeoJSON yang diterima")
        return "Tidak ada data GeoJSON yang diterima. Pastikan data tidak terlalu besar atau coba gambar ulang.", 400 
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        geojson_data = json.loads(geojson_str)
        
        if not geojson_data.get('features'):
            return " Tidak ada data fitur untuk diekspor.", 400

        valid_features = []
        for i, feature in enumerate(geojson_data['features']):
            try:
                if not feature.get('geometry'):
                    continue
                    
                original_props = feature.get('properties', {})
                geom_shape = shape(feature['geometry'])
                
                # Cek jika ini adalah Folium Circle 
                is_folium_circle = 'radius' in original_props and geom_shape.geom_type == 'Polygon'
                
                if is_folium_circle:
                    # Circle dikonversi menjadi Point + Radius untuk Shapefile
                    centroid = geom_shape.centroid
                    
                    new_feature = {
                        "type": "Feature",
                        "geometry": centroid.__geo_interface__,
                        "properties": original_props.copy() 
                    }
                    
                    new_feature['properties']['RADIUS'] = new_feature['properties'].pop('radius')
                    new_feature['properties']['TIPE_GEOM'] = 'Point' 
                    new_feature['properties']['TIPE_ASAL'] = 'Circle'
                    
                    new_feature['properties'].pop('shape', None)
                    new_feature['properties'].pop('_leaflet_id', None)

                    valid_features.append(new_feature)

                else:
                    # Fitur Normal (Point, Line, Polygon)
                    geom = geom_shape
                    
                    if not geom.is_valid:
                        geom = make_valid(geom)
                    
                    if geom.geom_type == 'GeometryCollection':
                        continue

                    if 'properties' not in feature or feature['properties'] is None:
                        feature['properties'] = {}
                    
                    feature['properties']['TIPE_GEOM'] = geom.geom_type 
                    feature['properties']['TIPE_ASAL'] = feature['properties'].pop('shape', 'Draw') 
                    feature['properties'].pop('_leaflet_id', None)

                    feature['geometry'] = geom.__geo_interface__
                    valid_features.append(feature)
                
                # Tambahkan properti wajib ID
                valid_features[-1]['properties']['ID_FITUR'] = i + 1 
                
            except Exception as e:
                logging.error(f"Error processing feature {i}: {str(e)}")
                continue

        if not valid_features:
            return " Tidak ada geometri valid yang dapat diekspor.", 400
        
        gdf_all = gpd.GeoDataFrame.from_features(valid_features, crs='EPSG:4326')
        
        # ⭐ PERBAIKAN: Jangan ubah nama kolom 'geometry' karena ini kolom khusus GeoPandas
        cleaned_columns = {}
        for col in gdf_all.columns:
            if col == 'geometry':
                cleaned_columns[col] = col  # Pertahankan nama 'geometry' untuk kolom geometry
            else:
                cleaned_columns[col] = clean_column_name(col)
        
        gdf_all.rename(columns=cleaned_columns, inplace=True)
        
        # ⭐ PERBAIKAN: Pastikan kolom geometry tetap sebagai kolom geometry aktif
        gdf_all = gdf_all.set_geometry('geometry')
        
        # Pisahkan GeoDataFrame berdasarkan tipe geometri untuk ekspor SHP yang terpisah
        gdf_points = gdf_all[gdf_all.geometry.type.isin(['Point'])]
        gdf_lines = gdf_all[gdf_all.geometry.type.isin(['LineString', 'MultiLineString'])]
        gdf_polygons = gdf_all[gdf_all.geometry.type.isin(['Polygon', 'MultiPolygon'])]

        files_created = []
        
        # Tulis ke Shapefile
        if not gdf_points.empty:
            points_path = os.path.join(temp_dir, 'titik_digambar.shp')
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
            return " Tidak ada data yang dapat diekspor ke Shapefile.", 400

        # Zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    # Hanya sertakan file SHP, SHX, DBF, PRJ, CPG
                    if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)

        zip_buffer.seek(0)

        # Kirim file ZIP
        return send_file(
            zip_buffer,
            download_name='peta_digambar.zip',
            mimetype='application/zip',
            as_attachment=True
        )

    except json.JSONDecodeError as e:
        return f" Error dalam format data GeoJSON: {str(e)}", 400
        
    except Exception as e:
        logging.error(f"Fatal error during SHP export: {str(e)}", exc_info=True)
        return f" Terjadi kesalahan fatal saat memproses file: {str(e)}", 500
        
    finally:
        # Cleanup direktori temporer
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    logging.info("Aplikasi Flask dimulai...")
    # Pastikan Anda menginstal: pip install flask folium shapely geopandas
    # Untuk menjalankan di lokal: Buat folder 'static/Gambar' dan letakkan '217.jpg' di dalamnya.
    app.run(debug=True, host='0.0.0.0', port=5000)





# from flask import Flask, url_for, send_file, request, jsonify
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
# from shapely.ops import transform
# import logging
# import re
# import pymysql
# from pymysql import MySQLError
# from pyproj import Transformer, CRS

# app = Flask(__name__)
# # MENAIKKAN BATAS UKURAN PAYLOAD POST (50 MB)
# app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# # Konfigurasi MySQL
# app.config['MYSQL_HOST'] = 'localhost'
# app.config['MYSQL_USER'] = 'root'
# app.config['MYSQL_PASSWORD'] = ''
# app.config['MYSQL_DB'] = 'gis_db'
# app.config['MYSQL_CHARSET'] = 'utf8mb4'
# app.config['MYSQL_PORT'] = 3306
# app.config['MYSQL_AUTOCOMMIT'] = True

# # Konfigurasi UTM Zone 52S (EPSG:32752) - UNTUK LOKASI ANDA
# app.config['UTM_ZONE'] = 'EPSG:32752'

# # Konfigurasi logging
# logging.basicConfig(level=logging.INFO)

# # Fungsi untuk koneksi database MySQL
# def get_mysql_connection():
#     """Membuat koneksi ke database MySQL dengan penanganan error"""
#     try:
#         connection = pymysql.connect(
#             host=app.config['MYSQL_HOST'],
#             user=app.config['MYSQL_USER'],
#             password=app.config['MYSQL_PASSWORD'],
#             database=app.config['MYSQL_DB'],
#             charset=app.config['MYSQL_CHARSET'],
#             port=app.config['MYSQL_PORT'],
#             autocommit=app.config['MYSQL_AUTOCOMMIT'],
#             cursorclass=pymysql.cursors.DictCursor
#         )
#         logging.info("Koneksi MySQL berhasil dibuat")
#         return connection
#     except MySQLError as e:
#         logging.error(f"MySQL Connection Error: {str(e)}")
#         return None
#     except Exception as e:
#         logging.error(f"Unexpected error in MySQL connection: {str(e)}")
#         return None

# # Fungsi untuk membuat database dan tabel jika belum ada
# def init_database():
#     """Membuat database dan tabel jika belum ada"""
#     try:
#         # Koneksi tanpa database terlebih dahulu
#         connection = pymysql.connect(
#             host=app.config['MYSQL_HOST'],
#             user=app.config['MYSQL_USER'],
#             password=app.config['MYSQL_PASSWORD'],
#             charset=app.config['MYSQL_CHARSET'],
#             port=app.config['MYSQL_PORT']
#         )
        
#         with connection.cursor() as cursor:
#             # Buat database jika belum ada
#             cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config['MYSQL_DB']}")
#             cursor.execute(f"USE {app.config['MYSQL_DB']}")
            
#             # Buat tabel jika belum ada
#             create_table_sql = """
#             CREATE TABLE IF NOT EXISTS polygon_areas (
#                 id INT AUTO_INCREMENT PRIMARY KEY,
#                 geometry_wkt TEXT NOT NULL,
#                 area_sq_m DECIMAL(15, 2) NOT NULL,
#                 area_sq_km DECIMAL(15, 6) NOT NULL,
#                 area_hectare DECIMAL(15, 4) NOT NULL,
#                 utm_zone VARCHAR(10) NOT NULL,
#                 method VARCHAR(50) NOT NULL,
#                 calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#             )
#             """
#             cursor.execute(create_table_sql)
#             logging.info("Database dan tabel berhasil diinisialisasi")
        
#         connection.commit()
#         connection.close()
#         return True
        
#     except Exception as e:
#         logging.error(f"Error inisialisasi database: {str(e)}")
#         return False

# # Fungsi untuk menghitung luas dengan UTM Zone 52S
# def calculate_area_utm(geometry):
#     """Menghitung luas polygon menggunakan UTM Zone 52S (EPSG:32752)"""
#     try:
#         # Buat transformer dari WGS84 (EPSG:4326) ke UTM Zone 52S (EPSG:32752)
#         transformer = Transformer.from_crs("EPSG:4326", app.config['UTM_ZONE'], always_xy=True)
        
#         # Transformasi geometry ke UTM
#         geometry_utm = transform(transformer.transform, geometry)
        
#         # Hitung luas dalam meter persegi
#         area_sq_m = geometry_utm.area
        
#         # Konversi ke unit lainnya
#         area_sq_km = area_sq_m / 1_000_000
#         area_hectare = area_sq_m / 10_000
        
#         return area_sq_m, area_sq_km, area_hectare
        
#     except Exception as e:
#         logging.error(f"Error dalam perhitungan UTM: {str(e)}")
#         raise e

# # Fungsi untuk menghitung luas dengan MySQL spatial functions
# def calculate_area_mysql(wkt_geometry):
#     """Menghitung luas menggunakan MySQL spatial functions"""
#     try:
#         connection = get_mysql_connection()
#         if not connection:
#             return None, None, None, "MySQL Connection Failed"
            
#         with connection.cursor() as cursor:
#             # Query untuk menghitung luas dalam meter persegi
#             sql = """
#             SELECT 
#                 ST_Area(ST_GeomFromText(%s)) as area_sq_m,
#                 ST_Area(ST_GeomFromText(%s)) / 1000000 as area_sq_km,
#                 ST_Area(ST_GeomFromText(%s)) / 10000 as area_hectare
#             """
#             cursor.execute(sql, (wkt_geometry, wkt_geometry, wkt_geometry))
#             result = cursor.fetchone()
            
#             if result and result['area_sq_m'] is not None:
#                 area_sq_m = float(result['area_sq_m'])
#                 area_sq_km = float(result['area_sq_km'])
#                 area_hectare = float(result['area_hectare'])
                
#                 # Simpan hasil perhitungan ke database
#                 insert_sql = """
#                 INSERT INTO polygon_areas (geometry_wkt, area_sq_m, area_sq_km, area_hectare, utm_zone, method, calculated_at)
#                 VALUES (%s, %s, %s, %s, %s, %s, NOW())
#                 """
#                 cursor.execute(insert_sql, (wkt_geometry, area_sq_m, area_sq_km, area_hectare, app.config['UTM_ZONE'], 'MySQL'))
#                 connection.commit()
                
#                 return area_sq_m, area_sq_km, area_hectare, 'MySQL'
#             else:
#                 return None, None, None, "MySQL Calculation Failed"
                
#     except MySQLError as e:
#         logging.error(f"MySQL Error: {str(e)}")
#         return None, None, None, f"MySQL Error: {str(e)}"
#     finally:
#         if connection:
#             connection.close()

# # Fungsi pembersihan nama kolom untuk Shapefile
# def clean_column_name(col_name):
#     """Batasi panjang kolom dan hapus karakter ilegal untuk Shapefile (DBF)."""
#     cleaned = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
#     return cleaned[:10].upper()

# # ====================================================================
# # FUNGSI INDEX (MAP INITIALIZATION)
# # ====================================================================
# @app.route('/')
# def index():
#     kordinat_awal = [-3.675, 128.220]
#     folium_peta = folium.Map(location=kordinat_awal, zoom_start=15, zoom_control=True) 
#     map_name = folium_peta.get_name()

#     # --- Data Statis (Marker, Polygon, TileLayer) ---
#     x_polygon = [128.199513, 128.187740, 128.188359, 128.200797]
#     y_polygon = [-3.677841, -3.678988, -3.690433, -3.687038]
#     kordinat_polygon = list(zip(x_polygon, y_polygon))
#     polygon_akhir = Polygon(kordinat_polygon)
#     gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')

#     x_marker = [128.222795, 128.156195, 128.255609, 128.150965, 128.202479]
#     y_marker = [-3.626639, -3.622669, -3.657574, -3.649438, -3.595145]
#     kordinat_marker = list(zip(x_marker, y_marker))
#     for x_marker, y_marker in kordinat_marker:
#         folium.Marker(
#             location=[y_marker, x_marker],
#             tooltip='Marker',
#             icon=folium.Icon(color='green', icon='star')
#         ).add_to(folium_peta)

#     x_radius = 128.180946
#     y_radius = -3.698711
#     kordinat_radius = Point(x_radius, y_radius)
#     gdp_radius = gpd.GeoDataFrame(geometry=[kordinat_radius], crs='EPSG:4326')

#     folium.TileLayer(
#         tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
#         attr='Kartendaten: © OpenStreetMap-Mitwirkante, SRTM | Kartendarstellung: © OpenTopoMap (CC-BY-SA)',
#         overlay=False,
#         name='TopoMap',
#         control=True
#     ).add_to(folium_peta)

#     folium.TileLayer(
#         tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#         attr='Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
#         overlay=False,
#         name='ESRI Satelite',
#         control=True
#     ).add_to(folium_peta)
    
#     try:
#         gambar = url_for('static', filename='Gambar/217.jpg', _external=True) 
#     except RuntimeError:
#         gambar = 'static/Gambar/217.jpg'

#     html_polygon = f'''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h2 style="color:black;font-family:Arial;">Kawasan Bebas Kejahatan</h2>
#             <img src="{gambar}" width="250">
#         </body>
#         </html>
#         '''
    
#     html_radius = '''
#         <!DOCTYPE html>
#         <html>
#         <body>
#             <h3 style="color:red;font-family:Arial;">Kawasan Rawan Covid-19</h3>
#         </body>
#         </html>
#         '''
        
#     frame_polygon = folium.IFrame(html=html_polygon, width=300, height=250)
#     popup_polygon = folium.Popup(frame_polygon, max_width=2650)
#     folium.GeoJson(gdp_polygon.to_json(), popup=popup_polygon, style_function=lambda x:{'fillColor': 'Blue', 'color': 'red', 'fillOpacity': 0.3}).add_to(folium_peta)

#     frame_radius = folium.IFrame(html=html_radius, width=300, height=250)
#     popup_radius = folium.Popup(frame_radius, max_width=2650)
#     folium.GeoJson(gdp_radius.to_json(), popup=popup_radius, marker=folium.Circle(color='Black', fillColor='Blue', fillOpacity=0.4, radius=250)).add_to(folium_peta)

#     # FeatureGroup untuk menyimpan hasil gambar pengguna
#     drawn_items = folium.FeatureGroup(name="Drawn Items").add_to(folium_peta)
#     drawn_items_name = drawn_items.get_name()
    
#     # FeatureGroup untuk highlight polygon yang dipilih
#     highlight_group = folium.FeatureGroup(name="Highlighted Polygon").add_to(folium_peta)
#     highlight_group_name = highlight_group.get_name()
    
#     # Draw Control di kanan atas
#     Draw(
#         export=False, 
#         feature_group=drawn_items, 
#         position='topright', 
#         draw_options={
#             'polyline': {'repeatMode': True},
#             'rectangle': {'repeatMode': True},
#             'circle': {'repeatMode': True},
#             'marker': {'repeatMode': True},
#             'polygon': {'allowIntersection': False, 'drawError': {'color': 'red', 'message': 'Error123'}, 'shapeOptions': {'color': 'red'}, 'repeatMode': True}
#         },
#         edit_options={'edit': True, 'remove': True}
#     ).add_to(folium_peta)
    
#     # --- Penambahan Library Turf.js (Perhitungan Geometri) ---
#     turf_js_cdn = '<script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>'
#     folium_peta.get_root().header.add_child(folium.Element(turf_js_cdn))

#     # 🌟 IMPLEMENTASI MENU ALA GOOGLE EARTH PRO (HTML/CSS/JS)
#     html_js = """
#     <style>
#         /* Container untuk seluruh menu */
#         .menu-bar { 
#             position: absolute; 
#             top: 0px; 
#             left: 0px;
#             right:0px; 
#             z-index: 1000; 
#             font-family: Arial, sans-serif;
#             display: flex;
#             background-color: #f9f9f9;
#             border-radius: 4px;
#             box-shadow: 0 2px 5px rgba(0,0,0,0.2);
#             padding: 2px;
#         }
#         .menu-item {
#             position: relative;
#             padding: 5px 10px;
#             cursor: pointer;
#             font-size: 14px;
#             color: #333;
#             user-select: none;
#         }
#         .menu-item:hover {
#             background-color: #ddd;
#             border-radius: 2px;
#         }

#         /* Konten Dropdown */
#         .dropdown-content {
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
#         }
#         .dropdown-content button, .dropdown-content .submenu-item {
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
#         }
#         .dropdown-content button:hover, .dropdown-content .submenu-item:hover {
#             background-color: #007bff;
#             color: white;
#         }
#         .show-dropdown {
#             display: block;
#         }

#         /* Submenu Container */
#         .submenu-item::after {
#             content: '►';
#             float: right;
#             margin-left: 10px;
#             font-size: 10px;
#         }
#         .submenu-content {
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
#         }
#         .submenu-item:hover .submenu-content {
#             display: block;
#         }
        
#         /* PENEMPATAN KONTROL ZOOM */
#         .leaflet-top.leaflet-left {
#             left: auto !important; 
#             right: 5px !important; 
#             top: 30px !important;
#         }
#         .leaflet-top.leaflet-right {
#             top: 120px !important; 
#             transform:translateX(5px);
#         }
        
#         /* STYLE UNTUK TABEL HASIL LUAS YANG BISA DIGESER DENGAN HEADER TETAP */
#         .results-container {
#             position: fixed;
#             top: 100px;
#             right: 20px;
#             width: 500px;
#             background: white;
#             border: 2px solid #2c3e50;
#             border-radius: 8px;
#             box-shadow: 0 4px 15px rgba(0,0,0,0.3);
#             z-index: 999;
#             display: none;
#             max-height: 500px;
#             overflow: hidden;
#             cursor: default;
#         }
        
#         .results-header {
#             background: #2c3e50;
#             color: white;
#             padding: 12px;
#             font-weight: bold;
#             display: flex;
#             justify-content: space-between;
#             align-items: center;
#             cursor: move;
#             user-select: none;
#             border-radius: 6px 6px 0 0;
#         }
        
#         .close-results {
#             background: none;
#             border: none;
#             color: white;
#             font-size: 20px;
#             cursor: pointer;
#             padding: 0;
#             width: 24px;
#             height: 24px;
#             display: flex;
#             align-items: center;
#             justify-content: center;
#             z-index: 1001;
#         }
        
#         .close-results:hover {
#             background: rgba(255,255,255,0.2);
#             border-radius: 50%;
#         }
        
#         /* Container untuk tabel dengan scroll */
#         .table-container {
#             overflow-y: auto;
#             max-height: 400px;
#             position: relative;
#         }
        
#         .results-table {
#             width: 100%;
#             border-collapse: collapse;
#             font-size: 11px;
#         }
        
#         /* Header tabel yang tetap saat di-scroll */
#         .results-table th {
#             background: #f8f9fa;
#             padding: 8px;
#             text-align: left;
#             border-bottom: 2px solid #ddd;
#             font-weight: bold;
#             position: sticky;
#             top: 0;
#             background: #f8f9fa;
#             z-index: 10;
#         }
        
#         .results-table td {
#             padding: 8px;
#             border-bottom: 1px solid #eee;
#             cursor: pointer; /* Baris tabel bisa diklik */
#         }
        
#         .results-table tr:hover {
#             background: #e3f2fd !important; /* Highlight saat hover */
#         }
        
#         .results-table tr.selected {
#             background: #ffeb3b !important; /* Warna kuning untuk baris terpilih */
#             font-weight: bold;
#         }
        
#         .area-value {
#             font-weight: bold;
#             color: #2c3e50;
#         }
        
#         .no-results {
#             padding: 20px;
#             text-align: center;
#             color: #666;
#             font-style: italic;
#         }
        
#         .export-btn {
#             background: #28a745;
#             color: white;
#             border: none;
#             padding: 5px 10px;
#             border-radius: 4px;
#             cursor: pointer;
#             font-size: 10px;
#             margin: 2px;
#             transition: background 0.2s;
#         }
        
#         .export-btn:hover {
#             background: #218838;
#         }
        
#         .delete-btn {
#             background: #dc3545;
#             color: white;
#             border: none;
#             padding: 5px 10px;
#             border-radius: 4px;
#             cursor: pointer;
#             font-size: 10px;
#             margin: 2px;
#             transition: background 0.2s;
#         }
        
#         .delete-btn:hover {
#             background: #c82333;
#         }
        
#         .zoom-btn {
#             background: #ff9800;
#             color: white;
#             border: none;
#             padding: 5px 10px;
#             border-radius: 4px;
#             cursor: pointer;
#             font-size: 10px;
#             margin: 2px;
#             transition: background 0.2s;
#         }
        
#         .zoom-btn:hover {
#             background: #e68900;
#         }
        
#         .loading {
#             display: none;
#             position: fixed;
#             top: 50%;
#             left: 50%;
#             transform: translate(-50%, -50%);
#             background: rgba(255,255,255,0.95);
#             padding: 25px;
#             border-radius: 8px;
#             box-shadow: 0 4px 15px rgba(0,0,0,0.3);
#             z-index: 1000;
#             border: 1px solid #ccc;
#         }
        
#         .info-panel {
#             position: fixed;
#             bottom: 20px;
#             left: 20px;
#             background: white;
#             padding: 12px;
#             border-radius: 6px;
#             box-shadow: 0 2px 10px rgba(0,0,0,0.2);
#             font-size: 12px;
#             z-index: 998;
#             cursor: move;
#             user-select: none;
#             border: 1px solid #2c3e50;
#             max-width: 250px;
#         }
        
#         /* Style untuk indikator draggable */
#         .drag-handle {
#             cursor: move;
#             margin-right: 8px;
#             font-size: 16px;
#         }
        
#         /* Style saat sedang dragging */
#         .dragging {
#             opacity: 0.9;
#             box-shadow: 0 6px 20px rgba(0,0,0,0.4);
#             border-color: #007bff;
#         }
        
#         /* Responsive design */
#         @media (max-width: 768px) {
#             .results-container {
#                 width: 90%;
#                 right: 5%;
#                 left: 5%;
#             }
#         }
        
#         /* Scrollbar styling */
#         .table-container::-webkit-scrollbar {
#             width: 8px;
#         }
        
#         .table-container::-webkit-scrollbar-track {
#             background: #f1f1f1;
#             border-radius: 4px;
#         }
        
#         .table-container::-webkit-scrollbar-thumb {
#             background: #c1c1c1;
#             border-radius: 4px;
#         }
        
#         .table-container::-webkit-scrollbar-thumb:hover {
#             background: #a8a8a8;
#         }
        
#         /* Style untuk highlight polygon */
#         .highlight-polygon {
#             stroke: #ff0000 !important;
#             stroke-width: 4 !important;
#             stroke-opacity: 1 !important;
#             fill-color: #ffff00 !important;
#             fill-opacity: 0.3 !important;
#         }
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

#         <!-- MENU ANALISIS - PERTAHANKAN FITUR HITUNG LUAS POLYGON -->
#         <div class='menu-item' onclick="toggleMenu('analysis')">Analisis</div>
#         <div id='analysisDropdown' class='dropdown-content'>
#             <button onclick="calculateAllPolygonsArea()">Hitung Luas Semua Polygon</button>
#             <button onclick="showResultsTable()">Tampilkan Hasil</button>
#             <button onclick="clearAllResults()">Hapus Semua Hasil</button>
#             <button onclick="clearHighlight()">Hapus Highlight</button>
#         </div>

#     </div>

#     <!-- CONTAINER UNTUK TABEL HASIL LUAS YANG BISA DIGESER DENGAN HEADER TETAP -->
#     <div id="resultsContainer" class="results-container">
#         <div class="results-header" id="resultsHeader">
#             <span>📋 Hasil Perhitungan Luas</span>
#             <button class="close-results" onclick="hideResultsTable()">×</button>
#         </div>
#         <div class="table-container">
#             <table class="results-table">
#                 <thead>
#                     <tr>
#                         <th>ID</th>
#                         <th>Luas (m²)</th>
#                         <th>Luas (ha)</th>
#                         <th>Luas (km²)</th>
#                         <th>Aksi</th>
#                     </tr>
#                 </thead>
#                 <tbody id="resultsBody">
#                     <!-- Data hasil akan dimasukkan di sini oleh JavaScript -->
#                 </tbody>
#             </table>
#         </div>
#     </div>

#     <!-- INFO PANEL UTM YANG BISA DIGESER -->
#     <div class="info-panel" id="infoPanel">
#         <div style="font-weight: bold; margin-bottom: 5px;">🌍 Informasi Peta</div>
#         <strong>UTM Zone:</strong> 52S (EPSG:32752)<br>
#         <strong>Lokasi:</strong> Maluku, Indonesia<br>
#         <strong>Status:</strong> <span id="drawingStatus">Siap</span><br>
#         <strong>Polygon Terpilih:</strong> <span id="selectedPolygon">Tidak ada</span>
#     </div>

#     <!-- LOADING INDICATOR -->
#     <div id="loadingIndicator" class="loading">
#         <div style="text-align: center;">
#             <div style="font-size: 16px; margin-bottom: 10px;">🔄 Menghitung Luas</div>
#             <div>Menggunakan UTM Zone 52S...</div>
#             <div style="margin-top: 10px; font-size: 12px; color: #666;">Harap tunggu</div>
#         </div>
#     </div>

#     <script>
#         // FUNGSI FORMAT NUMBER DI SCOPE GLOBAL
#         function formatNumber(num) {
#             return num.toFixed(2).replace(/\\d(?=(\\d{3})+\\.)/g, '$&.').replace('.', ',');
#         }
        
#         function formatNumberForDisplay(num) {
#             return new Intl.NumberFormat('id-ID', {
#                 minimumFractionDigits: 2,
#                 maximumFractionDigits: 2
#             }).format(num);
#         }
        
#         // FUNGSI KHUSUS UNTUK FORMAT KM² - HAPUS ANGKA 0 DI DEPAN
#         function formatKm2(num) {
#             if (num < 1 && num > 0) {
#                 // Hilangkan angka 0 di depan untuk angka desimal kecil
#                 return num.toFixed(6).replace('0.', '.');
#             } else {
#                 return num.toFixed(6);
#             }
#         }

#         const menuItems = [
#             {id: 'fileDropdown', parentId: 'file'},
#             {id: 'editDropdown', parentId: 'edit'},
#             {id: 'viewDropdown', parentId: 'view'},
#             {id: 'analysisDropdown', parentId: 'analysis'}
#         ];
        
#         // Array untuk menyimpan hasil perhitungan
#         let areaResults = [];
        
#         // Variabel untuk menyimpan layer polygon yang sesuai dengan hasil
#         let polygonLayers = new Map();
        
#         // Variabel untuk highlight layer
#         let currentHighlightLayer = null;
#         let currentSelectedRow = null;
        
#         // Variabel untuk drag functionality
#         let dragState = {
#             isDragging: false,
#             currentDraggable: null,
#             dragOffset: { x: 0, y: 0 },
#             startX: 0,
#             startY: 0
#         };

#         // FUNGSI DRAG AND DROP YANG DIPERBAIKI
#         function initializeDraggable(element) {
#             const header = element.querySelector('.results-header') || element;
            
#             header.addEventListener('mousedown', startDrag);
#             header.addEventListener('touchstart', startDragTouch, { passive: false });
            
#             function startDrag(e) {
#                 if (e.target.classList.contains('close-results')) {
#                     return;
#                 }
                
#                 e.preventDefault();
#                 dragState.isDragging = true;
#                 dragState.currentDraggable = element;
                
#                 const rect = element.getBoundingClientRect();
#                 dragState.dragOffset.x = e.clientX - rect.left;
#                 dragState.dragOffset.y = e.clientY - rect.top;
#                 dragState.startX = e.clientX;
#                 dragState.startY = e.clientY;
                
#                 element.classList.add('dragging');
                
#                 document.addEventListener('mousemove', onDrag);
#                 document.addEventListener('mouseup', stopDrag);
#             }
            
#             function startDragTouch(e) {
#                 if (e.target.classList.contains('close-results')) {
#                     return;
#                 }
                
#                 e.preventDefault();
#                 const touch = e.touches[0];
#                 dragState.isDragging = true;
#                 dragState.currentDraggable = element;
                
#                 const rect = element.getBoundingClientRect();
#                 dragState.dragOffset.x = touch.clientX - rect.left;
#                 dragState.dragOffset.y = touch.clientY - rect.top;
#                 dragState.startX = touch.clientX;
#                 dragState.startY = touch.clientY;
                
#                 element.classList.add('dragging');
                
#                 document.addEventListener('touchmove', onDragTouch, { passive: false });
#                 document.addEventListener('touchend', stopDrag);
#             }
            
#             function onDrag(e) {
#                 if (!dragState.isDragging || dragState.currentDraggable !== element) return;
                
#                 e.preventDefault();
                
#                 const x = e.clientX - dragState.dragOffset.x;
#                 const y = e.clientY - dragState.dragOffset.y;
                
#                 applyNewPosition(element, x, y);
#             }
            
#             function onDragTouch(e) {
#                 if (!dragState.isDragging || dragState.currentDraggable !== element) return;
                
#                 e.preventDefault();
#                 const touch = e.touches[0];
                
#                 const x = touch.clientX - dragState.dragOffset.x;
#                 const y = touch.clientY - dragState.dragOffset.y;
                
#                 applyNewPosition(element, x, y);
#             }
            
#             function stopDrag() {
#                 if (dragState.isDragging && dragState.currentDraggable === element) {
#                     dragState.isDragging = false;
#                     dragState.currentDraggable = null;
#                     element.classList.remove('dragging');
                    
#                     savePanelPosition(element.id, {
#                         left: element.style.left,
#                         top: element.style.top
#                     });
                    
#                     document.removeEventListener('mousemove', onDrag);
#                     document.removeEventListener('touchmove', onDragTouch);
#                     document.removeEventListener('mouseup', stopDrag);
#                     document.removeEventListener('touchend', stopDrag);
#                 }
#             }
#         }
        
#         // FUNGSI UNTUK MENERAPKAN POSISI BARU DENGAN BATASAN
#         function applyNewPosition(element, x, y) {
#             const viewportWidth = window.innerWidth;
#             const viewportHeight = window.innerHeight;
#             const elementWidth = element.offsetWidth;
#             const elementHeight = element.offsetHeight;
            
#             const boundedX = Math.max(10, Math.min(x, viewportWidth - elementWidth - 10));
#             const boundedY = Math.max(10, Math.min(y, viewportHeight - elementHeight - 10));
            
#             element.style.left = boundedX + 'px';
#             element.style.top = boundedY + 'px';
#             element.style.right = 'auto';
#             element.style.bottom = 'auto';
#         }
        
#         // FUNGSI UNTUK MENYIMPAN POSISI PANEL
#         function savePanelPosition(panelId, position) {
#             try {
#                 const positions = JSON.parse(localStorage.getItem('panelPositions') || '{}');
#                 positions[panelId] = position;
#                 localStorage.setItem('panelPositions', JSON.stringify(positions));
#             } catch (e) {
#                 console.error('Error saving panel position:', e);
#             }
#         }
        
#         // FUNGSI UNTUK MEMUAT POSISI PANEL YANG DISIMPAN
#         function loadPanelPosition(panelId, defaultPosition) {
#             try {
#                 const positions = JSON.parse(localStorage.getItem('panelPositions') || '{}');
#                 const position = positions[panelId];
#                 const element = document.getElementById(panelId);
                
#                 if (element && position) {
#                     if (position.left && position.top) {
#                         element.style.left = position.left;
#                         element.style.top = position.top;
#                         element.style.right = 'auto';
#                         element.style.bottom = 'auto';
#                     }
#                 } else if (element && defaultPosition) {
#                     if (defaultPosition.left) element.style.left = defaultPosition.left;
#                     if (defaultPosition.top) element.style.top = defaultPosition.top;
#                     if (defaultPosition.right) element.style.right = defaultPosition.right;
#                     if (defaultPosition.bottom) element.style.bottom = defaultPosition.bottom;
#                 }
#             } catch (e) {
#                 console.error('Error loading panel position:', e);
#             }
#         }

#         function closeAllMenus(exceptId) {
#             for (let i = 0; i < menuItems.length; i++) {
#                 const item = menuItems[i];
#                 if (item.id !== exceptId) {
#                     document.getElementById(item.id).classList.remove('show-dropdown');
#                 }
#             }
#         }
        
#         function closeAllSubmenus() {
#             const submenus = document.getElementsByClassName('submenu-content');
#             for (let i = 0; i < submenus.length; i++) {
#                 submenus[i].style.display = 'none';
#             }
#         }

#         function toggleMenu(menuName) {
#             const id = menuName + 'Dropdown';
#             const dropdown = document.getElementById(id);
            
#             if (dropdown.classList.contains('show-dropdown')) {
#                 dropdown.classList.remove('show-dropdown');
#                 closeAllSubmenus();
#             } else {
#                 closeAllMenus(id);
#                 dropdown.classList.add('show-dropdown');
#             }
#         }
        
#         function showSubmenu(id) {
#             document.getElementById(id).style.display = 'block';
#         }
        
#         function hideSubmenu(id) {
#              setTimeout(() => { 
#                  const submenu = document.getElementById(id);
#                  if (!submenu.matches(':hover') && !submenu.parentElement.matches(':hover')) {
#                      submenu.style.display = 'none';
#                  }
#              }, 50);
#         }

#         window.onclick = function(event) {
#             const menuBar = document.getElementById('menuBar');
#             if (!menuBar.contains(event.target)) {
#                 closeAllMenus(null);
#                 closeAllSubmenus();
#             }
#         }
        
#         function getDrawnItems() {
#             const drawnItemsName = """ + json.dumps(drawn_items_name) + """;
#             let drawnItems = window[drawnItemsName];
            
#             if (!drawnItems) {
#                 const mapName = """ + json.dumps(map_name) + """;
#                 const mapElement = document.getElementById(mapName);
#                 if (mapElement && mapElement._leaflet_map) {
#                     const leafletMap = mapElement._leaflet_map;
#                     leafletMap.eachControl(function(control) {
#                         if(control.options && control.options.edit && control.options.edit.featureGroup){
#                             drawnItems = control.options.edit.featureGroup;
#                         }
#                     });
#                 }
#             }
#             return drawnItems;
#         }
        
#         // FUNGSI UNTUK MENDAPATKAN HIGHLIGHT GROUP
#         function getHighlightGroup() {
#             const highlightGroupName = """ + json.dumps(highlight_group_name) + """;
#             let highlightGroup = window[highlightGroupName];
            
#             if (!highlightGroup) {
#                 const mapName = """ + json.dumps(map_name) + """;
#                 const mapElement = document.getElementById(mapName);
#                 if (mapElement && mapElement._leaflet_map) {
#                     const leafletMap = mapElement._leaflet_map;
#                     leafletMap.eachLayer(function(layer) {
#                         if(layer instanceof L.FeatureGroup && layer.options && layer.options.name === "Highlighted Polygon") {
#                             highlightGroup = layer;
#                         }
#                     });
#                 }
#             }
#             return highlightGroup;
#         }
        
#         function performExport(format) {
#             const drawnItems = getDrawnItems();
#             closeAllMenus(null);

#             if (!drawnItems || drawnItems.getLayers().length === 0) {
#                 alert("Harap gambar setidaknya satu fitur untuk diekspor.");
#                 return;
#             }
            
#             try {
#                 const geojson = drawnItems.toGeoJSON();
                
#                 const form = document.createElement('form');
#                 form.method = 'POST';
                
#                 if (format === 'shp') {
#                     form.action = """ + json.dumps(url_for('export_to_shp')) + """;
#                 } else if (format === 'geojson') {
#                     form.action = """ + json.dumps(url_for('export_to_geojson')) + """;
#                 } else {
#                     alert("Format export tidak valid.");
#                     return;
#                 }
                
#                 const input = document.createElement('input');
#                 input.type = 'hidden';
#                 input.name = 'geojson_data';
#                 input.value = JSON.stringify(geojson);
#                 form.appendChild(input);

#                 document.body.appendChild(form);
#                 form.submit();
#                 document.body.removeChild(form);
                
#             } catch (error) {
#                 console.error("Error creating GeoJSON:", error);
#                 alert("Error membuat data export: " + error.message);
#             }
#         }

#         // FUNGSI HITUNG LUAS SEMUA POLYGON DENGAN UTM ZONE 52S
#         function calculateAllPolygonsArea() {
#             const drawnItems = getDrawnItems();
#             closeAllMenus(null);

#             if (!drawnItems) {
#                 alert("Tidak ada layer yang digambar.");
#                 return;
#             }

#             // Dapatkan semua polygon
#             const layers = drawnItems.getLayers();
#             const polygons = layers.filter(layer => layer instanceof L.Polygon);

#             if (polygons.length === 0) {
#                 alert("Tidak ada polygon yang ditemukan. Harap gambar polygon terlebih dahulu.");
#                 return;
#             }

#             // Tampilkan loading
#             showLoading();
#             updateDrawingStatus('Menghitung luas semua polygon...');
            
#             let completedCalculations = 0;
#             let totalPolygons = polygons.length;
#             let successfulCalculations = 0;

#             // Hitung luas untuk setiap polygon
#             polygons.forEach((polygon, index) => {
#                 const geojson = polygon.toGeoJSON();
                
#                 // Kirim data ke server untuk perhitungan luas dengan UTM 52S
#                 fetch(""" + json.dumps(url_for('calculate_area_json')) + """, {
#                     method: 'POST',
#                     headers: {
#                         'Content-Type': 'application/json',
#                     },
#                     body: JSON.stringify({geojson_data: geojson})
#                 })
#                 .then(response => response.json())
#                 .then(data => {
#                     completedCalculations++;
                    
#                     if (data.success) {
#                         successfulCalculations++;
                        
#                         // Simpan layer polygon yang sesuai dengan hasil
#                         const resultId = areaResults.length + 1;
                        
#                         // Tambahkan ke hasil
#                         addAreaResult({
#                             id: resultId,
#                             area_m2: data.area_sq_m,
#                             area_hectare: data.area_hectare,
#                             area_km2: data.area_sq_km,
#                             method: data.method,
#                             utm_zone: data.utm_zone,
#                             timestamp: new Date().toLocaleString('id-ID'),
#                             geometry: data.geometry_wkt,
#                             layer: polygon // Simpan reference ke layer
#                         });
                        
#                         // Simpan mapping antara resultId dan layer
#                         polygonLayers.set(resultId, polygon);
                        
#                         // Update popup untuk polygon ini
#                         polygon.bindPopup(
#                             '<div style=\"font-size: 12px;\">' +
#                             '<h4>Hasil Perhitungan Luas (Polygon ' + completedCalculations + ')</h4>' +
#                             '<p><strong>Luas:</strong> ' + formatNumberForDisplay(data.area_sq_m) + ' m²</p>' +
#                             '<p><strong>Luas:</strong> ' + data.area_hectare.toFixed(4) + ' ha</p>' +
#                             '<p><strong>Luas:</strong> ' + formatKm2(data.area_sq_km) + ' km²</p>' +
#                             '<p><strong>Metode:</strong> ' + data.method + '</p>' +
#                             '<p><strong>UTM Zone:</strong> ' + data.utm_zone + '</p>' +
#                             '</div>'
#                         );
#                     }
                    
#                     // Jika semua perhitungan selesai
#                     if (completedCalculations === totalPolygons) {
#                         hideLoading();
#                         updateDrawingStatus('Siap');
                        
#                         // Tampilkan tabel hasil
#                         showResultsTable();
                        
#                         // Tampilkan konfirmasi sukses
#                         if (successfulCalculations > 0) {
#                             alert('Berhasil menghitung luas ' + successfulCalculations + ' dari ' + totalPolygons + ' polygon!\\nMetode: ' + data.method + '\\nUTM Zone: ' + data.utm_zone);
#                         } else {
#                             alert("Gagal menghitung luas semua polygon.");
#                         }
#                     }
#                 })
#                 .catch(error => {
#                     completedCalculations++;
#                     console.error('Error:', error);
                    
#                     // Jika semua perhitungan selesai (termasuk yang error)
#                     if (completedCalculations === totalPolygons) {
#                         hideLoading();
#                         updateDrawingStatus('Error');
                        
#                         if (successfulCalculations > 0) {
#                             alert('Berhasil menghitung luas ' + successfulCalculations + ' dari ' + totalPolygons + ' polygon. Beberapa polygon gagal dihitung.');
#                         } else {
#                             alert("Error menghitung luas semua polygon.");
#                         }
#                     }
#                 });
#             });
#         }
        
#         // FUNGSI UNTUK MENAMBAHKAN HASIL KE TABEL (TANPA KOLOM METODE)
#         function addAreaResult(result) {
#             areaResults.push(result);
#             updateResultsTable();
#         }
        
#         // FUNGSI UNTUK UPDATE TABEL HASIL (TANPA KOLOM METODE)
#         function updateResultsTable() {
#             const tbody = document.getElementById('resultsBody');
#             tbody.innerHTML = '';
            
#             if (areaResults.length === 0) {
#                 tbody.innerHTML = '<tr><td colspan=\"5\" class=\"no-results\">Belum ada hasil perhitungan</td></tr>';
#                 return;
#             }
            
#             areaResults.forEach((result, index) => {
#                 const row = document.createElement('tr');
#                 row.setAttribute('data-result-id', result.id);
#                 row.innerHTML =
#                     '<td>' + result.id + '</td>' +
#                     '<td><span class=\"area-value\">' + formatNumberForDisplay(result.area_m2) + '</span></td>' +
#                     '<td><span class=\"area-value\">' + result.area_hectare.toFixed(4) + '</span></td>' +
#                     '<td><span class=\"area-value\">' + formatKm2(result.area_km2) + '</span></td>' +
#                     '<td>' +
#                     '<button class=\"zoom-btn\" onclick=\"zoomToPolygon(' + result.id + ', event)\">Zoom</button>' +
#                     '<button class=\"export-btn\" onclick=\"exportResult(' + index + ', event)\">Ekspor</button>' +
#                     '<button class=\"delete-btn\" onclick=\"deleteResult(' + index + ', event)\">Hapus</button>' +
#                     '</td>';
                
#                 // Tambah event listener untuk klik baris
#                 row.addEventListener('click', function(e) {
#                     // Jangan trigger jika klik pada tombol aksi
#                     if (!e.target.classList.contains('export-btn') && 
#                         !e.target.classList.contains('delete-btn') &&
#                         !e.target.classList.contains('zoom-btn')) {
#                         selectPolygon(result.id);
#                     }
#                 });
                
#                 tbody.appendChild(row);
#             });
#         }
        
#         // FUNGSI UNTUK MEMILIH POLYGON SAAT BARIS DIKLIK
#         function selectPolygon(resultId) {
#             // Hapus seleksi sebelumnya
#             if (currentSelectedRow) {
#                 currentSelectedRow.classList.remove('selected');
#             }
            
#             // Set seleksi baru
#             const rows = document.querySelectorAll('#resultsBody tr');
#             rows.forEach(row => {
#                 if (parseInt(row.getAttribute('data-result-id')) === resultId) {
#                     row.classList.add('selected');
#                     currentSelectedRow = row;
#                 }
#             });
            
#             // Highlight polygon di peta
#             highlightPolygon(resultId);
            
#             // Update info panel
#             updateSelectedPolygonInfo(resultId);
#         }
        
#         // FUNGSI UNTUK HIGHLIGHT POLYGON DI PETA
#         function highlightPolygon(resultId) {
#             const layer = polygonLayers.get(resultId);
#             const highlightGroup = getHighlightGroup();
            
#             if (!layer || !highlightGroup) {
#                 console.error('Layer atau highlight group tidak ditemukan');
#                 return;
#             }
            
#             // Hapus highlight sebelumnya
#             clearHighlight();
            
#             // Buat salinan layer dengan style highlight
#             const geojson = layer.toGeoJSON();
#             const highlightLayer = L.geoJSON(geojson, {
#                 style: {
#                     color: '#ff0000',
#                     weight: 4,
#                     opacity: 1,
#                     fillColor: '#ffff00',
#                     fillOpacity: 0.3
#                 },
#                 className: 'highlight-polygon'
#             });
            
#             // Tambahkan ke highlight group
#             highlightGroup.addLayer(highlightLayer);
#             currentHighlightLayer = highlightLayer;
            
#             // Zoom ke polygon yang dipilih
#             const map = getMap();
#             map.fitBounds(highlightLayer.getBounds());
#         }
        
#         // FUNGSI UNTUK ZOOM KE POLYGON
#         function zoomToPolygon(resultId, event) {
#             if (event) event.stopPropagation();
            
#             const layer = polygonLayers.get(resultId);
#             if (layer) {
#                 const map = getMap();
#                 map.fitBounds(layer.getBounds());
#                 selectPolygon(resultId); // Juga select polygon tersebut
#             }
#         }
        
#         // FUNGSI UNTUK MENGHAPUS HIGHLIGHT
#         function clearHighlight() {
#             if (currentHighlightLayer) {
#                 const highlightGroup = getHighlightGroup();
#                 if (highlightGroup) {
#                     highlightGroup.removeLayer(currentHighlightLayer);
#                 }
#                 currentHighlightLayer = null;
#             }
            
#             // Hapus seleksi baris
#             if (currentSelectedRow) {
#                 currentSelectedRow.classList.remove('selected');
#                 currentSelectedRow = null;
#             }
            
#             // Update info panel
#             updateSelectedPolygonInfo(null);
#         }
        
#         // FUNGSI UNTUK UPDATE INFO POLYGON TERPILIH
#         function updateSelectedPolygonInfo(resultId) {
#             const selectedPolygonElement = document.getElementById('selectedPolygon');
#             if (resultId) {
#                 selectedPolygonElement.textContent = 'ID: ' + resultId;
#                 selectedPolygonElement.style.color = '#28a745';
#                 selectedPolygonElement.style.fontWeight = 'bold';
#             } else {
#                 selectedPolygonElement.textContent = 'Tidak ada';
#                 selectedPolygonElement.style.color = '#6c757d';
#                 selectedPolygonElement.style.fontWeight = 'normal';
#             }
#         }
        
#         // FUNGSI UNTUK MENDAPATKAN MAP
#         function getMap() {
#             const mapName = """ + json.dumps(map_name) + """;
#             const mapElement = document.getElementById(mapName);
#             return mapElement ? mapElement._leaflet_map : null;
#         }
        
#         // FUNGSI UNTUK MENAMPILKAN TABEL HASIL
#         function showResultsTable() {
#             const resultsContainer = document.getElementById('resultsContainer');
#             resultsContainer.style.display = 'block';
#             updateResultsTable();
            
#             // Inisialisasi drag functionality
#             initializeDraggable(resultsContainer);
#             loadPanelPosition('resultsContainer', { 
#                 left: 'auto', 
#                 top: '100px', 
#                 right: '20px', 
#                 bottom: 'auto' 
#             });
            
#             ensureElementInViewport(resultsContainer);
#         }
        
#         // FUNGSI UNTUK MENYEMBUNYIKAN TABEL HASIL
#         function hideResultsTable() {
#             document.getElementById('resultsContainer').style.display = 'none';
#         }
        
#         // FUNGSI BARU: HAPUS SEMUA HASIL
#         function clearAllResults() {
#             if (areaResults.length === 0) {
#                 alert("Tidak ada hasil yang bisa dihapus.");
#                 return;
#             }
            
#             if (confirm('Apakah Anda yakin ingin menghapus semua ' + areaResults.length + ' hasil perhitungan?')) {
#                 areaResults = [];
#                 polygonLayers.clear();
#                 clearHighlight();
#                 updateResultsTable();
#                 alert("Semua hasil perhitungan telah dihapus.");
#             }
#         }
        
#         // FUNGSI UNTUK EKSPOR HASIL
#         function exportResult(index, event) {
#             if (event) event.stopPropagation();
            
#             const result = areaResults[index];
#             const data = 'HASIL PERHITUNGAN LUAS POLYGON\\n' +
#                         '===============================\\n' +
#                         'ID: ' + result.id + '\\n' +
#                         'Luas (m²): ' + formatNumberForDisplay(result.area_m2) + '\\n' +
#                         'Luas (hektar): ' + result.area_hectare.toFixed(4) + '\\n' +
#                         'Luas (km²): ' + formatKm2(result.area_km2) + '\\n' +
#                         'Metode: ' + result.method + '\\n' +
#                         'UTM Zone: ' + result.utm_zone + '\\n' +
#                         'Waktu: ' + result.timestamp + '\\n' +
#                         '===============================';
            
#             const blob = new Blob([data], { type: 'text/plain' });
#             const url = URL.createObjectURL(blob);
#             const a = document.createElement('a');
#             a.href = url;
#             a.download = 'luas_polygon_' + result.id + '_utm_' + result.utm_zone + '.txt';
#             document.body.appendChild(a);
#             a.click();
#             document.body.removeChild(a);
#             URL.revokeObjectURL(url);
#         }
        
#         // FUNGSI UNTUK MENGHAPUS HASIL
#         function deleteResult(index, event) {
#             if (event) event.stopPropagation();
            
#             const result = areaResults[index];
#             if (confirm('Hapus hasil perhitungan ID ' + result.id + '?')) {
#                 // Hapus dari polygonLayers map
#                 polygonLayers.delete(result.id);
                
#                 // Hapus dari array results
#                 areaResults.splice(index, 1);
                
#                 // Jika yang dihapus adalah yang sedang dipilih, clear highlight
#                 if (currentSelectedRow && parseInt(currentSelectedRow.getAttribute('data-result-id')) === result.id) {
#                     clearHighlight();
#                 }
                
#                 updateResultsTable();
#             }
#         }
        
#         // FUNGSI LOADING
#         function showLoading() {
#             document.getElementById('loadingIndicator').style.display = 'block';
#         }
        
#         function hideLoading() {
#             document.getElementById('loadingIndicator').style.display = 'none';
#         }
        
#         // FUNGSI UNTUK UPDATE STATUS DI INFO PANEL
#         function updateDrawingStatus(status) {
#             const statusElement = document.getElementById('drawingStatus');
#             if (statusElement) {
#                 statusElement.textContent = status;
                
#                 if (status === 'Siap') {
#                     statusElement.style.color = '#28a745';
#                 } else if (status === 'Menghitung luas semua polygon...') {
#                     statusElement.style.color = '#ffc107';
#                 } else if (status === 'Error') {
#                     statusElement.style.color = '#dc3545';
#                 } else {
#                     statusElement.style.color = '#6c757d';
#                 }
#             }
#         }
        
#         // FUNGSI UNTUK MEMASTIKAN ELEMEN TIDAK KELUAR DARI VIEWPORT
#         function ensureElementInViewport(element) {
#             const rect = element.getBoundingClientRect();
#             const viewportWidth = window.innerWidth;
#             const viewportHeight = window.innerHeight;
            
#             if (rect.right > viewportWidth || rect.bottom > viewportHeight || rect.left < 0 || rect.top < 0) {
#                 element.style.left = 'auto';
#                 element.style.top = '100px';
#                 element.style.right = '20px';
#                 element.style.bottom = 'auto';
#             }
#         }

#         window.onload = function() {
#             const mapName = """ + json.dumps(map_name) + """;
#             const map = document.getElementById(mapName)._leaflet_map;
            
#             // Inisialisasi drag functionality untuk info panel
#             const infoPanel = document.getElementById('infoPanel');
#             if (infoPanel) {
#                 initializeDraggable(infoPanel);
#                 loadPanelPosition('infoPanel', { 
#                     left: '20px', 
#                     top: 'auto', 
#                     right: 'auto', 
#                     bottom: '20px' 
#                 });
#             }
            
#             setTimeout(function() { 
#                 if (getDrawnItems()) {
#                     document.getElementById('menuBar').style.display = 'flex';
#                     updateDrawingStatus('Siap');
#                 } else {
#                     console.error("Drawn Items FeatureGroup is NOT accessible. Export dinonaktifkan.");
#                     updateDrawingStatus('Error - Restart Aplikasi');
#                 }
#             }, 1000); 

#             // LOGIKA PERHITUNGAN PANJANG DENGAN TURF.JS
#             map.on(L.Draw.Event.CREATED, function (e) {
#                 const layer = e.layer;
#                 const type = String(e.layerType || '').toLowerCase(); 
                
#                 if (!type) {
#                     getDrawnItems().addLayer(layer);
#                     return;
#                 }

#                 let popupContent = '<h4>Hasil Pengukuran</h4>';
                
#                 try {
#                     const geojsonFeature = layer.toGeoJSON();

#                     if (type === 'polyline') {
#                         const lengthKm = turf.length(geojsonFeature, {units: 'kilometers'});
#                         const lengthM = lengthKm * 1000;

#                         popupContent +=
#                             '<p>Tipe: Garis</p>' +
#                             '<p>Panjang: <b>' + formatNumber(lengthM) + '</b> meter</p>' +
#                             '<p>Panjang: <b>' + formatNumber(lengthKm) + '</b> km</p>';
#                     } else if (type === 'circle') {
#                         const radiusM = layer.getRadius();
#                         const radiusKm = radiusM / 1000;
                        
#                         popupContent +=
#                             '<p>Tipe: Circle</p>' +
#                             '<p>Radius: <b>' + formatNumber(radiusM) + '</b> meter</p>' +
#                             '<p>Radius: <b>' + formatNumber(radiusKm) + '</b> km</p>';
#                     } else if (type === 'marker') {
#                         popupContent += '<p>Tipe: Titik</p><p>Koordinat: ' + layer.getLatLng().lat.toFixed(6) + ', ' + layer.getLatLng().lng.toFixed(6) + '</p>';
#                     } else {
#                         const displayType = type.charAt(0).toUpperCase() + type.slice(1);
#                         popupContent += '<p>Tipe: ' + displayType + '</p>';
#                     }

#                     layer.bindPopup(popupContent).openPopup();

#                 } catch (e) {
#                     console.error("Error calculating geometry or binding popup:", e);
#                     layer.bindPopup('Error saat menghitung geometri: ' + e.message).openPopup();
#                 }
                
#                 getDrawnItems().addLayer(layer);
#             });

#         };
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
# # Endpoint Export GeoJSON
# # --------------------------------------------------------------------------------------
# @app.route('/export_to_geojson', methods=['POST'])
# def export_to_geojson():
#     logging.info("=== Mulai Proses Export GeoJSON ===")
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
# # Endpoint Export SHP
# # --------------------------------------------------------------------------------------
# @app.route('/export_to_shp', methods=['POST'])
# def export_to_shp():
#     logging.info("=== Mulai Proses Export SHP ===")
#     geojson_str = request.form.get('geojson_data')

#     if not geojson_str:
#         logging.error("tidak ada data GeoJSON yang diterima")
#         return "Tidak ada data GeoJSON yang diterima.", 400 
    
#     temp_dir = tempfile.mkdtemp()
    
#     try:
#         geojson_data = json.loads(geojson_str)
        
#         if not geojson_data.get('features'):
#             return "Tidak ada data fitur untuk diekspor.", 400

#         valid_features = []
#         for i, feature in enumerate(geojson_data['features']):
#             try:
#                 if not feature.get('geometry'):
#                     continue
                    
#                 original_props = feature.get('properties', {})
#                 geom_shape = shape(feature['geometry'])
                
#                 is_folium_circle = 'radius' in original_props and geom_shape.geom_type == 'Polygon'
                
#                 if is_folium_circle:
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
                
#                 valid_features[-1]['properties']['ID_FITUR'] = i + 1 
                
#             except Exception as e:
#                 logging.error(f"Error processing feature {i}: {str(e)}")
#                 continue

#         if not valid_features:
#             return "Tidak ada geometri valid yang dapat diekspor.", 400
        
#         gdf_all = gpd.GeoDataFrame.from_features(valid_features, crs='EPSG:4326')
        
#         cleaned_columns = {}
#         for col in gdf_all.columns:
#             if col == 'geometry':
#                 cleaned_columns[col] = col
#             else:
#                 cleaned_columns[col] = clean_column_name(col)
        
#         gdf_all.rename(columns=cleaned_columns, inplace=True)
#         gdf_all = gdf_all.set_geometry('geometry')
        
#         gdf_points = gdf_all[gdf_all.geometry.type.isin(['Point'])]
#         gdf_lines = gdf_all[gdf_all.geometry.type.isin(['LineString', 'MultiLineString'])]
#         gdf_polygons = gdf_all[gdf_all.geometry.type.isin(['Polygon', 'MultiPolygon'])]

#         files_created = []
        
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
#             return "Tidak ada data yang dapat diekspor ke Shapefile.", 400

#         zip_buffer = io.BytesIO()
#         with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
#             for root, dirs, files in os.walk(temp_dir):
#                 for file in files:
#                     if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
#                         file_path = os.path.join(root, file)
#                         arcname = os.path.relpath(file_path, temp_dir)
#                         zf.write(file_path, arcname)

#         zip_buffer.seek(0)

#         return send_file(
#             zip_buffer,
#             download_name='peta_digambar.zip',
#             mimetype='application/zip',
#             as_attachment=True
#         )

#     except json.JSONDecodeError as e:
#         return f"Error dalam format data GeoJSON: {str(e)}", 400
        
#     except Exception as e:
#         logging.error(f"Fatal error during SHP export: {str(e)}", exc_info=True)
#         return f"Terjadi kesalahan fatal saat memproses file: {str(e)}", 500
        
#     finally:
#         if os.path.exists(temp_dir):
#             shutil.rmtree(temp_dir)

# # --------------------------------------------------------------------------------------
# # Endpoint untuk menghitung luas polygon dengan UTM Zone 52S
# # --------------------------------------------------------------------------------------
# @app.route('/calculate_area_json', methods=['POST'])
# def calculate_area_json():
#     """Menghitung luas polygon menggunakan UTM Zone 52S dan mengembalikan response JSON"""
#     logging.info("=== Mulai Perhitungan Luas Polygon dengan UTM Zone 52S ===")
    
#     try:
#         data = request.get_json()
#         geojson_data = data.get('geojson_data')
        
#         if not geojson_data:
#             return jsonify({
#                 'success': False,
#                 'error': 'Tidak ada data polygon yang diterima.'
#             }), 400
        
#         if not geojson_data.get('geometry'):
#             return jsonify({
#                 'success': False,
#                 'error': 'Data geometry tidak valid.'
#             }), 400
        
#         # Konversi GeoJSON ke Shapely geometry
#         geom = shape(geojson_data['geometry'])
#         wkt_geometry = geom.wkt
        
#         # Priority 1: Hitung dengan UTM Zone 52S (paling akurat untuk lokasi Anda)
#         try:
#             area_sq_m, area_sq_km, area_hectare = calculate_area_utm(geom)
#             method = 'UTM Zone 52S'
#             logging.info(f"Perhitungan UTM berhasil: {area_sq_m:.2f} m²")
            
#             # Simpan ke database jika MySQL tersedia
#             connection = get_mysql_connection()
#             if connection:
#                 try:
#                     with connection.cursor() as cursor:
#                         insert_sql = """
#                         INSERT INTO polygon_areas (geometry_wkt, area_sq_m, area_sq_km, area_hectare, utm_zone, method, calculated_at)
#                         VALUES (%s, %s, %s, %s, %s, %s, NOW())
#                         """
#                         cursor.execute(insert_sql, (wkt_geometry, area_sq_m, area_sq_km, area_hectare, app.config['UTM_ZONE'], method))
#                         connection.commit()
#                 except Exception as e:
#                     logging.error(f"Error menyimpan ke database: {str(e)}")
#                 finally:
#                     connection.close()
            
#             return jsonify({
#                 'success': True,
#                 'area_sq_m': area_sq_m,
#                 'area_sq_km': area_sq_km,
#                 'area_hectare': area_hectare,
#                 'method': method,
#                 'utm_zone': app.config['UTM_ZONE'],
#                 'geometry_wkt': wkt_geometry
#             })
            
#         except Exception as utm_error:
#             logging.error(f"Error perhitungan UTM: {str(utm_error)}")
            
#             # Priority 2: Coba dengan MySQL
#             mysql_area_m, mysql_area_km, mysql_area_ha, mysql_method = calculate_area_mysql(wkt_geometry)
#             if mysql_area_m is not None:
#                 return jsonify({
#                     'success': True,
#                     'area_sq_m': mysql_area_m,
#                     'area_sq_km': mysql_area_km,
#                     'area_hectare': mysql_area_ha,
#                     'method': mysql_method,
#                     'utm_zone': app.config['UTM_ZONE'],
#                     'geometry_wkt': wkt_geometry
#                 })
            
#             # Priority 3: Fallback ke Shapely (kurang akurat)
#             area_sq_m_fallback = geom.area * 1000000  # Konversi aproksimasi
#             area_sq_km_fallback = area_sq_m_fallback / 1_000_000
#             area_hectare_fallback = area_sq_m_fallback / 10_000
            
#             return jsonify({
#                 'success': True,
#                 'area_sq_m': area_sq_m_fallback,
#                 'area_sq_km': area_sq_km_fallback,
#                 'area_hectare': area_hectare_fallback,
#                 'method': 'Shapely (Fallback)',
#                 'utm_zone': app.config['UTM_ZONE'],
#                 'geometry_wkt': wkt_geometry,
#                 'warning': 'Menggunakan perhitungan fallback, hasil mungkin kurang akurat'
#             })
            
#     except Exception as e:
#         logging.error(f"Error calculating area: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': f'Error dalam perhitungan luas: {str(e)}'
#         }), 500

# if __name__ == '__main__':
#     logging.info("Aplikasi Flask dimulai...")
    
#     # Inisialisasi database
#     logging.info("Memulai inisialisasi database...")
#     if init_database():
#         logging.info("Inisialisasi database berhasil")
#     else:
#         logging.warning("Inisialisasi database gagal, fitur MySQL mungkin tidak berfungsi")
    
#     # Test UTM transformation
#     try:
#         from shapely.geometry import Polygon
#         test_polygon = Polygon([(128.0, -3.6), (128.1, -3.6), (128.1, -3.7), (128.0, -3.7)])
#         area_m, area_km, area_ha = calculate_area_utm(test_polygon)
#         logging.info(f"Test UTM Zone 52S berhasil: {area_m:.2f} m²")
#     except Exception as e:
#         logging.warning(f"Test UTM gagal: {str(e)}")
    
#     app.run(debug=True, host='0.0.0.0', port=5000)