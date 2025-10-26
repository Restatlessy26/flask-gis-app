from flask import Flask, url_for, send_file, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
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
from shapely.ops import transform
import logging
import re
import pymysql
from pymysql import MySQLError
from pyproj import Transformer, CRS
import uuid
from datetime import datetime
import secrets
import math
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# MENAIKKAN BATAS UKURAN PAYLOAD POST (50 MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

# Konfigurasi dengan environment variables untuk Render
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'gis_db')
app.config['MYSQL_CHARSET'] = os.environ.get('MYSQL_CHARSET', 'utf8mb4')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))
app.config['MYSQL_AUTOCOMMIT'] = True

# Konfigurasi UTM Zone 52S (EPSG:32752) - UNTUK LOKASI ANDA
app.config['UTM_ZONE'] = 'EPSG:32752'

# Konfigurasi SocketIO untuk real-time communication
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)

# Dictionary untuk menyimpan session user
user_sessions = {}

# ====================================================================
# FUNGSI-FUNGSI MULTIUSER YANG DITAMBAHKAN
# ====================================================================

def create_user_session(session_id, user_id, ip_address=None, user_agent=None):
    """Membuat atau memperbarui user session"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return False
            
        with connection.cursor() as cursor:
            sql = """
            INSERT INTO user_sessions (session_id, user_id, ip_address, user_agent, created_at, last_activity)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE 
            last_activity = NOW(),
            ip_address = VALUES(ip_address),
            user_agent = VALUES(user_agent)
            """
            cursor.execute(sql, (session_id, user_id, ip_address, user_agent))
            connection.commit()
            return True
    except Exception as e:
        logging.error(f"Error creating user session: {str(e)}")
        return False
    finally:
        if connection:
            connection.close()

def init_database_multiuser():
    """Membuat database dan tabel untuk multiuser jika belum ada"""
    try:
        # Koneksi tanpa database terlebih dahulu
        connection = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            charset=app.config['MYSQL_CHARSET'],
            port=app.config['MYSQL_PORT']
        )
        
        with connection.cursor() as cursor:
            # Buat database jika belum ada
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config['MYSQL_DB']}")
            cursor.execute(f"USE {app.config['MYSQL_DB']}")
            
            # Buat tabel polygon_areas jika belum ada (dengan kolom user_id dan session_id)
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS polygon_areas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                session_id VARCHAR(255) NOT NULL,
                geometry_wkt TEXT NOT NULL,
                area_sq_m DECIMAL(15, 2) NOT NULL,
                area_sq_km DECIMAL(15, 6) NOT NULL,
                area_hectare DECIMAL(15, 4) NOT NULL,
                utm_zone VARCHAR(10) NOT NULL,
                method VARCHAR(50) NOT NULL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_session_id (session_id)
            )
            """
            cursor.execute(create_table_sql)
            
            # Buat tabel untuk user sessions
            create_sessions_table = """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_last_activity (last_activity)
            )
            """
            cursor.execute(create_sessions_table)

            # Buat tabel untuk GPS tracks
            create_gps_tracks_table = """
            CREATE TABLE IF NOT EXISTS gps_tracks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL,
                session_id VARCHAR(255) NOT NULL,
                track_name VARCHAR(255),
                start_time DATETIME,
                end_time DATETIME,
                duration VARCHAR(50),
                total_distance DECIMAL(10, 2),
                average_speed DECIMAL(6, 2),
                max_speed DECIMAL(6, 2),
                point_count INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                INDEX idx_session_id (session_id)
            )
            """
            cursor.execute(create_gps_tracks_table)
            
            logging.info("Database dan tabel multiuser berhasil diinisialisasi")
        
        connection.commit()
        connection.close()
        return True
        
    except Exception as e:
        logging.error(f"Error inisialisasi database multiuser: {str(e)}")
        logging.info("Aplikasi tetap berjalan tanpa database multiuser")
        return True  # Return True agar aplikasi tetap berjalan

def calculate_area_mysql_multiuser(wkt_geometry, user_id, session_id):
    """Menghitung luas menggunakan MySQL spatial functions dengan info user"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return None, None, None, "MySQL Connection Failed"
            
        with connection.cursor() as cursor:
            # Query untuk menghitung luas dalam meter persegi
            sql = """
            SELECT 
                ST_Area(ST_GeomFromText(%s)) as area_sq_m,
                ST_Area(ST_GeomFromText(%s)) / 1000000 as area_sq_km,
                ST_Area(ST_GeomFromText(%s)) / 10000 as area_hectare
            """
            cursor.execute(sql, (wkt_geometry, wkt_geometry, wkt_geometry))
            result = cursor.fetchone()
            
            if result and result['area_sq_m'] is not None:
                area_sq_m = float(result['area_sq_m'])
                area_sq_km = float(result['area_sq_km'])
                area_hectare = float(result['area_hectare'])
                
                # Simpan hasil perhitungan ke database dengan user info
                insert_sql = """
                INSERT INTO polygon_areas (geometry_wkt, area_sq_m, area_sq_km, area_hectare, utm_zone, method, calculated_at, user_id, session_id)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                """
                cursor.execute(insert_sql, (wkt_geometry, area_sq_m, area_sq_km, area_hectare, app.config['UTM_ZONE'], 'MySQL', user_id, session_id))
                connection.commit()
                
                return area_sq_m, area_sq_km, area_hectare, 'MySQL'
            else:
                return None, None, None, "MySQL Calculation Failed"
                
    except MySQLError as e:
        logging.error(f"MySQL Error: {str(e)}")
        return None, None, None, f"MySQL Error: {str(e)}"
    finally:
        if connection:
            connection.close()

# ====================================================================
# SOCKET.IO EVENT HANDLERS - REAL-TIME MULTIUSER
# ====================================================================

@socketio.on('connect')
def handle_connect():
    """Handle ketika client terhubung"""
    try:
        # Generate unique user ID dan session ID
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        # Simpan ke session Flask
        session['user_id'] = user_id
        session['session_id'] = session_id
        
        # Simpan ke dictionary user_sessions
        user_sessions[session_id] = {
            'user_id': user_id,
            'connected_at': datetime.now(),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        }
        
        # Simpan ke database
        create_user_session(session_id, user_id, request.remote_addr, request.headers.get('User-Agent'))
        
        # Kirim konfirmasi ke client
        emit('connection_established', {
            'user_id': user_id,
            'session_id': session_id,
            'message': 'Connected successfully',
            'connected_users': len(user_sessions)
        })
        
        logging.info(f"User {user_id} connected. Total users: {len(user_sessions)}")
        
    except Exception as e:
        logging.error(f"Error in handle_connect: {str(e)}")
        emit('connection_error', {'error': 'Failed to establish connection'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle ketika client terputus"""
    try:
        session_id = session.get('session_id')
        user_id = session.get('user_id')
        
        if session_id in user_sessions:
            del user_sessions[session_id]
        
        # Broadcast ke semua user tentang perubahan jumlah user
        emit('user_count_update', {
            'connected_users': len(user_sessions)
        }, broadcast=True)
        
        logging.info(f"User {user_id} disconnected. Total users: {len(user_sessions)}")
        
    except Exception as e:
        logging.error(f"Error in handle_disconnect: {str(e)}")

