"""
Conexión a base de datos MySQL.
"""
import mysql.connector
from mysql.connector import pooling
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG

# Pool de conexiones
_connection_pool = None


def get_connection_pool():
    """Obtiene o crea el pool de conexiones."""
    global _connection_pool
    
    if _connection_pool is None:
        try:
            _connection_pool = pooling.MySQLConnectionPool(
                pool_name="gestion_pool",
                pool_size=5,
                **DB_CONFIG
            )
        except mysql.connector.Error as err:
            print(f"Error creando pool de conexiones: {err}")
            raise
    
    return _connection_pool


def get_connection():
    """Obtiene una conexión del pool."""
    pool = get_connection_pool()
    return pool.get_connection()


def init_database():
    """
    Inicializa la base de datos creando las tablas necesarias.
    """
    # Primero conectar sin especificar database para crearla si no existe
    config_sin_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    
    try:
        conn = mysql.connector.connect(**config_sin_db)
        cursor = conn.cursor()
        
        # Crear base de datos si no existe
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(f"USE {DB_CONFIG['database']}")
        
        # Crear tablas
        crear_tablas(cursor)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Base de datos '{DB_CONFIG['database']}' inicializada correctamente")
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ Error inicializando base de datos: {err}")
        return False


def crear_tablas(cursor):
    """Crea las tablas necesarias."""
    
    # Tabla de períodos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS periodos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            anio INT NOT NULL,
            mes INT NOT NULL,
            fecha_inicio DATE,
            fecha_fin DATE,
            cerrado BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_periodo (anio, mes)
        ) ENGINE=InnoDB
    """)
    
    # Tabla de movimientos bancarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_bancarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            periodo_id INT,
            banco VARCHAR(50) NOT NULL,
            fecha DATE NOT NULL,
            descripcion VARCHAR(500),
            referencia VARCHAR(100),
            categoria VARCHAR(100),
            tipo VARCHAR(50),
            debito DECIMAL(15,2) DEFAULT 0,
            credito DECIMAL(15,2) DEFAULT 0,
            saldo DECIMAL(15,2),
            es_traspaso_interno BOOLEAN DEFAULT FALSE,
            hash_movimiento VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (periodo_id) REFERENCES periodos(id),
            INDEX idx_fecha (fecha),
            INDEX idx_periodo (periodo_id),
            INDEX idx_hash (hash_movimiento)
        ) ENGINE=InnoDB
    """)
    
    # Tabla de ventas mensuales
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas_mensuales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            periodo_id INT,
            fecha DATE NOT NULL,
            venta_pesos DECIMAL(15,2),
            venta_kgs DECIMAL(10,2),
            sucursal VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (periodo_id) REFERENCES periodos(id),
            INDEX idx_fecha (fecha),
            INDEX idx_periodo (periodo_id)
        ) ENGINE=InnoDB
    """)
    
    # Tabla de pagos en efectivo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos_efectivo (
            id INT AUTO_INCREMENT PRIMARY KEY,
            periodo_id INT,
            fecha DATE NOT NULL,
            concepto VARCHAR(500),
            monto DECIMAL(15,2),
            categoria VARCHAR(100),
            hash_pago VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (periodo_id) REFERENCES periodos(id),
            INDEX idx_fecha (fecha),
            INDEX idx_periodo (periodo_id),
            INDEX idx_hash (hash_pago)
        ) ENGINE=InnoDB
    """)
    
    print("  → Tablas creadas/verificadas")


def test_connection():
    """Prueba la conexión a la base de datos."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error de conexión: {e}")
        return False
