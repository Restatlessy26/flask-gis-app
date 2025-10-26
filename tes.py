from flask import Flask, send_file, request, url_for, render_template_string
from shapely.geometry import Point, Polygon
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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
logging.basicConfig(level=logging.INFO)

def pembersihan_nama_kolom(kolom_nama):
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', kolom_nama)
    return cleaned[:10].upper()

# Route baru untuk halaman info
@app.route('/info')
def info():
    try:
        image_url = url_for('static', filename='Gambar/201874045.jpg', _external=True)
    except RuntimeError:
        image_url = '/static/Gambar/201874045.jpg'

    html_web = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Informasi Detail</title>
        </head>
        <body>
            <h2 style="color:red;font-family:Arial;">Kawasan Rawan Covid-19</h2>
            <p> Kawasan ini memiliki informasi sebagai berikut: </p>
            <ul>
                <li> Bangunan : 311 </li>
                <li> Masyarakat : 727 Jiwa </li>
                <li> Kendaraan : 188 </li>
            </ul>
            <img src="{image_url}" width="250">
            <br><br>
            <a href="/">Kembali ke Peta</a>
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
        style_function=lambda x:{
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

    # Modifikasi html_polygon dengan link ke halaman info
    html_polygon = '''
        <!DOCTYPE html>
        <html>
        <body>
            <p> Untuk informasi selengkapnya : <a href="/info" target="_blank">Klik disini</a> </p>
        </body>
        </html> 
    '''  

    # Tambahkan GeoJSON dengan popup
    geojson_layer = folium.GeoJson(
        gdp_polygon_popup.to_json(),
        style_function=lambda x:{
            'color' : 'black',
            'fillColor' : 'orange',
            'fillOpacity' : 0.6
        }
    ).add_to(folium_peta)

    # Bind popup ke layer
    geojson_layer.add_child(folium.Popup(html_polygon, max_width=300))

    return folium_peta._repr_html_()

if __name__ == '__main__':
    app.run(debug=True)


#     import time

# def animate_line(text, delay=0.05):
#     """Menampilkan teks karakter per karakter dengan jeda."""
#     for c in text:
#         print(c, end='', flush=True)
#         time.sleep(delay)
#     print()

# lyrics = [
#     ("aku mau cari jalan tengah buat kamu apa yang tak bisa?", 0),
#     ("ajak kamu ke angkasa", 0.8),
#     ( "go to the moon kita berdansa", 0.6),
#     ("aku wish u best...", 0.2),
#     ("kamu yang the best...", 0.6),
#     ("kata mamaku...", 0.8),
#     ("masih muda banyak waktu", 0.8)
# ]

# def display_lyrics_with_delay(lyrics_list):
#     for text, initial_delay in lyrics_list:
#         if initial_delay > 0:
#             time.sleep(initial_delay)
#         animate_line(text)
# if __name__ == '__main__':
#     display_lyrics_with_delay(lyrics)