@socketio.on('user_activity')
def handle_user_activity(data):
    """Handle aktivitas user untuk tracking"""
    try:
        session_id = session.get('session_id')
        activity_type = data.get('type', 'unknown')
        
        # Update last activity di database
        connection = get_mysql_connection()
        if connection:
            with connection.cursor() as cursor:
                sql = "UPDATE user_sessions SET last_activity = NOW() WHERE session_id = %s"
                cursor.execute(sql, (session_id,))
                connection.commit()
            connection.close()
            
        logging.debug(f"User activity: {activity_type} from session {session_id}")
        
    except Exception as e:
        logging.error(f"Error in handle_user_activity: {str(e)}")

@socketio.on('collaborative_drawing')
def handle_collaborative_drawing(data):
    """Handle collaborative drawing untuk multi-user real-time"""
    try:
        # Track user activity
        handle_user_activity({'type': 'collaborative_drawing'})
        
        # Broadcast drawing ke semua user lain
        emit('collaborative_drawing_update', {
            'geometry': data.get('geometry'),
            'type': data.get('type'),
            'style': data.get('style', {}),
            'user_id': session.get('user_id'),
            'timestamp': datetime.now().isoformat()
        }, broadcast=True, include_self=False)
        
    except Exception as e:
        logging.error(f"Error in handle_collaborative_drawing: {str(e)}")

