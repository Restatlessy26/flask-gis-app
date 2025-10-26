from flask import Flask, url_for, send_file, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from shapely.geometry import Polygon, Point, shape
from folium.plugins import Draw
from dotenv import load_dotenv
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

load_dotenv()

app = Flask(__name__)
# MENAIKKAN BATAS UKURAN PAYLOAD POST (50 MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 
app.config['SECRET_KEY'] = secrets.token_hex(32)  # Secret key untuk session

# Konfigurasi MySQL
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'gis_db')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', '3306'))

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
        return False

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
# KODE ASLI ANDA - TIDAK DIUBAH
# ====================================================================

# Fungsi untuk koneksi database MySQL
def get_mysql_connection():
    """Membuat koneksi ke database MySQL dengan penanganan error"""
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
        return None
    except Exception as e:
        logging.error(f"Unexpected error in MySQL connection: {str(e)}")
        return None

# Fungsi untuk membuat database dan tabel jika belum ada
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
        return False

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
# FUNGSI INDEX (MAP INITIALIZATION) - DIPERBAIKI
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

    # 🌟 IMPLEMENTASI MENU ALA GOOGLE EARTH PRO (HTML/CSS/JS) - DIPERBAIKI UNTUK GPS DAN PETA
    html_js = """
    <style>
        /* Container untuk seluruh menu */
        .menu-bar { 
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
        }
        .menu-item {
            position: relative;
            padding: 5px 10px;
            cursor: pointer;
            font-size: 14px;
            color: #333;
            user-select: none;
        }
        .menu-item:hover {
            background-color: #ddd;
            border-radius: 2px;
        }

        /* Konten Dropdown */
        .dropdown-content {
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
        }
        .dropdown-content button, .dropdown-content .submenu-item {
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
        }
        .dropdown-content button:hover, .dropdown-content .submenu-item:hover {
            background-color: #007bff;
            color: white;
        }
        .show-dropdown {
            display: block;
        }

        /* Submenu Container */
        .submenu-item::after {
            content: '►';
            float: right;
            margin-left: 10px;
            font-size: 10px;
        }
        .submenu-content {
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
        }
        .submenu-item:hover .submenu-content {
            display: block;
        }
        
        /* PENEMPATAN KONTROL ZOOM */
        .leaflet-top.leaflet-left {
            left: auto !important; 
            right: 5px !important; 
            top: 30px !important;
        }
        .leaflet-top.leaflet-right {
            top: 120px !important; 
            transform:translateX(5px);
        }
        
        /* STYLE UNTUK TABEL HASIL LUAS YANG BISA DIGESER DENGAN HEADER TETAP */
        .results-container {
            position: fixed;
            top: 100px;
            right: 20px;
            width: 500px;
            background: white;
            border: 2px solid #2c3e50;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            z-index: 999;
            display: none;
            max-height: 500px;
            overflow: hidden;
            cursor: default;
        }
        
        .results-header {
            background: #2c3e50;
            color: white;
            padding: 12px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: move;
            user-select: none;
            border-radius: 6px 6px 0 0;
        }
        
        .close-results {
            background: none;
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            padding: 0;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1001;
        }
        
        .close-results:hover {
            background: rgba(255,255,255,0.2);
            border-radius: 50%;
        }
        
        /* Container untuk tabel dengan scroll */
        .table-container {
            overflow-y: auto;
            max-height: 400px;
            position: relative;
        }
        
        .results-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }
        
        /* Header tabel yang tetap saat di-scroll */
        .results-table th {
            background: #f8f9fa;
            padding: 8px;
            text-align: left;
            border-bottom: 2px solid #ddd;
            font-weight: bold;
            position: sticky;
            top: 0;
            background: #f8f9fa;
            z-index: 10;
        }
        
        .results-table td {
            padding: 8px;
            border-bottom: 1px solid #eee;
            cursor: pointer; /* Baris tabel bisa diklik */
        }
        
        .results-table tr:hover {
            background: #e3f2fd !important; /* Highlight saat hover */
        }
        
        .results-table tr.selected {
            background: #ffeb3b !important; /* Warna kuning untuk baris terpilih */
            font-weight: bold;
        }
        
        .area-value {
            font-weight: bold;
            color: #2c3e50;
        }
        
        .no-results {
            padding: 20px;
            text-align: center;
            color: #666;
            font-style: italic;
        }
        
        .export-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            margin: 2px;
            transition: background 0.2s;
        }
        
        .export-btn:hover {
            background: #218838;
        }
        
        .delete-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            margin: 2px;
            transition: background 0.2s;
        }
        
        .delete-btn:hover {
            background: #c82333;
        }
        
        .zoom-btn {
            background: #ff9800;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            margin: 2px;
            transition: background 0.2s;
        }
        
        .zoom-btn:hover {
            background: #e68900;
        }
        
        .loading {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255,255,255,0.95);
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            z-index: 1000;
            border: 1px solid #ccc;
        }
        
        .info-panel {
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 12px;
            border-radius: 6px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 12px;
            z-index: 998;
            cursor: move;
            user-select: none;
            border: 1px solid #2c3e50;
            max-width: 250px;
        }
        
        /* Style untuk indikator draggable */
        .drag-handle {
            cursor: move;
            margin-right: 8px;
            font-size: 16px;
        }
        
        /* Style saat sedang dragging */
        .dragging {
            opacity: 0.9;
            box-shadow: 0 6px 20px rgba(0,0,0,0.4);
            border-color: #007bff;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .results-container {
                width: 90%;
                right: 5%;
                left: 5%;
            }
        }
        
        /* Scrollbar styling */
        .table-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .table-container::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }
        
        .table-container::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 4px;
        }
        
        .table-container::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8;
        }
        
        /* Style untuk highlight polygon */
        .highlight-polygon {
            stroke: #ff0000 !important;
            stroke-width: 4 !important;
            stroke-opacity: 1 !important;
            fill-color: #ffff00 !important;
            fill-opacity: 0.3 !important;
        }
        
        /* Style untuk status undo/redo */
        .undo-redo-status {
            position: fixed;
            top: 40px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            display: none;
        }

        /* ========================================= */
        /* PERBAIKAN STYLE UNTUK GPS TRACKING */
        /* ========================================= */
        
        /* PERBAIKAN: Tombol GPS yang lebih bawah (dari 80px menjadi 120px) */
        .gps-button {
            position: absolute;
            top: 120px;  /* DIPERBAIKI: DARI 80px MENJADI 120px */
            left: 10px;
            z-index: 1000;
            background: white;
            border: 2px solid rgba(0,0,0,0.2);
            border-radius: 4px;
            padding: 8px;
            cursor: pointer;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4);
            transition: all 0.3s ease;
        }

        .gps-button:hover {
            background: #f4f4f4;
            transform: scale(1.05);
        }

        .gps-button.active {
            background: #4CAF50;
            color: white;
            border-color: #4CAF50;
        }

        .gps-button.disabled {
            background: #cccccc;
            cursor: not-allowed;
            opacity: 0.6;
        }

        .gps-button.loading {
            background: #ff9800;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }

        /* Info panel GPS yang lebih informatif */
        .gps-info {
            position: fixed;
            top: 120px;
            left: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 12px;
            z-index: 998;
            border: 2px solid #2c3e50;
            max-width: 280px;
            display: none;
        }

        .gps-info.visible {
            display: block;
        }

        .gps-status {
            font-weight: bold;
            margin-bottom: 8px;
            padding: 4px 8px;
            border-radius: 4px;
            text-align: center;
        }

        .gps-status.tracking {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .gps-status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .gps-status.waiting {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }

        .gps-coordinates {
            font-family: 'Courier New', monospace;
            font-size: 11px;
            margin: 8px 0;
            background: #f8f9fa;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
        }

        .gps-actions {
            margin-top: 10px;
            text-align: center;
        }

        .gps-actions button {
            background: #007bff;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            margin: 2px;
            transition: background 0.2s;
        }

        .gps-actions button:hover {
            background: #0056b3;
        }

        .gps-actions button.stop {
            background: #dc3545;
        }

        .gps-actions button.stop:hover {
            background: #c82333;
        }

        /* Marker lokasi pengguna yang lebih mencolok */
        .user-location-marker {
            background: #4285F4;
            border: 3px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            animation: pulse-marker 2s infinite;
        }

        @keyframes pulse-marker {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }

        /* Circle akurasi yang lebih jelas */
        .accuracy-circle {
            stroke: #4285F4;
            stroke-width: 2;
            stroke-opacity: 0.6;
            fill: #4285F4;
            fill-opacity: 0.1;
            animation: pulse-circle 3s infinite;
        }

        @keyframes pulse-circle {
            0% { stroke-opacity: 0.6; }
            50% { stroke-opacity: 0.3; }
            100% { stroke-opacity: 0.6; }
        }

        /* ========================================= */
        /* STYLE UNTUK MULTIUSER FEATURES */
        /* ========================================= */
        
        /* PERBAIKAN: User status yang bisa digeser */
        .user-status {
            position: fixed;
            top: 5px;
            right: 5px;
            background: rgba(255,255,255,0.95);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 1001;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            border: 1px solid #2c3e50;
            cursor: move; /* INDIKATOR BISA DIGESER */
            user-select: none;
        }
        
        /* Style saat dragging user status */
        .user-status.dragging {
            opacity: 0.9;
            box-shadow: 0 6px 20px rgba(0,0,0,0.4);
            border-color: #007bff;
        }
        
        .user-count {
            font-weight: bold;
            color: #28a745;
        }
        
        .user-id {
            font-size: 10px;
            color: #666;
            margin-top: 2px;
        }
        
        .collaborative-marker {
            background: #ff6b6b;
            border: 3px solid white;
            border-radius: 50%;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        .user-typing-indicator {
            position: fixed;
            bottom: 60px;
            left: 20px;
            background: rgba(255,255,255,0.9);
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 11px;
            z-index: 1000;
            border: 1px solid #ddd;
            display: none;
        }

        /* ========================================= */
        /* STYLE UNTUK GPS TRACKING RECORDER */
        /* ========================================= */

        .gps-recorder {
            position: absolute;
            top: 160px; /* Di bawah tombol GPS biasa */
            left: 10px;
            z-index: 1000;
            background: white;
            border: 2px solid rgba(0,0,0,0.2);
            border-radius: 4px;
            padding: 8px;
            cursor: pointer;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4);
            transition: all 0.3s ease;
        }

        .gps-recorder:hover {
            background: #f4f4f4;
            transform: scale(1.05);
        }

        .gps-recorder.recording {
            background: #dc3545;
            color: white;
            border-color: #dc3545;
            animation: pulse-recording 1.5s infinite;
        }

        .gps-recorder.paused {
            background: #ffc107;
            color: black;
            border-color: #ffc107;
        }

        @keyframes pulse-recording {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }

        .recorder-panel {
            position: fixed;
            top: 200px;
            left: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            font-size: 12px;
            z-index: 998;
            border: 2px solid #2c3e50;
            max-width: 300px;
            display: none;
        }

        .recorder-panel.visible {
            display: block;
        }

        .recorder-status {
            font-weight: bold;
            margin-bottom: 8px;
            padding: 4px 8px;
            border-radius: 4px;
            text-align: center;
        }

        .recorder-status.recording {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .recorder-status.paused {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }

        .recorder-status.stopped {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .recorder-info {
            font-family: 'Courier New', monospace;
            font-size: 11px;
            margin: 8px 0;
            background: #f8f9fa;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
        }

        .recorder-actions {
            margin-top: 10px;
            text-align: center;
        }

        .recorder-actions button {
            background: #007bff;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            margin: 2px;
            transition: background 0.2s;
        }

        .recorder-actions button:hover {
            background: #0056b3;
        }

        .recorder-actions button.stop {
            background: #dc3545;
        }

        .recorder-actions button.stop:hover {
            background: #c82333;
        }

        .recorder-actions button.export {
            background: #28a745;
        }

        .recorder-actions button.export:hover {
            background: #218838;
        }

        /* Style untuk track line di peta */
        .gps-track-line {
            stroke: #ff6b6b;
            stroke-width: 4;
            stroke-opacity: 0.8;
            fill: none;
            animation: pulse-track 2s infinite;
        }

        @keyframes pulse-track {
            0% { stroke-width: 4; }
            50% { stroke-width: 6; }
            100% { stroke-width: 4; }
        }

        .track-point-marker {
            background: #ff6b6b;
            border: 2px solid white;
            border-radius: 50%;
            width: 6px;
            height: 6px;
        }

        /* Popup info untuk track */
        .track-popup {
            font-size: 12px;
            min-width: 250px;
        }

        .track-popup h4 {
            margin: 0 0 8px 0;
            color: #2c3e50;
            border-bottom: 1px solid #eee;
            padding-bottom: 4px;
        }

        .track-popup .track-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: 8px 0;
        }

        .track-popup .stat-item {
            display: flex;
            flex-direction: column;
        }

        .track-popup .stat-label {
            font-size: 10px;
            color: #666;
            margin-bottom: 2px;
        }

        .track-popup .stat-value {
            font-weight: bold;
            color: #2c3e50;
        }

        .track-popup .track-actions {
            margin-top: 10px;
            text-align: center;
        }
    </style>

    <!-- Status Multi-User YANG BISA DIGESER -->
    <div class="user-status" id="userStatus">
        <div>👥 Users Online: <span class="user-count" id="userCount">1</span></div>
        <div class="user-id">Your ID: <span id="userId">-</span></div>
    </div>

    <!-- Typing Indicator -->
    <div class="user-typing-indicator" id="typingIndicator">
        <span id="typingText">Someone is typing...</span>
    </div>

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
            <button onclick="undo()">Undo (Ctrl+Z)</button>
            <button onclick="redo()">Redo (Ctrl+Y)</button>
        </div>
        
        <div class='menu-item' onclick="toggleMenu('view')">Lihat</div>
        <div id='viewDropdown' class='dropdown-content'>
               <button disabled style="color: #888;">Toolbar</button>
        </div>

        <!-- MENU ANALISIS - PERTAHANKAN FITUR HITUNG LUAS POLYGON -->
        <div class='menu-item' onclick="toggleMenu('analysis')">Analisis</div>
        <div id='analysisDropdown' class='dropdown-content'>
            <button onclick="calculateAllPolygonsArea()">Hitung Luas Semua Polygon</button>
            <button onclick="showResultsTable()">Tampilkan Hasil</button>
            <button onclick="clearAllResults()">Hapus Semua Hasil</button>
            <button onclick="clearHighlight()">Hapus Highlight</button>
        </div>

        <!-- MENU KOLABORASI - FITUR MULTIUSER BARU -->
        <div class='menu-item' onclick="toggleMenu('collaborative')">Kolaborasi</div>
        <div id='collaborativeDropdown' class='dropdown-content'>
            <button onclick="toggleCollaborativeMode()" id="collaborativeToggle">Aktifkan Mode Kolaborasi</button>
            <button onclick="broadcastMyLocation()">Bagikan Lokasi Saya</button>
            <button onclick="showOnlineUsers()">Tampilkan User Online</button>
            <button onclick="toggleGPSRecorder()" id="menuGPSRecorder">🎥 Rekam Perjalanan GPS</button>
        </div>

    </div>

    <!-- CONTAINER UNTUK TABEL HASIL LUAS YANG BISA DIGESER DENGAN HEADER TETAP -->
    <div id="resultsContainer" class="results-container">
        <div class="results-header" id="resultsHeader">
            <span>📋 Hasil Perhitungan Luas</span>
            <button class="close-results" onclick="hideResultsTable()">×</button>
        </div>
        <div class="table-container">
            <table class="results-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Luas (m²)</th>
                        <th>Luas (ha)</th>
                        <th>Luas (km²)</th>
                        <th>Aksi</th>
                    </tr>
                </thead>
                <tbody id="resultsBody">
                    <!-- Data hasil akan dimasukkan di sini oleh JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <!-- PERBAIKAN: INFO PANEL UTM DISEMBUNYIKAN DARI USER -->
    <div class="info-panel" id="infoPanel" style="display: none;">
        <div style="font-weight: bold; margin-bottom: 5px;">🌍 Informasi Peta</div>
        <strong>UTM Zone:</strong> 52S (EPSG:32752)<br>
        <strong>Lokasi:</strong> Maluku, Indonesia<br>
        <strong>Status:</strong> <span id="drawingStatus">Siap</span><br>
        <strong>Polygon Terpilih:</strong> <span id="selectedPolygon">Tidak ada</span>
    </div>

    <!-- ========================================= -->
    <!-- ELEMEN UNTUK FITUR GPS TRACKING REAL-TIME YANG DIPERBAIKI -->
    <!-- ========================================= -->
    
    <!-- Tombol GPS Tracking - DIPINDAH KE SEBELAH KIRI DAN LEBIH BAWAH -->
    <div id="gpsButton" class="gps-button" title="Aktifkan Pelacakan GPS">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3A8.994 8.994 0 0 0 13 3.06V1h-2v2.06A8.994 8.994 0 0 0 3.06 11H1v2h2.06A8.994 8.994 0 0 0 11 20.94V23h2v-2.06A8.994 8.994 0 0 0 20.94 13H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z"/>
        </svg>
    </div>

    <!-- Info Panel GPS - DIPINDAH KE SEBELAH KIRI -->
    <div class="gps-info" id="gpsInfo">
        <div style="font-weight: bold; margin-bottom: 5px;">📍 Informasi GPS</div>
        <div class="gps-status" id="gpsStatus">Menunggu...</div>
        <div class="gps-coordinates">
            <strong>Lat:</strong> <span id="gpsLat">-</span><br>
            <strong>Lng:</strong> <span id="gpsLng">-</span><br>
            <strong>Akurasi:</strong> <span id="gpsAccuracy">-</span> meter<br>
            <strong>Terakhir Update:</strong> <span id="gpsLastUpdate">-</span>
        </div>
        <div class="gps-actions">
            <button onclick="centerOnUser()">🎯 Pusatkan Peta</button>
            <button onclick="stopGPSTracking()" class="stop">⏹️ Stop</button>
        </div>
    </div>

    <!-- ========================================= -->
    <!-- ELEMEN UNTUK GPS TRACKING RECORDER -->
    <!-- ========================================= -->

    <!-- Tombol GPS Recorder -->
    <div id="gpsRecorder" class="gps-recorder" title="Mulai Rekaman Perjalanan">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
        </svg>
    </div>

    <!-- Panel Info Recorder -->
    <div class="recorder-panel" id="recorderPanel">
        <div style="font-weight: bold; margin-bottom: 5px;">🎥 Perekam Perjalanan</div>
        <div class="recorder-status" id="recorderStatus">Berhenti</div>
        <div class="recorder-info">
            <strong>Durasi:</strong> <span id="recorderDuration">00:00:00</span><br>
            <strong>Jarak:</strong> <span id="recorderDistance">0 km</span><br>
            <strong>Titik:</strong> <span id="recorderPoints">0</span><br>
            <strong>Status:</strong> <span id="recorderStatusInfo">Berhenti</span>
        </div>
        <div class="recorder-actions">
            <button onclick="togglePauseRecording()" id="pauseRecording">⏸️ Jeda</button>
            <button onclick="stopGPSRecording()" class="stop">⏹️ Stop</button>
            <button onclick="exportGPSTrack()" class="export">💾 Ekspor</button>
            <button onclick="clearGPSTrack()" class="delete">🗑️ Hapus</button>
        </div>
    </div>

    <!-- LOADING INDICATOR -->
    <div id="loadingIndicator" class="loading">
        <div style="text-align: center;">
            <div style="font-size: 16px; margin-bottom: 10px;">🔄 Menghitung Luas</div>
            <div>Menggunakan UTM Zone 52S...</div>
            <div style="margin-top: 10px; font-size: 12px; color: #666;">Harap tunggu</div>
        </div>
    </div>

    <!-- UNDO/REDO STATUS INDICATOR -->
    <div id="undoRedoStatus" class="undo-redo-status"></div>

    <script>
        // =========================================
        // INISIALISASI SOCKET.IO UNTUK REAL-TIME
        // =========================================
        
        // Koneksi Socket.IO
        const socket = io();
        
        // Variabel untuk collaborative mode
        let collaborativeMode = false;
        let collaborativeLayers = new Map();
        
        // Event ketika terhubung ke server
        socket.on('connect', function() {
            console.log('Connected to server with Socket.IO');
        });
        
        // Event ketika koneksi berhasil established
        socket.on('connection_established', function(data) {
            console.log('Connection established:', data);
            document.getElementById('userId').textContent = data.user_id.substring(0, 8) + '...';
            document.getElementById('userCount').textContent = data.connected_users;
            
            // Simpan user info
            window.userId = data.user_id;
            window.sessionId = data.session_id;
        });
        
        // Update jumlah user online
        socket.on('user_count_update', function(data) {
            document.getElementById('userCount').textContent = data.connected_users;
        });
        
        // Terima drawing dari user lain
        socket.on('collaborative_drawing_update', function(data) {
            if (!collaborativeMode) return;
            
            addCollaborativeDrawing(data);
        });
        
        // Terima hasil perhitungan luas real-time
        socket.on('area_calculation_result', function(data) {
            handleAreaCalculationResult(data);
        });

        // =========================================
        // FUNGSI MULTIUSER BARU
        // =========================================
        
        function toggleCollaborativeMode() {
            collaborativeMode = !collaborativeMode;
            const button = document.getElementById('collaborativeToggle');
            
            if (collaborativeMode) {
                button.textContent = 'Nonaktifkan Mode Kolaborasi';
                button.style.background = '#28a745';
                button.style.color = 'white';
                alert('Mode kolaborasi diaktifkan! Anda dapat melihat drawing user lain.');
            } else {
                button.textContent = 'Aktifkan Mode Kolaborasi';
                button.style.background = '';
                button.style.color = '';
                // Hapus semua collaborative layers
                clearCollaborativeDrawings();
                alert('Mode kolaborasi dinonaktifkan.');
            }
        }
        
        function addCollaborativeDrawing(data) {
            const map = getMap();
            if (!map) return;
            
            try {
                const geojson = data.geometry;
                const layer = L.geoJSON(geojson, {
                    style: data.style || {
                        color: '#ff6b6b',
                        weight: 3,
                        opacity: 0.7,
                        fillOpacity: 0.2
                    }
                }).addTo(map);
                
                // Tambahkan popup dengan info user
                layer.bindPopup(`
                    <div style="font-size: 12px;">
                        <strong>Drawing dari User</strong><br>
                        ID: ${data.user_id.substring(0, 8)}...<br>
                        Waktu: ${new Date(data.timestamp).toLocaleTimeString('id-ID')}
                    </div>
                `);
                
                // Simpan layer
                const layerId = `${data.user_id}_${Date.now()}`;
                collaborativeLayers.set(layerId, layer);
                
                // Auto-remove setelah 5 menit
                setTimeout(() => {
                    if (collaborativeLayers.has(layerId)) {
                        map.removeLayer(layer);
                        collaborativeLayers.delete(layerId);
                    }
                }, 5 * 60 * 1000);
                
            } catch (error) {
                console.error('Error adding collaborative drawing:', error);
            }
        }
        
        function clearCollaborativeDrawings() {
            const map = getMap();
            if (!map) return;
            
            collaborativeLayers.forEach((layer, layerId) => {
                map.removeLayer(layer);
            });
            collaborativeLayers.clear();
        }
        
        function broadcastMyLocation() {
            if (!navigator.geolocation) {
                alert('GPS tidak didukung oleh browser Anda.');
                return;
            }
            
            navigator.geolocation.getCurrentPosition(function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Kirim ke server
                socket.emit('collaborative_drawing', {
                    geometry: {
                        type: 'Point',
                        coordinates: [lng, lat]
                    },
                    type: 'marker',
                    style: {
                        color: '#4285F4',
                        radius: 8
                    },
                    broadcast: true
                });
                
                alert('Lokasi Anda telah dibagikan ke semua user!');
            }, function(error) {
                alert('Error mendapatkan lokasi: ' + error.message);
            });
        }
        
        function showOnlineUsers() {
            alert(`Total user online: ${document.getElementById('userCount').textContent}\\nYour ID: ${window.userId}`);
        }

        // =========================================
        // FUNGSI UNTUK MENGIRIM ACTIVITY KE SERVER
        // =========================================
        
        function sendUserActivity(type) {
            socket.emit('user_activity', {
                type: type,
                timestamp: new Date().toISOString()
            });
        }

        // =========================================
        // MODIFIKASI FUNGSI EXISTING UNTUK REAL-TIME
        // =========================================
        
        // Override fungsi calculateAllPolygonsArea untuk menggunakan Socket.IO
        function calculateAllPolygonsArea() {
            const drawnItems = getDrawnItems();
            closeAllMenus(null);

            if (!drawnItems) {
                alert("Tidak ada layer yang digambar.");
                return;
            }

            const layers = drawnItems.getLayers();
            const polygons = layers.filter(layer => layer instanceof L.Polygon);

            if (polygons.length === 0) {
                alert("Tidak ada polygon yang ditemukan. Harap gambar polygon terlebih dahulu.");
                return;
            }

            showLoading();
            updateDrawingStatus('Menghitung luas semua polygon...');
            
            let completedCalculations = 0;
            let totalPolygons = polygons.length;

            polygons.forEach((polygon, index) => {
                const geojson = polygon.toGeoJSON();
                
                // Kirim via Socket.IO bukan HTTP POST
                socket.emit('area_calculation_request', {
                    geojson_data: geojson
                });
                
                completedCalculations++;
                
                // Jika semua perhitungan selesai
                if (completedCalculations === totalPolygons) {
                    hideLoading();
                    updateDrawingStatus('Siap');
                    alert('Permintaan perhitungan luas telah dikirim! Hasil akan ditampilkan secara real-time.');
                }
            });
        }
        
        // Fungsi untuk handle hasil perhitungan dari Socket.IO
        function handleAreaCalculationResult(data) {
            if (data.success) {
                // Proses hasil sama seperti sebelumnya
                const resultId = areaResults.length + 1;
                
                // Cari layer polygon yang sesuai
                const drawnItems = getDrawnItems();
                const layers = drawnItems.getLayers();
                const polygons = layers.filter(layer => layer instanceof L.Polygon);
                
                if (polygons.length > 0) {
                    const polygon = polygons[polygons.length - 1]; // Ambil yang terakhir
                    
                    addAreaResult({
                        id: resultId,
                        area_m2: data.area_sq_m,
                        area_hectare: data.area_hectare,
                        area_km2: data.area_sq_km,
                        method: data.method,
                        utm_zone: data.utm_zone,
                        timestamp: new Date().toLocaleString('id-ID'),
                        geometry: data.geometry_wkt,
                        layer: polygon
                    });
                    
                    polygonLayers.set(resultId, polygon);
                    
                    polygon.bindPopup(
                        '<div style=\"font-size: 12px;\">' +
                        '<h4>Hasil Perhitungan Luas (Real-time)</h4>' +
                        '<p><strong>Luas:</strong> ' + formatNumberForDisplay(data.area_sq_m) + ' m²</p>' +
                        '<p><strong>Luas:</strong> ' + data.area_hectare.toFixed(4) + ' ha</p>' +
                        '<p><strong>Luas:</strong> ' + formatKm2(data.area_sq_km) + ' km²</p>' +
                        '<p><strong>Metode:</strong> ' + data.method + '</p>' +
                        '<p><strong>UTM Zone:</strong> ' + data.utm_zone + '</p>' +
                        '</div>'
                    );
                }
                
                showResultsTable();
                
            } else {
                alert('Error dalam perhitungan: ' + data.error);
            }
        }

        // =========================================
        // KODE JAVASCRIPT ASLI ANDA - DIPERBAIKI
        // =========================================
        
        // FUNGSI FORMAT NUMBER DI SCOPE GLOBAL
        function formatNumber(num) {
            return num.toFixed(2).replace(/\\d(?=(\\d{3})+\\.)/g, '$&.').replace('.', ',');
        }
        
        function formatNumberForDisplay(num) {
            return new Intl.NumberFormat('id-ID', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            }).format(num);
        }
        
        // FUNGSI KHUSUS UNTUK FORMAT KM² - HAPUS ANGKA 0 DI DEPAN
        function formatKm2(num) {
            if (num < 1 && num > 0) {
                // Hilangkan angka 0 di depan untuk angka desimal kecil
                return num.toFixed(6).replace('0.', '.');
            } else {
                return num.toFixed(6);
            }
        }

        const menuItems = [
            {id: 'fileDropdown', parentId: 'file'},
            {id: 'editDropdown', parentId: 'edit'},
            {id: 'viewDropdown', parentId: 'view'},
            {id: 'analysisDropdown', parentId: 'analysis'},
            {id: 'collaborativeDropdown', parentId: 'collaborative'}
        ];
        
        // Array untuk menyimpan hasil perhitungan
        let areaResults = [];
        
        // Variabel untuk menyimpan layer polygon yang sesuai dengan hasil
        let polygonLayers = new Map();
        
        // Variabel untuk highlight layer
        let currentHighlightLayer = null;
        let currentSelectedRow = null;
        
        // Variabel untuk drag functionality
        let dragState = {
            isDragging: false,
            currentDraggable: null,
            dragOffset: { x: 0, y: 0 },
            startX: 0,
            startY: 0
        };

        // =========================================
        // VARIABEL UNTUK GPS TRACKING REAL-TIME YANG DIPERBAIKI
        // =========================================
        let gpsWatchId = null;
        let userLocationMarker = null;
        let accuracyCircle = null;
        let isGPSTracking = false;
        let gpsUpdateInterval = null;

        // =========================================
        // VARIABEL UNTUK GPS TRACKING RECORDER
        // =========================================
        let gpsRecorder = {
            isRecording: false,
            isPaused: false,
            trackPoints: [],
            trackLine: null,
            trackStartTime: null,
            trackInterval: null,
            totalDistance: 0,
            averageSpeed: 0,
            maxSpeed: 0,
            updateFrequency: 3000, // Update setiap 3 detik
            lastPosition: null,
            lastTimestamp: null
        };

        // =========================================
        // FUNGSI UNTUK GPS TRACKING REAL-TIME - DIPERBAIKI
        // =========================================

        // Fungsi untuk memulai GPS tracking - DIPERBAIKI
        function startGPSTracking() {
            console.log('Memulai GPS tracking...');
            
            if (!navigator.geolocation) {
                alert("❌ GPS tidak didukung oleh browser Anda.");
                updateGPSStatus('Browser tidak mendukung GPS', 'error');
                return;
            }

            const gpsButton = document.getElementById('gpsButton');
            const gpsInfo = document.getElementById('gpsInfo');
            const gpsStatus = document.getElementById('gpsStatus');
            
            // Update UI
            gpsButton.classList.add('active');
            gpsButton.title = "Nonaktifkan Pelacakan GPS";
            gpsInfo.style.display = 'block';
            gpsStatus.textContent = 'Mencari sinyal GPS...';
            gpsStatus.className = 'gps-status waiting';
            
            isGPSTracking = true;
            updateDrawingStatus('Melacak GPS...');

            // Options untuk geolocation - DIPERBAIKI
            const geoOptions = {
                enableHighAccuracy: true,    // Gunakan GPS jika available
                timeout: 30000,              // Timeout 30 detik
                maximumAge: 60000            // Cache position maksimal 1 menit
            };

            // Dapatkan posisi saat ini terlebih dahulu
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    console.log('✅ Berhasil mendapatkan posisi GPS:', position);
                    updateUserLocation(position);
                    gpsStatus.textContent = 'Pelacakan GPS Aktif';
                    gpsStatus.className = 'gps-status tracking';
                    
                    // Mulai watch position untuk update berkelanjutan
                    gpsWatchId = navigator.geolocation.watchPosition(
                        updateUserLocation,
                        handleGPSError,
                        geoOptions
                    );
                    
                    // Update informasi setiap 5 detik
                    gpsUpdateInterval = setInterval(updateGPSInfo, 5000);
                    
                    // Kirim activity ke server
                    sendUserActivity('gps_tracking_started');
                },
                function(error) {
                    console.error('❌ Error mendapatkan posisi GPS:', error);
                    handleGPSError(error);
                },
                geoOptions
            );
        }

        // Fungsi untuk menghentikan GPS tracking - DIPERBAIKI
        function stopGPSTracking() {
            console.log('Menghentikan GPS tracking...');
            
            if (gpsWatchId !== null) {
                navigator.geolocation.clearWatch(gpsWatchId);
                gpsWatchId = null;
            }
            
            if (gpsUpdateInterval !== null) {
                clearInterval(gpsUpdateInterval);
                gpsUpdateInterval = null;
            }
            
            const gpsButton = document.getElementById('gpsButton');
            const gpsInfo = document.getElementById('gpsInfo');
            const gpsStatus = document.getElementById('gpsStatus');
            
            // Update UI
            gpsButton.classList.remove('active');
            gpsButton.title = "Aktifkan Pelacakan GPS";
            gpsStatus.textContent = 'Pelacakan Dihentikan';
            gpsStatus.className = 'gps-status';
            
            isGPSTracking = false;
            updateDrawingStatus('Siap');
            
            // Hapus marker dari peta
            removeUserLocationMarker();
            
            // Kirim activity ke server
            sendUserActivity('gps_tracking_stopped');
            
            // Sembunyikan info panel setelah beberapa detik
            setTimeout(() => {
                if (!isGPSTracking) {
                    gpsInfo.style.display = 'none';
                }
            }, 3000);
        }

        // PERBAIKAN: Fungsi untuk menghapus marker lokasi pengguna
        function removeUserLocationMarker() {
            const map = getMap();
            if (!map) return;
            
            // Hapus semua marker user location dari peta
            if (userLocationMarker) {
                try {
                    map.removeLayer(userLocationMarker);
                } catch (e) {
                    console.log('Marker sudah dihapus');
                }
                userLocationMarker = null;
            }
            if (accuracyCircle) {
                try {
                    map.removeLayer(accuracyCircle);
                } catch (e) {
                    console.log('Circle sudah dihapus');
                }
                accuracyCircle = null;
            }
            
            // PERBAIKAN: Hapus juga marker dari collaborative group jika ada
            const collaborativeGroup = getCollaborativeGroup();
            if (collaborativeGroup) {
                collaborativeGroup.eachLayer(function(layer) {
                    if (layer.options && layer.options.userId === window.userId) {
                        collaborativeGroup.removeLayer(layer);
                    }
                });
            }
        }

        // Fungsi untuk menangani error GPS - DIPERBAIKI
        function handleGPSError(error) {
            console.error('🚨 GPS Error:', error);
            const gpsStatus = document.getElementById('gpsStatus');
            const gpsButton = document.getElementById('gpsButton');
            
            const errorMessage = getGPSErrorMessage(error);
            gpsStatus.textContent = 'Error: ' + errorMessage;
            gpsStatus.className = 'gps-status error';
            gpsButton.classList.remove('active');
            
            isGPSTracking = false;
            updateDrawingStatus('Error GPS');
            
            // Tampilkan alert dengan saran perbaikan
            showGPSAlert(errorMessage);
        }

        // Fungsi untuk menampilkan alert GPS dengan saran
        function showGPSAlert(errorMessage) {
            let suggestion = '';
            
            switch(errorMessage) {
                case 'Akses GPS ditolak. Izinkan akses lokasi di browser.':
                    suggestion = '📱 Buka pengaturan browser Anda dan izinkan akses lokasi untuk website ini.';
                    break;
                case 'Informasi lokasi tidak tersedia.':
                    suggestion = '📍 Pastikan GPS perangkat Anda aktif dan terhubung ke internet.';
                    break;
                case 'Permintaan lokasi timeout.':
                    suggestion = '⏱️ Coba lagi dalam beberapa saat. Pastikan sinyal GPS kuat.';
                    break;
                default:
                    suggestion = '🔄 Refresh halaman dan coba lagi.';
            }
            
            alert(`❌ Gagal mengakses GPS:\\n${errorMessage}\\n\\n💡 Saran:\\n${suggestion}`);
        }

        // Fungsi untuk mendapatkan pesan error GPS - DIPERBAIKI
        function getGPSErrorMessage(error) {
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    return "Akses GPS ditolak. Izinkan akses lokasi di browser.";
                case error.POSITION_UNAVAILABLE:
                    return "Informasi lokasi tidak tersedia. Pastikan GPS aktif.";
                case error.TIMEOUT:
                    return "Permintaan lokasi timeout. Coba lagi.";
                default:
                    return "Error tidak diketahui: " + error.message;
            }
        }

        // =========================================
        // FUNGSI UNTUK MENDAPATKAN PETA - DIPERBAIKI
        // =========================================

        // FUNGSI UNTUK MENDAPATKAN MAP - DIPERBAIKI DENGAN MULTI-METODE
        function getMap() {
            // Cara 1: Cari melalui nama map yang diketahui
            const mapName = """ + json.dumps(map_name) + """;
            let mapElement = document.getElementById(mapName);
            
            if (mapElement && mapElement._leaflet_map) {
                console.log('✅ Peta ditemukan via mapName:', mapName);
                return mapElement._leaflet_map;
            }
            
            // Cara 2: Cari di seluruh window object
            for (let key in window) {
                if (window[key] instanceof L.Map) {
                    console.log('✅ Peta ditemukan di window:', key);
                    return window[key];
                }
            }
            
            // Cara 3: Cari di semua elemen dengan class leaflet-container
            const leafletContainers = document.getElementsByClassName('leaflet-container');
            if (leafletContainers.length > 0 && leafletContainers[0]._leaflet_map) {
                console.log('✅ Peta ditemukan via leaflet-container');
                return leafletContainers[0]._leaflet_map;
            }
            
            console.error('❌ Peta tidak ditemukan dengan semua metode');
            return null;
        }

        // PERBAIKAN: Fungsi untuk memperbarui lokasi pengguna di peta
        function updateUserLocation(position) {
            console.log('📍 Memperbarui lokasi pengguna:', position);
            
            const map = getMap();
            if (!map) {
                console.error('❌ Peta tidak ditemukan, mencoba lagi dalam 1 detik...');
                setTimeout(() => updateUserLocation(position), 1000);
                return;
            }
            
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            
            console.log(`📍 Koordinat: ${lat}, ${lng}, Akurasi: ${accuracy}m`);
            
            // PERBAIKAN: Hapus marker dan circle sebelumnya JIKA ADA
            removeUserLocationMarker();
            
            // PERBAIKAN: Buat marker dengan ID khusus untuk menghindari duplikasi
            userLocationMarker = L.marker([lat, lng], {
                icon: L.divIcon({
                    className: 'user-location-marker',
                    iconSize: [20, 20],
                    html: '<div style="width: 100%; height: 100%; border-radius: 50%; background: #4285F4; border: 3px solid white; box-shadow: 0 2px 10px rgba(0,0,0,0.3);"></div>'
                }),
                zIndexOffset: 1000
            }).addTo(map);
            
            // PERBAIKAN: Tambahkan circle akurasi
            accuracyCircle = L.circle([lat, lng], {
                radius: accuracy,
                color: '#4285F4',
                fillColor: '#4285F4',
                fillOpacity: 0.1,
                weight: 2,
                opacity: 0.5,
                className: 'accuracy-circle'
            }).addTo(map);
            
            // PERBAIKAN: Popup dengan event handler yang lebih baik
            userLocationMarker.bindPopup(`
                <div style="font-size: 12px; min-width: 200px;">
                    <strong>📍 Lokasi Anda</strong><br>
                    <strong>Lat:</strong> ${lat.toFixed(6)}<br>
                    <strong>Lng:</strong> ${lng.toFixed(6)}<br>
                    <strong>Akurasi:</strong> ${accuracy.toFixed(1)} meter<br>
                    <strong>Waktu:</strong> ${new Date().toLocaleTimeString('id-ID')}<br>
                    <div style="margin-top: 8px; text-align: center;">
                        <button onclick="centerOnUser()" style="background: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; margin: 2px;">
                            🎯 Pusatkan Peta
                        </button>
                        <button onclick="stopGPSTracking()" style="background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; margin: 2px;">
                            ⏹️ Stop
                        </button>
                    </div>
                </div>
            `);
            
            // PERBAIKAN: Pusatkan hanya pada pertama kali
            if (!window.userLocationInitialized) {
                centerOnUser();
                window.userLocationInitialized = true;
            }
            
            updateGPSInfo();
            updateGPSStatus('Lokasi ditemukan', 'tracking');
            console.log('✅ Marker lokasi berhasil ditambahkan ke peta');
        }

        // Fungsi untuk memusatkan peta ke lokasi pengguna - DIPERBAIKI
        function centerOnUser() {
            if (userLocationMarker) {
                const map = getMap();
                const latlng = userLocationMarker.getLatLng();
                
                // Zoom yang lebih reasonable
                map.setView(latlng, 16);
                
                // Buka popup lokasi
                userLocationMarker.openPopup();
                
                console.log('🎯 Memusatkan peta ke lokasi pengguna:', latlng);
            } else {
                alert('❌ Lokasi pengguna belum tersedia. Aktifkan GPS tracking terlebih dahulu.');
            }
        }

        // Fungsi untuk memperbarui info GPS di panel - DIPERBAIKI
        function updateGPSInfo() {
            if (!userLocationMarker) return;
            
            const latlng = userLocationMarker.getLatLng();
            const accuracy = accuracyCircle ? accuracyCircle.getRadius() : 0;
            
            document.getElementById('gpsLat').textContent = latlng.lat.toFixed(6);
            document.getElementById('gpsLng').textContent = latlng.lng.toFixed(6);
            document.getElementById('gpsAccuracy').textContent = accuracy.toFixed(1);
            document.getElementById('gpsLastUpdate').textContent = new Date().toLocaleTimeString('id-ID');
        }

        // Fungsi untuk update status GPS
        function updateGPSStatus(message, type) {
            const gpsStatus = document.getElementById('gpsStatus');
            if (!gpsStatus) return;
            
            gpsStatus.textContent = message;
            gpsStatus.className = 'gps-status ' + (type || '');
        }

        // =========================================
        // FUNGSI UNTUK GPS TRACKING RECORDER
        // =========================================

        // Fungsi untuk memulai perekaman GPS perjalanan
        function startGPSRecording() {
            console.log('🚀 Memulai perekaman GPS perjalanan...');
            
            if (!navigator.geolocation) {
                alert("❌ GPS tidak didukung oleh browser Anda.");
                return;
            }

            const recorderButton = document.getElementById('gpsRecorder');
            const recorderPanel = document.getElementById('recorderPanel');
            const recorderStatus = document.getElementById('recorderStatus');
            
            // Reset data sebelumnya
            gpsRecorder.trackPoints = [];
            gpsRecorder.totalDistance = 0;
            gpsRecorder.averageSpeed = 0;
            gpsRecorder.maxSpeed = 0;
            gpsRecorder.lastPosition = null;
            
            // Update UI
            recorderButton.classList.add('recording');
            recorderButton.title = "Hentikan Rekaman Perjalanan";
            recorderPanel.style.display = 'block';
            recorderStatus.textContent = 'Sedang Merekam...';
            recorderStatus.className = 'recorder-status recording';
            
            gpsRecorder.isRecording = true;
            gpsRecorder.isPaused = false;
            gpsRecorder.trackStartTime = new Date();
            
            updateDrawingStatus('Merekam perjalanan GPS...');

            // Options untuk geolocation
            const geoOptions = {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            };

            // Dapatkan posisi awal
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    console.log('✅ Posisi awal untuk perekaman:', position);
                    addTrackPoint(position);
                    
                    // Mulai interval perekaman
                    gpsRecorder.trackInterval = setInterval(function() {
                        if (gpsRecorder.isRecording && !gpsRecorder.isPaused) {
                            navigator.geolocation.getCurrentPosition(
                                addTrackPoint,
                                handleRecorderError,
                                geoOptions
                            );
                        }
                    }, gpsRecorder.updateFrequency);
                    
                    // Update info setiap detik
                    setInterval(updateRecorderInfo, 1000);
                    
                    // Kirim activity ke server
                    sendUserActivity('gps_recording_started');
                },
                function(error) {
                    console.error('❌ Error mendapatkan posisi awal:', error);
                    handleRecorderError(error);
                },
                geoOptions
            );
        }

        // Fungsi untuk menambahkan titik track
        function addTrackPoint(position) {
            if (!gpsRecorder.isRecording || gpsRecorder.isPaused) return;
            
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            const accuracy = position.coords.accuracy;
            const speed = position.coords.speed || 0;
            const timestamp = new Date();
            
            console.log(`📍 Menambahkan titik track: ${lat}, ${lng}`);
            
            const trackPoint = {
                lat: lat,
                lng: lng,
                accuracy: accuracy,
                speed: speed,
                timestamp: timestamp.toISOString()
            };
            
            // Hitung jarak dari titik sebelumnya
            if (gpsRecorder.lastPosition) {
                const distance = calculateDistance(
                    gpsRecorder.lastPosition.lat, gpsRecorder.lastPosition.lng,
                    lat, lng
                );
                gpsRecorder.totalDistance += distance;
                
                // Update kecepatan
                if (speed > 0) {
                    gpsRecorder.averageSpeed = (gpsRecorder.averageSpeed * (gpsRecorder.trackPoints.length - 1) + speed) / gpsRecorder.trackPoints.length;
                    gpsRecorder.maxSpeed = Math.max(gpsRecorder.maxSpeed, speed);
                }
            }
            
            gpsRecorder.trackPoints.push(trackPoint);
            gpsRecorder.lastPosition = { lat: lat, lng: lng };
            gpsRecorder.lastTimestamp = timestamp;
            
            // Update track line di peta
            updateTrackLine();
            
            // Update info panel
            updateRecorderInfo();
        }

        // Fungsi untuk menghitung jarak antara dua titik (Haversine formula)
        function calculateDistance(lat1, lon1, lat2, lon2) {
            const R = 6371000; // Radius bumi dalam meter
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            
            const a = 
                Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
                Math.sin(dLon/2) * Math.sin(dLon/2);
            
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            const distance = R * c;
            
            return distance;
        }

        // Fungsi untuk memperbarui garis track di peta
        function updateTrackLine() {
            const map = getMap();
            if (!map || gpsRecorder.trackPoints.length < 2) return;
            
            // Buat array koordinat untuk polyline
            const latlngs = gpsRecorder.trackPoints.map(point => [point.lat, point.lng]);
            
            // Hapus track line lama jika ada
            if (gpsRecorder.trackLine) {
                map.removeLayer(gpsRecorder.trackLine);
            }
            
            // Buat track line baru
            gpsRecorder.trackLine = L.polyline(latlngs, {
                color: '#ff6b6b',
                weight: 4,
                opacity: 0.8,
                lineCap: 'round',
                lineJoin: 'round',
                className: 'gps-track-line'
            }).addTo(map);
            
            // Tambahkan popup ke track line
            gpsRecorder.trackLine.bindPopup(createTrackPopupContent());
            
            // Auto-panjangkan view untuk mencakup seluruh track
            map.fitBounds(gpsRecorder.trackLine.getBounds(), { padding: [20, 20] });
        }

        // Fungsi untuk membuat konten popup track
        function createTrackPopupContent() {
            const duration = calculateDuration();
            const distanceKm = (gpsRecorder.totalDistance / 1000).toFixed(2);
            const avgSpeedKmh = (gpsRecorder.averageSpeed * 3.6).toFixed(1);
            const maxSpeedKmh = (gpsRecorder.maxSpeed * 3.6).toFixed(1);
            
            return `
                <div class="track-popup">
                    <h4>📊 Informasi Perjalanan</h4>
                    <div class="track-stats">
                        <div class="stat-item">
                            <span class="stat-label">Jarak Tempuh:</span>
                            <span class="stat-value">${distanceKm} km</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Waktu Tempuh:</span>
                            <span class="stat-value">${duration}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Kecepatan Rata-rata:</span>
                            <span class="stat-value">${avgSpeedKmh} km/jam</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Kecepatan Maksimum:</span>
                            <span class="stat-value">${maxSpeedKmh} km/jam</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Jumlah Titik:</span>
                            <span class="stat-value">${gpsRecorder.trackPoints.length}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Status:</span>
                            <span class="stat-value">${gpsRecorder.isPaused ? 'Dijeda' : 'Aktif'}</span>
                        </div>
                    </div>
                    <div class="track-actions">
                        <button onclick="exportGPSTrack()" class="export-btn" style="background: #28a745; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; margin: 2px;">
                            💾 Ekspor ke SHP
                        </button>
                        <button onclick="clearGPSTrack()" class="delete-btn" style="background: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; margin: 2px;">
                            🗑️ Hapus Track
                        </button>
                    </div>
                </div>
            `;
        }

        // Fungsi untuk menghitung durasi perjalanan
        function calculateDuration() {
            if (!gpsRecorder.trackStartTime) return '00:00:00';
            
            const now = gpsRecorder.isRecording ? new Date() : gpsRecorder.lastTimestamp;
            const diff = Math.floor((now - gpsRecorder.trackStartTime) / 1000);
            
            const hours = Math.floor(diff / 3600);
            const minutes = Math.floor((diff % 3600) / 60);
            const seconds = diff % 60;
            
            return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }

        // Fungsi untuk menghentikan perekaman
        function stopGPSRecording() {
            console.log('🛑 Menghentikan perekaman GPS perjalanan...');
            
            if (gpsRecorder.trackInterval) {
                clearInterval(gpsRecorder.trackInterval);
                gpsRecorder.trackInterval = null;
            }
            
            const recorderButton = document.getElementById('gpsRecorder');
            const recorderStatus = document.getElementById('recorderStatus');
            
            // Update UI
            recorderButton.classList.remove('recording', 'paused');
            recorderButton.title = "Mulai Rekaman Perjalanan";
            recorderStatus.textContent = 'Rekaman Dihentikan';
            recorderStatus.className = 'recorder-status stopped';
            
            gpsRecorder.isRecording = false;
            gpsRecorder.isPaused = false;
            
            updateDrawingStatus('Siap');
            
            // Buka popup track
            if (gpsRecorder.trackLine) {
                gpsRecorder.trackLine.openPopup();
            }
            
            // Kirim activity ke server
            sendUserActivity('gps_recording_stopped');
        }

        // Fungsi untuk menjeda/melanjutkan perekaman
        function togglePauseRecording() {
            if (!gpsRecorder.isRecording) return;
            
            gpsRecorder.isPaused = !gpsRecorder.isPaused;
            
            const recorderButton = document.getElementById('gpsRecorder');
            const recorderStatus = document.getElementById('recorderStatus');
            const pauseButton = document.getElementById('pauseRecording');
            
            if (gpsRecorder.isPaused) {
                recorderButton.classList.add('paused');
                recorderButton.classList.remove('recording');
                recorderStatus.textContent = 'Dijeda';
                recorderStatus.className = 'recorder-status paused';
                pauseButton.textContent = '▶️ Lanjutkan';
                updateDrawingStatus('Rekaman dijeda');
            } else {
                recorderButton.classList.add('recording');
                recorderButton.classList.remove('paused');
                recorderStatus.textContent = 'Sedang Merekam...';
                recorderStatus.className = 'recorder-status recording';
                pauseButton.textContent = '⏸️ Jeda';
                updateDrawingStatus('Merekam perjalanan GPS...');
            }
            
            sendUserActivity(gpsRecorder.isPaused ? 'gps_recording_paused' : 'gps_recording_resumed');
        }

        // Fungsi untuk menangani error perekaman
        function handleRecorderError(error) {
            console.error('🚨 GPS Recorder Error:', error);
            const recorderStatus = document.getElementById('recorderStatus');
            
            const errorMessage = getGPSErrorMessage(error);
            recorderStatus.textContent = 'Error: ' + errorMessage;
            recorderStatus.className = 'recorder-status error';
            
            updateDrawingStatus('Error GPS Recorder');
        }

        // Fungsi untuk memperbarui info recorder
        function updateRecorderInfo() {
            if (!gpsRecorder.isRecording) return;
            
            const duration = calculateDuration();
            const distanceKm = (gpsRecorder.totalDistance / 1000).toFixed(2);
            const pointCount = gpsRecorder.trackPoints.length;
            
            document.getElementById('recorderDuration').textContent = duration;
            document.getElementById('recorderDistance').textContent = distanceKm + ' km';
            document.getElementById('recorderPoints').textContent = pointCount;
            document.getElementById('recorderStatusInfo').textContent = gpsRecorder.isPaused ? 'Dijeda' : 'Merekam';
        }

        // Fungsi untuk mengekspor track GPS ke SHP
        function exportGPSTrack() {
            if (gpsRecorder.trackPoints.length < 2) {
                alert('❌ Tidak ada data track yang cukup untuk diekspor. Minimal 2 titik.');
                return;
            }
            
            console.log('💾 Mengekspor track GPS...');
            
            const trackData = {
                points: gpsRecorder.trackPoints,
                start_time: gpsRecorder.trackStartTime.toISOString(),
                end_time: gpsRecorder.lastTimestamp ? gpsRecorder.lastTimestamp.toISOString() : new Date().toISOString(),
                duration: calculateDuration(),
                total_distance: gpsRecorder.totalDistance,
                average_speed: gpsRecorder.averageSpeed,
                max_speed: gpsRecorder.maxSpeed,
                point_count: gpsRecorder.trackPoints.length
            };
            
            // Tampilkan loading
            showLoading();
            
            // Kirim data ke server
            fetch('/export_gps_track', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    track_data: trackData
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.blob();
            })
            .then(blob => {
                // Buat URL untuk download
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `gps_track_${new Date().getTime()}.zip`;
                
                document.body.appendChild(a);
                a.click();
                
                // Cleanup
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                hideLoading();
                alert('✅ Track GPS berhasil diekspor!');
            })
            .catch(error => {
                console.error('Error exporting GPS track:', error);
                hideLoading();
                alert('❌ Gagal mengekspor track GPS: ' + error.message);
            });
        }

        // Fungsi untuk menghapus track GPS
        function clearGPSTrack() {
            if (confirm('Apakah Anda yakin ingin menghapus track perjalanan ini?')) {
                const map = getMap();
                
                // Hapus track line dari peta
                if (gpsRecorder.trackLine) {
                    map.removeLayer(gpsRecorder.trackLine);
                    gpsRecorder.trackLine = null;
                }
                
                // Reset data recorder
                gpsRecorder.trackPoints = [];
                gpsRecorder.totalDistance = 0;
                gpsRecorder.averageSpeed = 0;
                gpsRecorder.maxSpeed = 0;
                
                // Update UI
                updateRecorderInfo();
                
                alert('Track perjalanan telah dihapus.');
            }
        }

        // Fungsi untuk toggle recorder (start/stop)
        function toggleGPSRecorder() {
            if (!gpsRecorder.isRecording) {
                startGPSRecording();
            } else {
                stopGPSRecording();
            }
        }

        // =========================================
        // FUNGSI TAMBAHAN UNTUK DEBUG GPS DAN PETA
        // =========================================

        // Fungsi untuk mengecek status permission GPS
        function checkGPSPermission() {
            if (!navigator.permissions) {
                console.log('❌ Browser tidak mendukung Permissions API');
                return;
            }
            
            navigator.permissions.query({name: 'geolocation'})
                .then(function(result) {
                    console.log('🔍 Status Permission GPS:', result.state);
                    
                    if (result.state === 'granted') {
                        console.log('✅ Permission GPS sudah diizinkan');
                    } else if (result.state === 'prompt') {
                        console.log('⚠️ Permission GPS menunggu persetujuan');
                    } else if (result.state === 'denied') {
                        console.log('❌ Permission GPS ditolak');
                        alert('❌ Akses GPS ditolak. Silakan izinkan akses lokasi di pengaturan browser Anda.');
                    }
                    
                    // Listen for changes in permission
                    result.onchange = function() {
                        console.log('🔄 Status permission berubah:', this.state);
                    };
                })
                .catch(function(error) {
                    console.error('❌ Error checking GPS permission:', error);
                });
        }

        // Fungsi untuk mendapatkan informasi perangkat GPS
        function getGPSDeviceInfo() {
            console.log('📱 Informasi Perangkat GPS:');
            console.log(' - Geolocation supported:', !!navigator.geolocation);
            console.log(' - HTTPS:', window.location.protocol === 'https:');
            console.log(' - Localhost:', window.location.hostname === 'localhost');
            console.log(' - User Agent:', navigator.userAgent);
        }

        // FUNGSI UNTUK MENDAPATKAN COLLABORATIVE GROUP
        function getCollaborativeGroup() {
            const collaborativeGroupName = """ + json.dumps(collaborative_group_name) + """;
            let collaborativeGroup = window[collaborativeGroupName];
            
            if (!collaborativeGroup) {
                const map = getMap();
                if (map) {
                    map.eachLayer(function(layer) {
                        if (layer instanceof L.FeatureGroup && layer.options && layer.options.name === "Collaborative Drawings") {
                            collaborativeGroup = layer;
                        }
                    });
                }
            }
            return collaborativeGroup;
        }

        // =============================================
        // IMPLEMENTASI UNDO/REDO FUNCTIONALITY
        // =============================================
        let undoStack = [];
        let redoStack = [];
        let maxUndoSteps = 50;

        // Fungsi untuk menyimpan state saat ini ke undo stack
        function saveState() {
            const drawnItems = getDrawnItems();
            if (!drawnItems) return;
            
            const currentState = drawnItems.toGeoJSON();
            undoStack.push(currentState);
            
            // Batasi ukuran undo stack
            if (undoStack.length > maxUndoSteps) {
                undoStack.shift();
            }
            
            // Reset redo stack ketika ada perubahan baru
            redoStack = [];
            
            updateUndoRedoButtons();
        }

        // Fungsi untuk undo
        function undo() {
            if (undoStack.length === 0) return;
            
            const drawnItems = getDrawnItems();
            if (!drawnItems) return;
            
            // Simpan state saat ini ke redo stack
            const currentState = drawnItems.toGeoJSON();
            redoStack.push(currentState);
            
            // Ambil state sebelumnya dari undo stack
            const previousState = undoStack.pop();
            
            // Terapkan state sebelumnya
            drawnItems.clearLayers();
            if (previousState && previousState.features) {
                L.geoJSON(previousState, {
                    onEachFeature: function (feature, layer) {
                        drawnItems.addLayer(layer);
                    }
                });
            }
            
            updateUndoRedoButtons();
            showUndoRedoStatus('Undo berhasil');
        }

        // Fungsi untuk redo
        function redo() {
            if (redoStack.length === 0) return;
            
            const drawnItems = getDrawnItems();
            if (!drawnItems) return;
            
            // Simpan state saat ini ke undo stack
            const currentState = drawnItems.toGeoJSON();
            undoStack.push(currentState);
            
            // Ambil state berikutnya dari redo stack
            const nextState = redoStack.pop();
            
            // Terapkan state berikutnya
            drawnItems.clearLayers();
            if (nextState && nextState.features) {
                L.geoJSON(nextState, {
                    onEachFeature: function (feature, layer) {
                        drawnItems.addLayer(layer);
                    }
                });
            }
            
            updateUndoRedoButtons();
            showUndoRedoStatus('Redo berhasil');
        }

        // Fungsi untuk update status tombol undo/redo
        function updateUndoRedoButtons() {
            const undoButton = document.querySelector('#editDropdown button:nth-child(1)');
            const redoButton = document.querySelector('#editDropdown button:nth-child(2)');
            
            if (undoButton) {
                if (undoStack.length > 0) {
                    undoButton.disabled = false;
                    undoButton.style.color = '';
                    undoButton.textContent = `Undo (Ctrl+Z) - ${undoStack.length}`;
                } else {
                    undoButton.disabled = true;
                    undoButton.style.color = '#888';
                    undoButton.textContent = 'Undo (Ctrl+Z)';
                }
            }
            
            if (redoButton) {
                if (redoStack.length > 0) {
                    redoButton.disabled = false;
                    redoButton.style.color = '';
                    redoButton.textContent = `Redo (Ctrl+Y) - ${redoStack.length}`;
                } else {
                    redoButton.disabled = true;
                    redoButton.style.color = '#888';
                    redoButton.textContent = 'Redo (Ctrl+Y)';
                }
            }
        }

        // Fungsi untuk menampilkan status undo/redo
        function showUndoRedoStatus(message) {
            const statusElement = document.getElementById('undoRedoStatus');
            if (statusElement) {
                statusElement.textContent = message;
                statusElement.style.display = 'block';
                
                setTimeout(() => {
                    statusElement.style.display = 'none';
                }, 2000);
            }
        }

        // Event listener untuk keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl+Z untuk undo
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                if (undoStack.length > 0) {
                    undo();
                }
            }
            // Ctrl+Y atau Ctrl+Shift+Z untuk redo
            else if (((e.ctrlKey || e.metaKey) && e.key === 'y') || 
                     ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'z')) {
                e.preventDefault();
                if (redoStack.length > 0) {
                    redo();
                }
            }
        });

        // FUNGSI DRAG AND DROP YANG DIPERBAIKI
        function initializeDraggable(element) {
            const header = element.querySelector('.results-header') || element;
            
            header.addEventListener('mousedown', startDrag);
            header.addEventListener('touchstart', startDragTouch, { passive: false });
            
            function startDrag(e) {
                if (e.target.classList.contains('close-results')) {
                    return;
                }
                
                e.preventDefault();
                dragState.isDragging = true;
                dragState.currentDraggable = element;
                
                const rect = element.getBoundingClientRect();
                dragState.dragOffset.x = e.clientX - rect.left;
                dragState.dragOffset.y = e.clientY - rect.top;
                dragState.startX = e.clientX;
                dragState.startY = e.clientY;
                
                element.classList.add('dragging');
                
                document.addEventListener('mousemove', onDrag);
                document.addEventListener('mouseup', stopDrag);
            }
            
            function startDragTouch(e) {
                if (e.target.classList.contains('close-results')) {
                    return;
                }
                
                e.preventDefault();
                const touch = e.touches[0];
                dragState.isDragging = true;
                dragState.currentDraggable = element;
                
                const rect = element.getBoundingClientRect();
                dragState.dragOffset.x = touch.clientX - rect.left;
                dragState.dragOffset.y = touch.clientY - rect.top;
                dragState.startX = touch.clientX;
                dragState.startY = touch.clientY;
                
                element.classList.add('dragging');
                
                document.addEventListener('touchmove', onDragTouch, { passive: false });
                document.addEventListener('touchend', stopDrag);
            }
            
            function onDrag(e) {
                if (!dragState.isDragging || dragState.currentDraggable !== element) return;
                
                e.preventDefault();
                
                const x = e.clientX - dragState.dragOffset.x;
                const y = e.clientY - dragState.dragOffset.y;
                
                applyNewPosition(element, x, y);
            }
            
            function onDragTouch(e) {
                if (!dragState.isDragging || dragState.currentDraggable !== element) return;
                
                e.preventDefault();
                const touch = e.touches[0];
                
                const x = touch.clientX - dragState.dragOffset.x;
                const y = touch.clientY - dragState.dragOffset.y;
                
                applyNewPosition(element, x, y);
            }
            
            function stopDrag() {
                if (dragState.isDragging && dragState.currentDraggable === element) {
                    dragState.isDragging = false;
                    dragState.currentDraggable = null;
                    element.classList.remove('dragging');
                    
                    savePanelPosition(element.id, {
                        left: element.style.left,
                        top: element.style.top
                    });
                    
                    document.removeEventListener('mousemove', onDrag);
                    document.removeEventListener('touchmove', onDragTouch);
                    document.removeEventListener('mouseup', stopDrag);
                    document.removeEventListener('touchend', stopDrag);
                }
            }
        }
        
        // FUNGSI UNTUK MENERAPKAN POSISI BARU DENGAN BATASAN
        function applyNewPosition(element, x, y) {
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            const elementWidth = element.offsetWidth;
            const elementHeight = element.offsetHeight;
            
            const boundedX = Math.max(10, Math.min(x, viewportWidth - elementWidth - 10));
            const boundedY = Math.max(10, Math.min(y, viewportHeight - elementHeight - 10));
            
            element.style.left = boundedX + 'px';
            element.style.top = boundedY + 'px';
            element.style.right = 'auto';
            element.style.bottom = 'auto';
        }
        
        // FUNGSI UNTUK MENYIMPAN POSISI PANEL
        function savePanelPosition(panelId, position) {
            try {
                const positions = JSON.parse(localStorage.getItem('panelPositions') || '{}');
                positions[panelId] = position;
                localStorage.setItem('panelPositions', JSON.stringify(positions));
            } catch (e) {
                console.error('Error saving panel position:', e);
            }
        }
        
        // FUNGSI UNTUK MEMUAT POSISI PANEL YANG DISIMPAN
        function loadPanelPosition(panelId, defaultPosition) {
            try {
                const positions = JSON.parse(localStorage.getItem('panelPositions') || '{}');
                const position = positions[panelId];
                const element = document.getElementById(panelId);
                
                if (element && position) {
                    if (position.left && position.top) {
                        element.style.left = position.left;
                        element.style.top = position.top;
                        element.style.right = 'auto';
                        element.style.bottom = 'auto';
                    }
                } else if (element && defaultPosition) {
                    if (defaultPosition.left) element.style.left = defaultPosition.left;
                    if (defaultPosition.top) element.style.top = defaultPosition.top;
                    if (defaultPosition.right) element.style.right = defaultPosition.right;
                    if (defaultPosition.bottom) element.style.bottom = defaultPosition.bottom;
                }
            } catch (e) {
                console.error('Error loading panel position:', e);
            }
        }

        function closeAllMenus(exceptId) {
            for (let i = 0; i < menuItems.length; i++) {
                const item = menuItems[i];
                if (item.id !== exceptId) {
                    document.getElementById(item.id).classList.remove('show-dropdown');
                }
            }
        }
        
        function closeAllSubmenus() {
            const submenus = document.getElementsByClassName('submenu-content');
            for (let i = 0; i < submenus.length; i++) {
                submenus[i].style.display = 'none';
            }
        }

        function toggleMenu(menuName) {
            const id = menuName + 'Dropdown';
            const dropdown = document.getElementById(id);
            
            if (dropdown.classList.contains('show-dropdown')) {
                dropdown.classList.remove('show-dropdown');
                closeAllSubmenus();
            } else {
                closeAllMenus(id);
                dropdown.classList.add('show-dropdown');
            }
        }
        
        function showSubmenu(id) {
            document.getElementById(id).style.display = 'block';
        }
        
        function hideSubmenu(id) {
             setTimeout(() => { 
                 const submenu = document.getElementById(id);
                 if (!submenu.matches(':hover') && !submenu.parentElement.matches(':hover')) {
                     submenu.style.display = 'none';
                 }
             }, 50);
        }

        window.onclick = function(event) {
            const menuBar = document.getElementById('menuBar');
            if (!menuBar.contains(event.target)) {
                closeAllMenus(null);
                closeAllSubmenus();
            }
        }
        
        function getDrawnItems() {
            const drawnItemsName = """ + json.dumps(drawn_items_name) + """;
            let drawnItems = window[drawnItemsName];
            
            if (!drawnItems) {
                const mapName = """ + json.dumps(map_name) + """;
                const mapElement = document.getElementById(mapName);
                if (mapElement && mapElement._leaflet_map) {
                    const leafletMap = mapElement._leaflet_map;
                    leafletMap.eachControl(function(control) {
                        if(control.options && control.options.edit && control.options.edit.featureGroup){
                            drawnItems = control.options.edit.featureGroup;
                        }
                    });
                }
            }
            return drawnItems;
        }
        
        // FUNGSI UNTUK MENDAPATKAN HIGHLIGHT GROUP
        function getHighlightGroup() {
            const highlightGroupName = """ + json.dumps(highlight_group_name) + """;
            let highlightGroup = window[highlightGroupName];
            
            if (!highlightGroup) {
                const mapName = """ + json.dumps(map_name) + """;
                const mapElement = document.getElementById(mapName);
                if (mapElement && mapElement._leaflet_map) {
                    const leafletMap = mapElement._leaflet_map;
                    leafletMap.eachLayer(function(layer) {
                        if(layer instanceof L.FeatureGroup && layer.options && layer.options.name === "Highlighted Polygon") {
                            highlightGroup = layer;
                        }
                    });
                }
            }
            return highlightGroup;
        }
        
        function performExport(format) {
            const drawnItems = getDrawnItems();
            closeAllMenus(null);

            if (!drawnItems || drawnItems.getLayers().length === 0) {
                alert("Harap gambar setidaknya satu fitur untuk diekspor.");
                return;
            }
            
            try {
                const geojson = drawnItems.toGeoJSON();
                
                const form = document.createElement('form');
                form.method = 'POST';
                
                if (format === 'shp') {
                    form.action = """ + json.dumps(url_for('export_to_shp')) + """;
                } else if (format === 'geojson') {
                    form.action = """ + json.dumps(url_for('export_to_geojson')) + """;
                } else {
                    alert("Format export tidak valid.");
                    return;
                }
                
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'geojson_data';
                input.value = JSON.stringify(geojson);
                form.appendChild(input);

                document.body.appendChild(form);
                form.submit();
                document.body.removeChild(form);
                
            } catch (error) {
                console.error("Error creating GeoJSON:", error);
                alert("Error membuat data export: " + error.message);
            }
        }

        // FUNGSI HITUNG LUAS SEMUA POLYGON DENGAN UTM ZONE 52S
        // (Sekarang menggunakan Socket.IO - lihat override di atas)

        // FUNGSI UNTUK MENAMBAHKAN HASIL KE TABEL (TANPA KOLOM METODE)
        function addAreaResult(result) {
            areaResults.push(result);
            updateResultsTable();
        }
        
        // FUNGSI UNTUK UPDATE TABEL HASIL (TANPA KOLOM METODE)
        function updateResultsTable() {
            const tbody = document.getElementById('resultsBody');
            tbody.innerHTML = '';
            
            if (areaResults.length === 0) {
                tbody.innerHTML = '<tr><td colspan=\"5\" class=\"no-results\">Belum ada hasil perhitungan</td></tr>';
                return;
            }
            
            areaResults.forEach((result, index) => {
                const row = document.createElement('tr');
                row.setAttribute('data-result-id', result.id);
                row.innerHTML =
                    '<td>' + result.id + '</td>' +
                    '<td><span class=\"area-value\">' + formatNumberForDisplay(result.area_m2) + '</span></td>' +
                    '<td><span class=\"area-value\">' + result.area_hectare.toFixed(4) + '</span></td>' +
                    '<td><span class=\"area-value\">' + formatKm2(result.area_km2) + '</span></td>' +
                    '<td>' +
                    '<button class=\"zoom-btn\" onclick=\"zoomToPolygon(' + result.id + ', event)\">Zoom</button>' +
                    '<button class=\"export-btn\" onclick=\"exportResult(' + index + ', event)\">Ekspor</button>' +
                    '<button class=\"delete-btn\" onclick=\"deleteResult(' + index + ', event)\">Hapus</button>' +
                    '</td>';
                
                // Tambah event listener untuk klik baris
                row.addEventListener('click', function(e) {
                    // Jangan trigger jika klik pada tombol aksi
                    if (!e.target.classList.contains('export-btn') && 
                        !e.target.classList.contains('delete-btn') &&
                        !e.target.classList.contains('zoom-btn')) {
                        selectPolygon(result.id);
                    }
                });
                
                tbody.appendChild(row);
            });
        }
        
        // FUNGSI UNTUK MEMILIH POLYGON SAAT BARIS DIKLIK
        function selectPolygon(resultId) {
            // Hapus seleksi sebelumnya
            if (currentSelectedRow) {
                currentSelectedRow.classList.remove('selected');
            }
            
            // Set seleksi baru
            const rows = document.querySelectorAll('#resultsBody tr');
            rows.forEach(row => {
                if (parseInt(row.getAttribute('data-result-id')) === resultId) {
                    row.classList.add('selected');
                    currentSelectedRow = row;
                }
            });
            
            // Highlight polygon di peta
            highlightPolygon(resultId);
            
            // Update info panel
            updateSelectedPolygonInfo(resultId);
        }
        
        // FUNGSI UNTUK HIGHLIGHT POLYGON DI PETA
        function highlightPolygon(resultId) {
            const layer = polygonLayers.get(resultId);
            const highlightGroup = getHighlightGroup();
            
            if (!layer || !highlightGroup) {
                console.error('Layer atau highlight group tidak ditemukan');
                return;
            }
            
            // Hapus highlight sebelumnya
            clearHighlight();
            
            // Buat salinan layer dengan style highlight
            const geojson = layer.toGeoJSON();
            const highlightLayer = L.geoJSON(geojson, {
                style: {
                    color: '#ff0000',
                    weight: 4,
                    opacity: 1,
                    fillColor: '#ffff00',
                    fillOpacity: 0.3
                },
                className: 'highlight-polygon'
            });
            
            // Tambahkan ke highlight group
            highlightGroup.addLayer(highlightLayer);
            currentHighlightLayer = highlightLayer;
            
            // Zoom ke polygon yang dipilih
            const map = getMap();
            map.fitBounds(highlightLayer.getBounds());
        }
        
        // FUNGSI UNTUK ZOOM KE POLYGON
        function zoomToPolygon(resultId, event) {
            if (event) event.stopPropagation();
            
            const layer = polygonLayers.get(resultId);
            if (layer) {
                const map = getMap();
                map.fitBounds(layer.getBounds());
                selectPolygon(resultId); // Juga select polygon tersebut
            }
        }
        
        // FUNGSI UNTUK MENGHAPUS HIGHLIGHT
        function clearHighlight() {
            if (currentHighlightLayer) {
                const highlightGroup = getHighlightGroup();
                if (highlightGroup) {
                    highlightGroup.removeLayer(currentHighlightLayer);
                }
                currentHighlightLayer = null;
            }
            
            // Hapus seleksi baris
            if (currentSelectedRow) {
                currentSelectedRow.classList.remove('selected');
                currentSelectedRow = null;
            }
            
            // Update info panel
            updateSelectedPolygonInfo(null);
        }
        
        // FUNGSI UNTUK UPDATE INFO POLYGON TERPILIH
        function updateSelectedPolygonInfo(resultId) {
            const selectedPolygonElement = document.getElementById('selectedPolygon');
            if (resultId) {
                selectedPolygonElement.textContent = 'ID: ' + resultId;
                selectedPolygonElement.style.color = '#28a745';
                selectedPolygonElement.style.fontWeight = 'bold';
            } else {
                selectedPolygonElement.textContent = 'Tidak ada';
                selectedPolygonElement.style.color = '#6c757d';
                selectedPolygonElement.style.fontWeight = 'normal';
            }
        }
        
        // FUNGSI UNTUK MENAMPILKAN TABEL HASIL
        function showResultsTable() {
            const resultsContainer = document.getElementById('resultsContainer');
            resultsContainer.style.display = 'block';
            updateResultsTable();
            
            // Inisialisasi drag functionality
            initializeDraggable(resultsContainer);
            loadPanelPosition('resultsContainer', { 
                left: 'auto', 
                top: '100px', 
                right: '20px', 
                bottom: 'auto' 
            });
            
            ensureElementInViewport(resultsContainer);
        }
        
        // FUNGSI UNTUK MENYEMBUNYIKAN TABEL HASIL
        function hideResultsTable() {
            document.getElementById('resultsContainer').style.display = 'none';
        }
        
        // FUNGSI BARU: HAPUS SEMUA HASIL
        function clearAllResults() {
            if (areaResults.length === 0) {
                alert("Tidak ada hasil yang bisa dihapus.");
                return;
            }
            
            if (confirm('Apakah Anda yakin ingin menghapus semua ' + areaResults.length + ' hasil perhitungan?')) {
                areaResults = [];
                polygonLayers.clear();
                clearHighlight();
                updateResultsTable();
                alert("Semua hasil perhitungan telah dihapus.");
            }
        }
        
        // FUNGSI UNTUK EKSPOR HASIL
        function exportResult(index, event) {
            if (event) event.stopPropagation();
            
            const result = areaResults[index];
            const data = 'HASIL PERHITUNGAN LUAS POLYGON\\n' +
                        '===============================\\n' +
                        'ID: ' + result.id + '\\n' +
                        'Luas (m²): ' + formatNumberForDisplay(result.area_m2) + '\\n' +
                        'Luas (hektar): ' + result.area_hectare.toFixed(4) + '\\n' +
                        'Luas (km²): ' + formatKm2(result.area_km2) + '\\n' +
                        'Metode: ' + result.method + '\\n' +
                        'UTM Zone: ' + result.utm_zone + '\\n' +
                        'Waktu: ' + result.timestamp + '\\n' +
                        '===============================';
            
            const blob = new Blob([data], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'luas_polygon_' + result.id + '_utm_' + result.utm_zone + '.txt';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
        
        // FUNGSI UNTUK MENGHAPUS HASIL
        function deleteResult(index, event) {
            if (event) event.stopPropagation();
            
            const result = areaResults[index];
            if (confirm('Hapus hasil perhitungan ID ' + result.id + '?')) {
                // Hapus dari polygonLayers map
                polygonLayers.delete(result.id);
                
                // Hapus dari array results
                areaResults.splice(index, 1);
                
                // Jika yang dihapus adalah yang sedang dipilih, clear highlight
                if (currentSelectedRow && parseInt(currentSelectedRow.getAttribute('data-result-id')) === result.id) {
                    clearHighlight();
                }
                
                updateResultsTable();
            }
        }
        
        // FUNGSI LOADING
        function showLoading() {
            document.getElementById('loadingIndicator').style.display = 'block';
        }
        
        function hideLoading() {
            document.getElementById('loadingIndicator').style.display = 'none';
        }
        
        // FUNGSI UNTUK UPDATE STATUS DI INFO PANEL
        function updateDrawingStatus(status) {
            const statusElement = document.getElementById('drawingStatus');
            if (statusElement) {
                statusElement.textContent = status;
                
                if (status === 'Siap') {
                    statusElement.style.color = '#28a745';
                } else if (status === 'Menghitung luas semua polygon...') {
                    statusElement.style.color = '#ffc107';
                } else if (status === 'Error') {
                    statusElement.style.color = '#dc3545';
                } else {
                    statusElement.style.color = '#6c757d';
                }
            }
        }
        
        // FUNGSI UNTUK MEMASTIKAN ELEMEN TIDAK KELUAR DARI VIEWPORT
        function ensureElementInViewport(element) {
            const rect = element.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            
            if (rect.right > viewportWidth || rect.bottom > viewportHeight || rect.left < 0 || rect.top < 0) {
                element.style.left = 'auto';
                element.style.top = '100px';
                element.style.right = '20px';
                element.style.bottom = 'auto';
            }
        }

        // =========================================
        // INISIALISASI APLIKASI - DIPERBAIKI
        // =========================================

        window.onload = function() {
            console.log('🚀 Window loaded, mencari peta...');
            
            const mapName = """ + json.dumps(map_name) + """;
            const mapElement = document.getElementById(mapName);
            
            if (mapElement && mapElement._leaflet_map) {
                console.log('✅ Peta ditemukan segera setelah window.load');
                window.mapReady = true;
            } else {
                console.log('⏳ Peta belum siap, menunggu...');
                window.mapReady = false;
            }
            
            // Tunggu sebentar untuk memastikan peta siap
            setTimeout(function() {
                const map = getMap();
                if (map) {
                    console.log('✅ Peta siap digunakan setelah delay:', map);
                    window.mapReady = true;
                    updateDrawingStatus('Siap');
                } else {
                    console.error('❌ Peta masih tidak ditemukan setelah delay');
                    updateDrawingStatus('Error - Peta Tidak Ditemukan');
                }
                
                // Tampilkan menu bar
                if (getDrawnItems()) {
                    document.getElementById('menuBar').style.display = 'flex';
                }
                
                // Inisialisasi drag functionality untuk info panel
                const infoPanel = document.getElementById('infoPanel');
                if (infoPanel) {
                    initializeDraggable(infoPanel);
                    loadPanelPosition('infoPanel', { 
                        left: '20px', 
                        top: 'auto', 
                        right: 'auto', 
                        bottom: '20px' 
                    });
                }
                
                // PERBAIKAN: Inisialisasi drag functionality untuk user status
                const userStatus = document.getElementById('userStatus');
                if (userStatus) {
                    initializeDraggable(userStatus);
                    loadPanelPosition('userStatus', { 
                        left: 'auto', 
                        top: '5px', 
                        right: '5px', 
                        bottom: 'auto' 
                    });
                }
                
                // Inisialisasi drag functionality untuk info panel GPS
                const gpsInfo = document.getElementById('gpsInfo');
                if (gpsInfo) {
                    initializeDraggable(gpsInfo);
                    loadPanelPosition('gpsInfo', { 
                        left: '20px', 
                        top: '120px', 
                        right: 'auto', 
                        bottom: 'auto' 
                    });
                }
                
                // Inisialisasi drag functionality untuk recorder panel
                const recorderPanel = document.getElementById('recorderPanel');
                if (recorderPanel) {
                    initializeDraggable(recorderPanel);
                    loadPanelPosition('recorderPanel', { 
                        left: '20px', 
                        top: '200px', 
                        right: 'auto', 
                        bottom: 'auto' 
                    });
                }
                
                // Event listener untuk tombol GPS - DIPERBAIKI
                const gpsButton = document.getElementById('gpsButton');
                if (gpsButton) {
                    gpsButton.addEventListener('click', function() {
                        if (isGPSTracking) {
                            stopGPSTracking();
                        } else {
                            startGPSTracking();
                        }
                    });
                } else {
                    console.error('❌ Tombol GPS tidak ditemukan');
                }
                
                // Event listener untuk tombol GPS Recorder
                const gpsRecorderBtn = document.getElementById('gpsRecorder');
                if (gpsRecorderBtn) {
                    gpsRecorderBtn.addEventListener('click', function() {
                        toggleGPSRecorder();
                    });
                }
                
                // Panggil fungsi debug
                console.log('🚀 Aplikasi dimuat, memeriksa GPS...');
                checkGPSPermission();
                getGPSDeviceInfo();
                
                // Simpan state awal untuk undo/redo
                saveState();
                updateUndoRedoButtons();
                
            }, 1000); // Tunggu 1 detik untuk memastikan peta siap

            // LOGIKA PERHITUNGAN PANJANG DENGAN TURF.JS
            // Tunggu sampai peta benar-benar siap
            setTimeout(function() {
                const map = getMap();
                if (map) {
                    map.on(L.Draw.Event.CREATED, function (e) {
                        const layer = e.layer;
                        const type = String(e.layerType || '').toLowerCase(); 
                        
                        if (!type) {
                            getDrawnItems().addLayer(layer);
                            return;
                        }

                        let popupContent = '<h4>Hasil Pengukuran</h4>';
                        
                        try {
                            const geojsonFeature = layer.toGeoJSON();

                            if (type === 'polyline') {
                                const lengthKm = turf.length(geojsonFeature, {units: 'kilometers'});
                                const lengthM = lengthKm * 1000;

                                popupContent +=
                                    '<p>Tipe: Garis</p>' +
                                    '<p>Panjang: <b>' + formatNumber(lengthM) + '</b> meter</p>' +
                                    '<p>Panjang: <b>' + formatNumber(lengthKm) + '</b> km</p>';
                            } else if (type === 'circle') {
                                const radiusM = layer.getRadius();
                                const radiusKm = radiusM / 1000;
                                
                                popupContent +=
                                    '<p>Tipe: Circle</p>' +
                                    '<p>Radius: <b>' + formatNumber(radiusM) + '</b> meter</p>' +
                                    '<p>Radius: <b>' + formatNumber(radiusKm) + '</b> km</p>';
                            } else if (type === 'marker') {
                                popupContent += '<p>Tipe: Titik</p><p>Koordinat: ' + layer.getLatLng().lat.toFixed(6) + ', ' + layer.getLatLng().lng.toFixed(6) + '</p>';
                            } else {
                                const displayType = type.charAt(0).toUpperCase() + type.slice(1);
                                popupContent += '<p>Tipe: ' + displayType + '</p>';
                            }

                            layer.bindPopup(popupContent).openPopup();

                        } catch (e) {
                            console.error("Error calculating geometry or binding popup:", e);
                            layer.bindPopup('Error saat menghitung geometri: ' + e.message).openPopup();
                        }
                        
                        getDrawnItems().addLayer(layer);
                        
                        // Kirim ke server untuk collaborative mode
                        if (collaborativeMode) {
                            socket.emit('collaborative_drawing', {
                                geometry: layer.toGeoJSON(),
                                type: type,
                                style: {
                                    color: '#ff6b6b',
                                    weight: 3
                                },
                                broadcast: true
                            });
                        }
                        
                        // Kirim activity
                        sendUserActivity('drawing_created');
                        
                        // Simpan state setelah membuat layer baru
                        saveState();
                    });

                    // Simpan state untuk event edit dan delete
                    map.on(L.Draw.Event.EDITED, function (e) {
                        saveState();
                    });

                    map.on(L.Draw.Event.DELETED, function (e) {
                        saveState();
                    });
                } else {
                    console.error('❌ Tidak dapat menambahkan event listener ke peta karena peta tidak ditemukan');
                }
            }, 1500); // Tunggu 1.5 detik untuk memastikan peta dan draw control siap
        };
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logging.info(f"Starting application on port {port}")
    
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

    # Jalankan aplikasi dengan Socket.IO
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=port, 
        debug=debug,
        allow_unsafe_werkzeug=True
    )