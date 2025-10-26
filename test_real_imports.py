#!/usr/bin/env python3
"""
Test REAL Package Imports - Bukan built-in modules
"""

def test_core_packages():
    print("🧪 TESTING REAL PACKAGE IMPORTS")
    print("=" * 50)
    
    # Package yang PERLU diinstall via conda/pip
    packages_to_test = [
        # === FLASK & WEB ===
        ("Flask", "flask"),
        ("Flask-SocketIO", "flask_socketio"), 
        ("Flask-SQLAlchemy", "flask_sqlalchemy"),
        ("Flask-CORS", "flask_cors"),
        
        # === DATABASE ===
        ("PostgreSQL Driver", "psycopg2"),
        ("MySQL Driver", "pymysql"),
        ("Redis", "redis"),
        
        # === GIS & MAPPING ===
        ("Shapely", "shapely"),
        ("Folium", "folium"),
        ("PyProj", "pyproj"),
        ("GeoPandas", "geopandas"),
        
        # === REAL-TIME ===
        ("Eventlet", "eventlet"),
        ("Gunicorn", "gunicorn"),
        
        # === UTILITIES ===
        ("Python Dotenv", "dotenv"),
    ]
    
    success_count = 0
    total_count = len(packages_to_test)
    
    for package_name, import_name in packages_to_test:
        try:
            __import__(import_name)
            print(f"✅ {package_name:20} - INSTALLED")
            success_count += 1
        except ImportError as e:
            print(f"❌ {package_name:20} - MISSING: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTS: {success_count}/{total_count} packages installed")
    
    if success_count == total_count:
        print("🎉 SEMUA PACKAGE TERINSTALL DENGAN BAIK!")
    else:
        print(f"⚠️  {total_count - success_count} package BELUM TERINSTALL")
        print("💡 Jalankan perintah instalasi yang diberikan di atas")

if __name__ == "__main__":
    test_core_packages()