@socketio.on('area_calculation_request')
def handle_area_calculation_request(data):
    """Handle request perhitungan luas dari client via Socket.IO"""
    try:
        # Track user activity
        handle_user_activity({'type': 'area_calculation'})
        
        geojson_data = data.get('geojson_data')
        user_id = session.get('user_id')
        session_id = session.get('session_id')
        
        if not geojson_data:
            emit('area_calculation_result', {
                'success': False,
                'error': 'No geometry data provided'
            })
            return
        
        # Proses perhitungan luas
        geom = shape(geojson_data['geometry'])
        wkt_geometry = geom.wkt
        
        # Priority 1: Hitung dengan UTM Zone 52S
        try:
            area_sq_m, area_sq_km, area_hectare = calculate_area_utm(geom)
            method = 'UTM Zone 52S'
            
            # Simpan ke database dengan user info
            connection = get_mysql_connection()
            if connection:
                with connection.cursor() as cursor:
                    insert_sql = """
                    INSERT INTO polygon_areas (geometry_wkt, area_sq_m, area_sq_km, area_hectare, utm_zone, method, calculated_at, user_id, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                    """
                    cursor.execute(insert_sql, (wkt_geometry, area_sq_m, area_sq_km, area_hectare, app.config['UTM_ZONE'], method, user_id, session_id))
                    connection.commit()
                connection.close()
            
            # Kirim hasil ke client
            emit('area_calculation_result', {
                'success': True,
                'area_sq_m': area_sq_m,
                'area_sq_km': area_sq_km,
                'area_hectare': area_hectare,
                'method': method,
                'utm_zone': app.config['UTM_ZONE'],
                'calculation_id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as utm_error:
            logging.error(f"UTM calculation error: {str(utm_error)}")
            
            # Priority 2: Coba dengan MySQL
            mysql_area_m, mysql_area_km, mysql_area_ha, mysql_method = calculate_area_mysql_multiuser(wkt_geometry, user_id, session_id)
            if mysql_area_m is not None:
                emit('area_calculation_result', {
                    'success': True,
                    'area_sq_m': mysql_area_m,
                    'area_sq_km': mysql_area_km,
                    'area_hectare': mysql_area_ha,
                    'method': mysql_method,
                    'utm_zone': app.config['UTM_ZONE'],
                    'calculation_id': str(uuid.uuid4()),
                    'timestamp': datetime.now().isoformat()
                })
                return
            
            # Priority 3: Fallback ke Shapely (kurang akurat)
            area_sq_m_fallback = geom.area * 1000000  # Konversi aproksimasi
            area_sq_km_fallback = area_sq_m_fallback / 1_000_000
            area_hectare_fallback = area_sq_m_fallback / 10_000
            
            emit('area_calculation_result', {
                'success': True,
                'area_sq_m': area_sq_m_fallback,
                'area_sq_km': area_sq_km_fallback,
                'area_hectare': area_hectare_fallback,
                'method': 'Shapely (Fallback)',
                'utm_zone': app.config['UTM_ZONE'],
                'calculation_id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'warning': 'Menggunakan perhitungan fallback, hasil mungkin kurang akurat'
            })
            
    except Exception as e:
        logging.error(f"Error in handle_area_calculation_request: {str(e)}")
        emit('area_calculation_result', {
            'success': False,
            'error': f'Calculation error: {str(e)}'
        })

# ====================================================================
# ENDPOINT API UNTUK MULTIUSER
# ====================================================================

@app.route('/api/user_stats')
def get_user_stats():
    """Endpoint untuk mendapatkan statistik user"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
            
        with connection.cursor() as cursor:
            # Total users
            cursor.execute("SELECT COUNT(DISTINCT user_id) as total_users FROM user_sessions")
            total_users = cursor.fetchone()['total_users']
            
            # Active users (last 5 minutes)
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) as active_users 
                FROM user_sessions 
                WHERE last_activity > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
            """)
            active_users = cursor.fetchone()['active_users']
            
            # Total calculations
            cursor.execute("SELECT COUNT(*) as total_calculations FROM polygon_areas")
            total_calculations = cursor.fetchone()['total_calculations']
            
            # Recent activity
            cursor.execute("""
                SELECT user_id, MAX(last_activity) as last_activity
                FROM user_sessions 
                GROUP BY user_id 
                ORDER BY last_activity DESC 
                LIMIT 10
            """)
            recent_users = cursor.fetchall()
            
        connection.close()
        
        return jsonify({
            'total_users': total_users,
            'active_users': active_users,
            'total_calculations': total_calculations,
            'recent_users': recent_users,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting user stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ====================================================================
# HEALTH CHECK ENDPOINT UNTUK RENDER
# ====================================================================

@app.route('/health')
def health_check():
    """Endpoint untuk health check Render"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': 'connected' if get_mysql_connection() else 'disconnected'
    })

# ====================================================================
# KODE ASLI ANDA - DIPERBAIKI DENGAN FALLBACK
# ====================================================================

# Fungsi untuk koneksi database MySQL dengan fallback
def get_mysql_connection():
    """Membuat koneksi ke database MySQL dengan penanganan error dan fallback"""
    try:
        connection = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            charset=app.config['MYSQL_CHARSET'],
            port=app.config['MYSQL_PORT'],
            autocommit=app.config['MYSQL_AUTOCOMMIT'],
            cursorclass=pymysql.cursors.DictCursor
        )
        logging.info("Koneksi MySQL berhasil dibuat")
        return connection
    except MySQLError as e:
        logging.error(f"MySQL Connection Error: {str(e)}")
        logging.info("Menggunakan mode tanpa database - fitur tertentu akan terbatas")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in MySQL connection: {str(e)}")
        logging.info("Menggunakan mode tanpa database - fitur tertentu akan terbatas")
        return None

# Fungsi untuk membuat database dan tabel jika belum ada dengan fallback
def init_database():
    """Membuat database dan tabel jika belum ada"""
    try:
        # Koneksi tanpa database terlebih dahulu
        connection = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            charset=app.config['MYSQL_CHARSET'],
            port=app.config['MYSQL_PORT']
        )
        
        with connection.cursor() as cursor:
            # Buat database jika belum ada
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {app.config['MYSQL_DB']}")
            cursor.execute(f"USE {app.config['MYSQL_DB']}")
            
            # Buat tabel jika belum ada
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS polygon_areas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                geometry_wkt TEXT NOT NULL,
                area_sq_m DECIMAL(15, 2) NOT NULL,
                area_sq_km DECIMAL(15, 6) NOT NULL,
                area_hectare DECIMAL(15, 4) NOT NULL,
                utm_zone VARCHAR(10) NOT NULL,
                method VARCHAR(50) NOT NULL,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table_sql)
            logging.info("Database dan tabel berhasil diinisialisasi")
        
        connection.commit()
        connection.close()
        return True
        
    except Exception as e:
        logging.error(f"Error inisialisasi database: {str(e)}")
        logging.info("Aplikasi tetap berjalan tanpa database")
        return True  # Return True agar aplikasi tetap berjalan

# Fungsi untuk menghitung luas dengan UTM Zone 52S
def calculate_area_utm(geometry):
    """Menghitung luas polygon menggunakan UTM Zone 52S (EPSG:32752)"""
    try:
        # Buat transformer dari WGS84 (EPSG:4326) ke UTM Zone 52S (EPSG:32752)
        transformer = Transformer.from_crs("EPSG:4326", app.config['UTM_ZONE'], always_xy=True)
        
        # Transformasi geometry ke UTM
        geometry_utm = transform(transformer.transform, geometry)
        
        # Hitung luas dalam meter persegi
        area_sq_m = geometry_utm.area
        
        # Konversi ke unit lainnya
        area_sq_km = area_sq_m / 1_000_000
        area_hectare = area_sq_m / 10_000
        
        return area_sq_m, area_sq_km, area_hectare
        
    except Exception as e:
        logging.error(f"Error dalam perhitungan UTM: {str(e)}")
        raise e

# Fungsi untuk menghitung luas dengan MySQL spatial functions
def calculate_area_mysql(wkt_geometry):
    """Menghitung luas menggunakan MySQL spatial functions"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return None, None, None, "MySQL Connection Failed"
            
        with connection.cursor() as cursor:
            # Query untuk menghitung luas dalam meter persegi
            sql = """
            SELECT 
                ST_Area(ST_GeomFromText(%s)) as area_sq_m,
                ST_Area(ST_GeomFromText(%s)) / 1000000 as area_sq_km,
                ST_Area(ST_GeomFromText(%s)) / 10000 as area_hectare
            """
            cursor.execute(sql, (wkt_geometry, wkt_geometry, wkt_geometry))
            result = cursor.fetchone()
            
            if result and result['area_sq_m'] is not None:
                area_sq_m = float(result['area_sq_m'])
                area_sq_km = float(result['area_sq_km'])
                area_hectare = float(result['area_hectare'])
                
                # Simpan hasil perhitungan ke database
                insert_sql = """
                INSERT INTO polygon_areas (geometry_wkt, area_sq_m, area_sq_km, area_hectare, utm_zone, method, calculated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(insert_sql, (wkt_geometry, area_sq_m, area_sq_km, area_hectare, app.config['UTM_ZONE'], 'MySQL'))
                connection.commit()
                
                return area_sq_m, area_sq_km, area_hectare, 'MySQL'
            else:
                return None, None, None, "MySQL Calculation Failed"
                
    except MySQLError as e:
        logging.error(f"MySQL Error: {str(e)}")
        return None, None, None, f"MySQL Error: {str(e)}"
    finally:
        if connection:
            connection.close()

# Fungsi pembersihan nama kolom untuk Shapefile
def clean_column_name(col_name):
    """Batasi panjang kolom dan hapus karakter ilegal untuk Shapefile (DBF)."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', col_name)
    return cleaned[:10].upper()

# ====================================================================
# ENDPOINT BARU UNTUK GPS TRACKING
# ====================================================================

@app.route('/export_gps_track', methods=['POST'])
def export_gps_track():
    """Mengekspor track GPS perjalanan ke Shapefile"""
    logging.info("=== Mulai Ekspor Track GPS Perjalanan ===")
    
    try:
        data = request.get_json()
        track_data = data.get('track_data')
        user_id = session.get('user_id', 'unknown')
        
        if not track_data:
            return jsonify({'success': False, 'error': 'Tidak ada data track yang diterima'}), 400
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Buat GeoJSON dari track data
            features = []
            
            # LineString untuk track perjalanan
            coordinates = []
            timestamps = []
            
            for point in track_data.get('points', []):
                coordinates.append([point['lng'], point['lat']])
                timestamps.append(point['timestamp'])
            
            if len(coordinates) < 2:
                return jsonify({'success': False, 'error': 'Data track tidak cukup'}), 400
            
            # Hitung total jarak menggunakan Haversine formula
            total_distance = 0
            for i in range(1, len(coordinates)):
                lon1, lat1 = coordinates[i-1]
                lon2, lat2 = coordinates[i]
                
                R = 6371000  # Radius bumi dalam meter
                dLat = math.radians(lat2 - lat1)
                dLon = math.radians(lon2 - lon1)
                a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2) * math.sin(dLon/2)
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = R * c
                
                total_distance += distance
            
            # Buat feature LineString
            line_feature = {
                "type": "Feature",
                "properties": {
                    "ID_TRACK": 1,
                    "USER_ID": user_id,
                    "START_TIME": track_data.get('start_time', ''),
                    "END_TIME": track_data.get('end_time', ''),
                    "DURATION": track_data.get('duration', ''),
                    "TOTAL_DIST": round(total_distance, 2),
                    "POINT_COUNT": len(coordinates),
                    "AVG_SPEED": track_data.get('average_speed', 0),
                    "MAX_SPEED": track_data.get('max_speed', 0)
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                }
            }
            features.append(line_feature)
            
            # Buat Points untuk setiap titik track
            for i, (coord, timestamp) in enumerate(zip(coordinates, timestamps)):
                point_feature = {
                    "type": "Feature",
                    "properties": {
                        "POINT_ID": i + 1,
                        "USER_ID": user_id,
                        "TIMESTAMP": timestamp,
                        "SEQUENCE": i + 1,
                        "LATITUDE": coord[1],
                        "LONGITUDE": coord[0]
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": coord
                    }
                }
                features.append(point_feature)
            
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            
            # Konversi ke GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(geojson['features'], crs='EPSG:4326')
            
            # Pisahkan points dan lines
            gdf_points = gdf[gdf.geometry.type == 'Point']
            gdf_lines = gdf[gdf.geometry.type == 'LineString']
            
            files_created = []
            
            # Export lines
            if not gdf_lines.empty:
                lines_path = os.path.join(temp_dir, 'gps_track_line.shp')
                gdf_lines.to_file(lines_path, driver='ESRI Shapefile', encoding='utf-8')
                files_created.append('gps_track_line')
            
            # Export points
            if not gdf_points.empty:
                points_path = os.path.join(temp_dir, 'gps_track_points.shp')
                gdf_points.to_file(points_path, driver='ESRI Shapefile', encoding='utf-8')
                files_created.append('gps_track_points')
            
            if not files_created:
                return jsonify({'success': False, 'error': 'Tidak ada data yang dapat diekspor'}), 400
            
            # Buat ZIP file
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zf.write(file_path, arcname)
            
            zip_buffer.seek(0)
            
            # Simpan ke database
            connection = get_mysql_connection()
            if connection:
                with connection.cursor() as cursor:
                    insert_sql = """
                    INSERT INTO gps_tracks (user_id, session_id, track_name, start_time, end_time, duration, total_distance, average_speed, max_speed, point_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        user_id,
                        session.get('session_id', 'unknown'),
                        f"Track_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        track_data.get('start_time'),
                        track_data.get('end_time'),
                        track_data.get('duration'),
                        total_distance,
                        track_data.get('average_speed', 0),
                        track_data.get('max_speed', 0),
                        len(coordinates)
                    ))
                    connection.commit()
                connection.close()
            
            # Log aktivitas
            logging.info(f"User {user_id} berhasil export GPS track dengan {len(coordinates)} points")
            
            return send_file(
                zip_buffer,
                download_name=f'gps_track_{user_id[:8]}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
                mimetype='application/zip',
                as_attachment=True
            )
            
        except Exception as e:
            logging.error(f"Error processing GPS track: {str(e)}")
            return jsonify({'success': False, 'error': f'Error memproses track: {str(e)}'}), 500
            
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except Exception as e:
        logging.error(f"Fatal error in GPS track export: {str(e)}")
        return jsonify({'success': False, 'error': f'Error fatal: {str(e)}'}), 500

# ====================================================================
# FUNGSI INDEX (MAP INITIALIZATION) - DIPERBAIKI DENGAN HTML/JS LENGKAP
# ====================================================================
@app.route('/')
def index():
    # Generate session ID jika belum ada
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['session_id'] = str(uuid.uuid4())
    
    kordinat_awal = [-3.675, 128.220]
    folium_peta = folium.Map(location=kordinat_awal, zoom_start=15, zoom_control=True) 
    map_name = folium_peta.get_name()

    # --- Data Statis (Polygon, TileLayer) ---
    # PERBAIKAN: HAPUS MARKER STATIS YANG MENYEBABKAN DUPLIKASI
    x_polygon = [128.199513, 128.187740, 128.188359, 128.200797]
    y_polygon = [-3.677841, -3.678988, -3.690433, -3.687038]
    kordinat_polygon = list(zip(x_polygon, y_polygon))
    polygon_akhir = Polygon(kordinat_polygon)
    gdp_polygon = gpd.GeoDataFrame(geometry=[polygon_akhir], crs='EPSG:4326')

    x_radius = 128.180946
    y_radius = -3.698711
    kordinat_radius = Point(x_radius, y_radius)
    gdp_radius = gpd.GeoDataFrame(geometry=[kordinat_radius], crs='EPSG:4326')

    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        attr='Kartendaten: © OpenStreetMap-Mitwirkante, SRTM | Kartendarstellung: © OpenTopoMap (CC-BY-SA)',
        overlay=False,
        name='TopoMap',
        control=True
    ).add_to(folium_peta)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri, Maxar, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA FSA, USGS, Aerogrid, IGN, IGP, and the GIS User Community',
        overlay=False,
        name='ESRI Satelite',
        control=True
    ).add_to(folium_peta)
    
    try:
        gambar = url_for('static', filename='Gambar/217.jpg', _external=True) 
    except RuntimeError:
        gambar = 'static/Gambar/217.jpg'

    html_polygon = f'''
        <!DOCTYPE html>
        <html>
        <body>
            <h2 style="color:black;font-family:Arial;">Kawasan Bebas Kejahatan</h2>
            <img src="{gambar}" width="250">
        </body>
        </html>
        '''
    
    html_radius = '''
        <!DOCTYPE html>
        <html>
        <body>
            <h3 style="color:red;font-family:Arial;">Kawasan Rawan Covid-19</h3>
        </body>
        </html>
        '''
        
    frame_polygon = folium.IFrame(html=html_polygon, width=300, height=250)
    popup_polygon = folium.Popup(frame_polygon, max_width=2650)
    folium.GeoJson(gdp_polygon.to_json(), popup=popup_polygon, style_function=lambda x:{'fillColor': 'Blue', 'color': 'red', 'fillOpacity': 0.3}).add_to(folium_peta)

    frame_radius = folium.IFrame(html=html_radius, width=300, height=250)
    popup_radius = folium.Popup(frame_radius, max_width=2650)
    folium.GeoJson(gdp_radius.to_json(), popup=popup_radius, marker=folium.Circle(color='Black', fillColor='Blue', fillOpacity=0.4, radius=250)).add_to(folium_peta)

    # FeatureGroup untuk menyimpan hasil gambar pengguna
    drawn_items = folium.FeatureGroup(name="Drawn Items").add_to(folium_peta)
    drawn_items_name = drawn_items.get_name()
    
    # FeatureGroup untuk highlight polygon yang dipilih
    highlight_group = folium.FeatureGroup(name="Highlighted Polygon").add_to(folium_peta)
    highlight_group_name = highlight_group.get_name()
    
    # FeatureGroup untuk collaborative drawings dari user lain
    collaborative_group = folium.FeatureGroup(name="Collaborative Drawings").add_to(folium_peta)
    collaborative_group_name = collaborative_group.get_name()
    
    # FeatureGroup untuk GPS tracks
    gps_tracks_group = folium.FeatureGroup(name="GPS Tracks").add_to(folium_peta)
    gps_tracks_group_name = gps_tracks_group.get_name()
    
    # Draw Control di kanan atas
    Draw(
        export=False, 
        feature_group=drawn_items, 
        position='topright', 
        draw_options={
            'polyline': {'repeatMode': True},
            'rectangle': {'repeatMode': True},
            'circle': {'repeatMode': True},
            'marker': {'repeatMode': True},
            'polygon': {'allowIntersection': False, 'drawError': {'color': 'red', 'message': 'Error123'}, 'shapeOptions': {'color': 'red'}, 'repeatMode': True}
        },
        edit_options={'edit': True, 'remove': True}
    ).add_to(folium_peta)
    
    # --- Penambahan Library Turf.js (Perhitungan Geometri) ---
    turf_js_cdn = '<script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>'
    folium_peta.get_root().header.add_child(folium.Element(turf_js_cdn))
    
    # --- Penambahan Library Socket.IO ---
    socketio_js = '<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>'
    folium_peta.get_root().header.add_child(folium.Element(socketio_js))

    # HTML/JS code YANG LENGKAP dengan menu file, edit, dll.
    html_js = """
    <style>
        /* Style untuk menu bar */
        .menu-bar {
            position: absolute;
            top: 10px;
            left: 50px;
            z-index: 1000;
            background: white;
            padding: 5px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        
        .menu-item {
            display: inline-block;
            position: relative;
        }
        
        .menu-button {
            background: none;
            border: none;
            padding: 8px 15px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .menu-button:hover {
            background-color: #f0f0f0;
        }
        
        .dropdown-content {
            display: none;
            position: absolute;
            background-color: white;
            min-width: 160px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            z-index: 1001;
        }
        
        .dropdown-content a {
            color: black;
            padding: 8px 12px;
            text-decoration: none;
            display: block;
            font-size: 13px;
        }
        
        .dropdown-content a:hover {
            background-color: #f0f0f0;
        }
        
        .menu-item:hover .dropdown-content {
            display: block;
        }
        
        /* Style untuk info panel */
        .info-panel {
            position: absolute;
            top: 60px;
            left: 50px;
            z-index: 999;
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            max-width: 300px;
        }
        
        .user-info {
            font-size: 12px;
            color: #666;
            margin-bottom: 5px;
        }
        
        .area-result {
            background: #e8f5e8;
            padding: 8px;
            border-radius: 3px;
            margin: 5px 0;
            font-size: 13px;
        }
        
        /* Style untuk GPS tracking */
        .gps-panel {
            position: absolute;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            width: 300px;
        }
        
        .gps-controls {
            margin: 10px 0;
        }
        
        .gps-button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 8px 15px;
            margin: 5px;
            border-radius: 3px;
            cursor: pointer;
        }
        
        .gps-button.stop {
            background: #f44336;
        }
        
        .gps-stats {
            font-size: 12px;
            color: #666;
        }
    </style>

    <div class="menu-bar">
        <div class="menu-item">
            <button class="menu-button">File</button>
            <div class="dropdown-content">
                <a href="#" onclick="exportToGeoJSON()">Export GeoJSON</a>
                <a href="#" onclick="exportToSHP()">Export Shapefile</a>
                <a href="#" onclick="importData()">Import Data</a>
                <a href="#" onclick="clearMap()">Clear Map</a>
            </div>
        </div>
        
        <div class="menu-item">
            <button class="menu-button">Edit</button>
            <div class="dropdown-content">
                <a href="#" onclick="undoLast()">Undo Last</a>
                <a href="#" onclick="redoLast()">Redo Last</a>
                <a href="#" onclick="selectAll()">Select All</a>
                <a href="#" onclick="deselectAll()">Deselect All</a>
            </div>
        </div>
        
        <div class="menu-item">
            <button class="menu-button">View</button>
            <div class="dropdown-content">
                <a href="#" onclick="toggleLayer('OpenStreetMap')">OSM Base Map</a>
                <a href="#" onclick="toggleLayer('TopoMap')">Topographic Map</a>
                <a href="#" onclick="toggleLayer('ESRI Satelite')">Satellite Imagery</a>
                <a href="#" onclick="toggleFullscreen()">Fullscreen Mode</a>
            </div>
        </div>
        
        <div class="menu-item">
            <button class="menu-button">Tools</button>
            <div class="dropdown-content">
                <a href="#" onclick="measureArea()">Measure Area</a>
                <a href="#" onclick="measureDistance()">Measure Distance</a>
                <a href="#" onclick="startGPSTracking()">GPS Tracking</a>
                <a href="#" onclick="showCoordinates()">Get Coordinates</a>
            </div>
        </div>
        
        <div class="menu-item">
            <button class="menu-button">Help</button>
            <div class="dropdown-content">
                <a href="#" onclick="showAbout()">About</a>
                <a href="#" onclick="showUserGuide()">User Guide</a>
                <a href="#" onclick="showShortcuts()">Keyboard Shortcuts</a>
            </div>
        </div>
    </div>

    <div class="info-panel">
        <div class="user-info">
            User: <span id="user-id">Loading...</span> | 
            Session: <span id="session-id">Loading...</span>
        </div>
        <div id="area-result" class="area-result" style="display: none;">
            <!-- Hasil perhitungan luas akan ditampilkan di sini -->
        </div>
        <div id="connection-status" style="font-size: 11px; color: green;">
            ● Connected
        </div>
    </div>

    <div class="gps-panel" id="gps-panel" style="display: none;">
        <h4>GPS Tracking</h4>
        <div class="gps-controls">
            <button class="gps-button" onclick="startTracking()">Start Tracking</button>
            <button class="gps-button stop" onclick="stopTracking()">Stop Tracking</button>
            <button class="gps-button" onclick="exportTrack()">Export Track</button>
        </div>
        <div class="gps-stats">
            <div>Points: <span id="gps-points">0</span></div>
            <div>Distance: <span id="gps-distance">0</span> meters</div>
            <div>Duration: <span id="gps-duration">00:00:00</span></div>
            <div>Speed: <span id="gps-speed">0</span> km/h</div>
        </div>
    </div>

    <script>
        // Socket.IO Connection
        const socket = io();
        
        // Variabel global
        let currentUser = null;
        let currentSession = null;
        let drawnItems = [];
        let gpsTrack = {
            points: [],
            startTime: null,
            isTracking: false
        };
        
        // Socket event handlers
        socket.on('connection_established', function(data) {
            currentUser = data.user_id;
            currentSession = data.session_id;
            
            document.getElementById('user-id').textContent = currentUser.substring(0, 8) + '...';
            document.getElementById('session-id').textContent = currentSession.substring(0, 8) + '...';
            
            console.log('Connected as user:', currentUser);
        });
        
        socket.on('user_count_update', function(data) {
            console.log('Connected users:', data.connected_users);
        });
        
        socket.on('collaborative_drawing_update', function(data) {
            // Handle collaborative drawing from other users
            addCollaborativeDrawing(data.geometry, data.type, data.style, data.user_id);
        });
        
        socket.on('area_calculation_result', function(data) {
            if (data.success) {
                showAreaResult(data);
            } else {
                alert('Error calculating area: ' + data.error);
            }
        });
        
        // Fungsi menu File
        function exportToGeoJSON() {
            // Implementasi export GeoJSON
            alert('Export to GeoJSON clicked');
        }
        
        function exportToSHP() {
            // Implementasi export Shapefile
            alert('Export to Shapefile clicked');
        }
        
        function importData() {
            // Implementasi import data
            alert('Import Data clicked');
        }
        
        function clearMap() {
            if (confirm('Are you sure you want to clear all drawings?')) {
                // Clear all drawn items
                drawnItems = [];
                updateMap();
            }
        }
        
        // Fungsi menu Edit
        function undoLast() {
            // Implementasi undo
            alert('Undo Last clicked');
        }
        
        function redoLast() {
            // Implementasi redo
            alert('Redo Last clicked');
        }
        
        function selectAll() {
            // Implementasi select all
            alert('Select All clicked');
        }
        
        function deselectAll() {
            // Implementasi deselect all
            alert('Deselect All clicked');
        }
        
        // Fungsi menu View
        function toggleLayer(layerName) {
            // Implementasi toggle layer
            alert('Toggle layer: ' + layerName);
        }
        
        function toggleFullscreen() {
            // Implementasi fullscreen
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }
            }
        }
        
        // Fungsi menu Tools
        function measureArea() {
            // Implementasi measure area
            alert('Measure Area tool activated');
        }
        
        function measureDistance() {
            // Implementasi measure distance
            alert('Measure Distance tool activated');
        }
        
        function startGPSTracking() {
            // Tampilkan panel GPS
            document.getElementById('gps-panel').style.display = 'block';
            alert('GPS Tracking panel opened');
        }
        
        function showCoordinates() {
            // Implementasi show coordinates
            alert('Get Coordinates tool activated');
        }
        
        // Fungsi menu Help
        function showAbout() {
            alert('GIS Web Application v2.0\\nMulti-user Collaborative Mapping\\n© 2024');
        }
        
        function showUserGuide() {
            alert('User Guide will be displayed here');
        }
        
        function showShortcuts() {
            alert('Keyboard Shortcuts:\\nCtrl+S - Save\\nCtrl+Z - Undo\\nCtrl+Y - Redo');
        }
        
        // Fungsi GPS Tracking
        function startTracking() {
            if (!gpsTrack.isTracking) {
                gpsTrack.isTracking = true;
                gpsTrack.startTime = new Date();
                gpsTrack.points = [];
                
                if (navigator.geolocation) {
                    navigator.geolocation.watchPosition(
                        function(position) {
                            const point = {
                                lat: position.coords.latitude,
                                lng: position.coords.longitude,
                                timestamp: new Date().toISOString(),
                                speed: position.coords.speed || 0
                            };
                            
                            gpsTrack.points.push(point);
                            updateGPSStats();
                            
                            // Add point to map
                            addGPSTrackPoint(point);
                        },
                        function(error) {
                            console.error('GPS Error:', error);
                            alert('GPS Error: ' + error.message);
                        },
                        {
                            enableHighAccuracy: true,
                            timeout: 5000,
                            maximumAge: 0
                        }
                    );
                } else {
                    alert('Geolocation is not supported by this browser.');
                }
            }
        }
        
        function stopTracking() {
            gpsTrack.isTracking = false;
            alert('GPS Tracking stopped. Total points: ' + gpsTrack.points.length);
        }
        
        function exportTrack() {
            if (gpsTrack.points.length === 0) {
                alert('No GPS track data to export');
                return;
            }
            
            // Kirim data track ke server untuk di-export
            fetch('/export_gps_track', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    track_data: {
                        points: gpsTrack.points,
                        start_time: gpsTrack.startTime,
                        end_time: new Date(),
                        duration: calculateDuration(gpsTrack.startTime, new Date()),
                        average_speed: calculateAverageSpeed(),
                        max_speed: calculateMaxSpeed()
                    }
                })
            })
            .then(response => response.blob())
            .then(blob => {
                // Download file
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = 'gps_track_' + currentUser + '.zip';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            })
            .catch(error => {
                console.error('Export error:', error);
                alert('Error exporting GPS track');
            });
        }
        
        function updateGPSStats() {
            document.getElementById('gps-points').textContent = gpsTrack.points.length;
            document.getElementById('gps-distance').textContent = calculateTotalDistance().toFixed(2);
            document.getElementById('gps-duration').textContent = calculateDuration(gpsTrack.startTime, new Date());
            document.getElementById('gps-speed').textContent = (calculateAverageSpeed() || 0).toFixed(2);
        }
        
        function calculateTotalDistance() {
            // Simplified distance calculation
            return gpsTrack.points.length * 10; // Placeholder
        }
        
        function calculateDuration(start, end) {
            const diff = Math.floor((end - start) / 1000);
            const hours = Math.floor(diff / 3600);
            const minutes = Math.floor((diff % 3600) / 60);
            const seconds = diff % 60;
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        
        function calculateAverageSpeed() {
            return gpsTrack.points.reduce((sum, point) => sum + (point.speed || 0), 0) / gpsTrack.points.length;
        }
        
        function calculateMaxSpeed() {
            return Math.max(...gpsTrack.points.map(point => point.speed || 0));
        }
        
        // Fungsi bantuan
        function addCollaborativeDrawing(geometry, type, style, userId) {
            // Add collaborative drawing to map
            console.log('Adding collaborative drawing from user:', userId);
        }
        
        function addGPSTrackPoint(point) {
            // Add GPS point to map
            console.log('Adding GPS point:', point);
        }
        
        function showAreaResult(data) {
            const areaDiv = document.getElementById('area-result');
            areaDiv.innerHTML = `
                <strong>Area Calculation Result:</strong><br>
                ${data.area_sq_m.toFixed(2)} m²<br>
                ${data.area_sq_km.toFixed(6)} km²<br>
                ${data.area_hectare.toFixed(4)} hectares<br>
                <small>Method: ${data.method}</small>
            `;
            areaDiv.style.display = 'block';
        }
        
        function updateMap() {
            // Update map dengan data terbaru
            console.log('Updating map with', drawnItems.length, 'items');
        }
        
        // Track user activity
        setInterval(() => {
            socket.emit('user_activity', { type: 'active' });
        }, 30000);
    </script>
    """
    
    folium_peta.get_root().html.add_child(folium.Element(html_js))
    folium.LayerControl(position='bottomright').add_to(folium_peta) 
    return folium_peta.get_root().render()

# --------------------------------------------------------------------------------------
# Endpoint Export GeoJSON
# --------------------------------------------------------------------------------------
@app.route('/export_to_geojson', methods=['POST'])
def export_to_geojson():
    logging.info("=== Mulai Proses Export GeoJSON ===")
    geojson_str = request.form.get('geojson_data')
    user_id = session.get('user_id', 'unknown')
    
    if not geojson_str:
        return "Tidak ada data GeoJSON yang diterima.", 400 
    
    geojson_buffer = io.BytesIO(geojson_str.encode('utf-8'))
    geojson_buffer.seek(0)
    
    # Log aktivitas export
    logging.info(f"User {user_id} melakukan export GeoJSON")
    
    return send_file(
        geojson_buffer,
        download_name=f'peta_digambar_{user_id[:8]}.geojson',
        mimetype='application/json',
        as_attachment=True
    )

# --------------------------------------------------------------------------------------
# Endpoint Export SHP
# --------------------------------------------------------------------------------------
@app.route('/export_to_shp', methods=['POST'])
def export_to_shp():
    logging.info("=== Mulai Proses Export SHP ===")
    geojson_str = request.form.get('geojson_data')
    user_id = session.get('user_id', 'unknown')

    if not geojson_str:
        logging.error("tidak ada data GeoJSON yang diterima")
        return "Tidak ada data GeoJSON yang diterima.", 400 
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        geojson_data = json.loads(geojson_str)
        
        if not geojson_data.get('features'):
            return "Tidak ada data fitur untuk diekspor.", 400

        valid_features = []
        for i, feature in enumerate(geojson_data['features']):
            try:
                if not feature.get('geometry'):
                    continue
                    
                original_props = feature.get('properties', {})
                geom_shape = shape(feature['geometry'])
                
                is_folium_circle = 'radius' in original_props and geom_shape.geom_type == 'Polygon'
                
                if is_folium_circle:
                    centroid = geom_shape.centroid
                    
                    new_feature = {
                        "type": "Feature",
                        "geometry": centroid.__geo_interface__,
                        "properties": original_props.copy() 
                    }
                    
                    new_feature['properties']['RADIUS'] = new_feature['properties'].pop('radius')
                    new_feature['properties']['TIPE_GEOM'] = 'Point' 
                    new_feature['properties']['TIPE_ASAL'] = 'Circle'
                    new_feature['properties']['USER_ID'] = user_id
                    
                    new_feature['properties'].pop('shape', None)
                    new_feature['properties'].pop('_leaflet_id', None)

                    valid_features.append(new_feature)

                else:
                    geom = geom_shape
                    
                    if not geom.is_valid:
                        geom = make_valid(geom)
                    
                    if geom.geom_type == 'GeometryCollection':
                        continue

                    if 'properties' not in feature or feature['properties'] is None:
                        feature['properties'] = {}
                    
                    feature['properties']['TIPE_GEOM'] = geom.geom_type 
                    feature['properties']['TIPE_ASAL'] = feature['properties'].pop('shape', 'Draw') 
                    feature['properties']['USER_ID'] = user_id
                    feature['properties'].pop('_leaflet_id', None)

                    feature['geometry'] = geom.__geo_interface__
                    valid_features.append(feature)
                
                valid_features[-1]['properties']['ID_FITUR'] = i + 1 
                
            except Exception as e:
                logging.error(f"Error processing feature {i}: {str(e)}")
                continue

        if not valid_features:
            return "Tidak ada geometri valid yang dapat diekspor.", 400
        
        gdf_all = gpd.GeoDataFrame.from_features(valid_features, crs='EPSG:4326')
        
        cleaned_columns = {}
        for col in gdf_all.columns:
            if col == 'geometry':
                cleaned_columns[col] = col
            else:
                cleaned_columns[col] = clean_column_name(col)
        
        gdf_all.rename(columns=cleaned_columns, inplace=True)
        gdf_all = gdf_all.set_geometry('geometry')
        
        gdf_points = gdf_all[gdf_all.geometry.type.isin(['Point'])]
        gdf_lines = gdf_all[gdf_all.geometry.type.isin(['LineString', 'MultiLineString'])]
        gdf_polygons = gdf_all[gdf_all.geometry.type.isin(['Polygon', 'MultiPolygon'])]

        files_created = []
        
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
            return "Tidak ada data yang dapat diekspor ke Shapefile.", 400

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)

        zip_buffer.seek(0)

        # Log aktivitas export
        logging.info(f"User {user_id} berhasil export SHP dengan {len(valid_features)} features")

        return send_file(
            zip_buffer,
            download_name=f'peta_digambar_{user_id[:8]}.zip',
            mimetype='application/zip',
            as_attachment=True
        )

    except json.JSONDecodeError as e:
        return f"Error dalam format data GeoJSON: {str(e)}", 400
        
    except Exception as e:
        logging.error(f"Fatal error during SHP export: {str(e)}", exc_info=True)
        return f"Terjadi kesalahan fatal saat memproses file: {str(e)}", 500
        
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

# --------------------------------------------------------------------------------------
# Endpoint untuk menghitung luas polygon dengan UTM Zone 52S
# --------------------------------------------------------------------------------------
@app.route('/calculate_area_json', methods=['POST'])
def calculate_area_json():
    """Menghitung luas polygon menggunakan UTM Zone 52S dan mengembalikan response JSON"""
    logging.info("=== Mulai Perhitungan Luas Polygon dengan UTM Zone 52S ===")
    
    try:
        data = request.get_json()
        geojson_data = data.get('geojson_data')
        user_id = session.get('user_id', 'unknown')
        session_id = session.get('session_id', 'unknown')
        
        if not geojson_data:
            return jsonify({
                'success': False,
                'error': 'Tidak ada data polygon yang diterima.'
            }), 400
        
        if not geojson_data.get('geometry'):
            return jsonify({
                'success': False,
                'error': 'Data geometry tidak valid.'
            }), 400
        
        # Konversi GeoJSON ke Shapely geometry
        geom = shape(geojson_data['geometry'])
        wkt_geometry = geom.wkt
        
        # Priority 1: Hitung dengan UTM Zone 52S (paling akurat untuk lokasi Anda)
        try:
            area_sq_m, area_sq_km, area_hectare = calculate_area_utm(geom)
            method = 'UTM Zone 52S'
            logging.info(f"Perhitungan UTM berhasil untuk user {user_id}: {area_sq_m:.2f} m²")
            
            # Simpan ke database dengan user info
            connection = get_mysql_connection()
            if connection:
                try:
                    with connection.cursor() as cursor:
                        insert_sql = """
                        INSERT INTO polygon_areas (geometry_wkt, area_sq_m, area_sq_km, area_hectare, utm_zone, method, calculated_at, user_id, session_id)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s)
                        """
                        cursor.execute(insert_sql, (wkt_geometry, area_sq_m, area_sq_km, area_hectare, app.config['UTM_ZONE'], method, user_id, session_id))
                        connection.commit()
                except Exception as e:
                    logging.error(f"Error menyimpan ke database: {str(e)}")
                finally:
                    connection.close()
            
            return jsonify({
                'success': True,
                'area_sq_m': area_sq_m,
                'area_sq_km': area_sq_km,
                'area_hectare': area_hectare,
                'method': method,
                'utm_zone': app.config['UTM_ZONE'],
                'geometry_wkt': wkt_geometry,
                'user_id': user_id
            })
            
        except Exception as utm_error:
            logging.error(f"Error perhitungan UTM: {str(utm_error)}")
            
            # Priority 2: Coba dengan MySQL
            mysql_area_m, mysql_area_km, mysql_area_ha, mysql_method = calculate_area_mysql_multiuser(wkt_geometry, user_id, session_id)
            if mysql_area_m is not None:
                return jsonify({
                    'success': True,
                    'area_sq_m': mysql_area_m,
                    'area_sq_km': mysql_area_km,
                    'area_hectare': mysql_area_ha,
                    'method': mysql_method,
                    'utm_zone': app.config['UTM_ZONE'],
                    'geometry_wkt': wkt_geometry,
                    'user_id': user_id
                })
            
            # Priority 3: Fallback ke Shapely (kurang akurat)
            area_sq_m_fallback = geom.area * 1000000  # Konversi aproksimasi
            area_sq_km_fallback = area_sq_m_fallback / 1_000_000
            area_hectare_fallback = area_sq_m_fallback / 10_000
            
            return jsonify({
                'success': True,
                'area_sq_m': area_sq_m_fallback,
                'area_sq_km': area_sq_km_fallback,
                'area_hectare': area_hectare_fallback,
                'method': 'Shapely (Fallback)',
                'utm_zone': app.config['UTM_ZONE'],
                'geometry_wkt': wkt_geometry,
                'user_id': user_id,
                'warning': 'Menggunakan perhitungan fallback, hasil mungkin kurang akurat'
            })
            
    except Exception as e:
        logging.error(f"Error calculating area: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error dalam perhitungan luas: {str(e)}'
        }), 500

# ====================================================================
# MAIN EXECUTION - DIPERBAIKI UNTUK RENDER
# ====================================================================

if __name__ == '__main__':
    logging.info("Aplikasi Flask dengan Socket.IO dimulai...")
    
    # Inisialisasi database
    logging.info("Memulai inisialisasi database...")
    if init_database():
        logging.info("Inisialisasi database berhasil")
    else:
        logging.warning("Inisialisasi database gagal, fitur MySQL mungkin tidak berfungsi")
    
    # Inisialisasi database multiuser
    logging.info("Memulai inisialisasi database multiuser...")
    if init_database_multiuser():
        logging.info("Inisialisasi database multiuser berhasil")
    else:
        logging.warning("Inisialisasi database multiuser gagal")
    
    # Test UTM transformation
    try:
        from shapely.geometry import Polygon
        test_polygon = Polygon([(128.0, -3.6), (128.1, -3.6), (128.1, -3.7), (128.0, -3.7)])
        area_m, area_km, area_ha = calculate_area_utm(test_polygon)
        logging.info(f"Test UTM Zone 52S berhasil: {area_m:.2f} m²")
    except Exception as e:
        logging.warning(f"Test UTM gagal: {str(e)}")
    
    # ====================================================================
    # KONFIGURASI UNTUK RENDER - AMBIL PORT DARI ENVIRONMENT
    # ====================================================================
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logging.info(f"🚀 Menjalankan aplikasi di port {port} (debug: {debug})")
    
    # Jalankan aplikasi dengan Socket.IO
    socketio.run(app, debug=debug, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)