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
            top: 10px; 
            left: 10px; 
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
            right: 10px !important; 
        }}
        /* Mendorong Draw Control ke bawah agar berada di bawah Zoom Control */
        .leaflet-top.leaflet-right {{
            top: 80px !important; 
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