"""
Sistema de Gestión Financiera - EERR
Aplicación principal Streamlit con navegación multi-página.

Ejecutar con: streamlit run app.py
"""
import streamlit as st
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NOMBRE_EMPRESA, CUIT_EMPRESA, SUCURSAL
from utils.formato import formato_moneda, formato_porcentaje

# Configuración de la página
st.set_page_config(
    page_title=f"Gestión Financiera - {NOMBRE_EMPRESA}",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    /* Ajustar tamaño de métricas para números de 9+ dígitos */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar con información de la empresa
with st.sidebar:
    st.image("https://via.placeholder.com/150x50?text=Logo", width=150)
    st.markdown(f"### {NOMBRE_EMPRESA}")
    st.caption(f"CUIT: {CUIT_EMPRESA}")
    st.caption(f"Sucursal: {SUCURSAL}")
    st.markdown("---")

# Página principal
st.markdown('<p class="main-header">📊 Sistema de Gestión Financiera</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-header">{NOMBRE_EMPRESA} - Estado de Resultados y Flujo de Caja</p>', unsafe_allow_html=True)

# ===========================================
# SECCIÓN DE CONEXIÓN A BASE DE DATOS
# ===========================================
st.subheader("🔌 Conexión a Base de Datos")

col_db1, col_db2, col_db3 = st.columns([1, 1, 2])

# Estado de conexión
from db.connection import test_connection, init_database, get_connection

conexion_ok = False

with col_db1:
    if st.button("🔗 Verificar Conexión", use_container_width=True):
        try:
            if test_connection():
                st.success("✅ Conectado")
                conexion_ok = True
            else:
                st.error("❌ Sin conexión")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

with col_db2:
    if st.button("🔄 Sincronizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with col_db3:
    # Mostrar estado actual
    try:
        if test_connection():
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Contar registros
            cursor.execute("SELECT COUNT(*) as total FROM movimientos_bancarios")
            total_mov = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM movimientos_bancarios WHERE banco = 'MANUAL'")
            total_manual = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM ventas_mensuales")
            total_ventas = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM periodos")
            total_periodos = cursor.fetchone()['total']
            
            cursor.close()
            conn.close()
            
            st.success(f"✅ MySQL: {total_mov} movimientos ({total_manual} manuales) | {total_ventas} ventas | {total_periodos} períodos")
            conexion_ok = True
        else:
            st.warning("⚠️ No conectado a MySQL")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

# Mostrar ayuda si no hay conexión
if not conexion_ok:
    with st.expander("❓ ¿Problemas de conexión?"):
        st.markdown("""
        **Verificá que:**
        1. Tu base MySQL sea accesible desde internet (si estás en la nube)
        2. Las credenciales estén cargadas en `st.secrets` o en `.env`:
        """)
        st.code("""
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=tu_password
MYSQL_DATABASE=gestion_franquicia
        """)
        st.caption("En Streamlit Community Cloud configurá estas variables en Settings > Secrets.")
        
        if st.button("🔧 Inicializar Base de Datos"):
            try:
                if init_database():
                    st.success("✅ Base de datos inicializada")
                    st.rerun()
                else:
                    st.error("❌ No se pudo inicializar")
            except Exception as e:
                st.error(f"Error: {str(e)}")

st.markdown("---")

# Resumen rápido
st.subheader("🏠 Panel Principal")

col1, col2, col3, col4 = st.columns(4)

# Intentar obtener datos de resumen
try:
    from db.queries import obtener_periodos, obtener_eerr_operativo
    
    periodos = obtener_periodos()
    
    if periodos:
        ultimo_periodo = periodos[0]
        eerr = obtener_eerr_operativo(periodo_id=ultimo_periodo['id'])
        
        with col1:
            st.metric(
                "Último Período",
                f"{ultimo_periodo['mes']:02d}/{ultimo_periodo['anio']}"
            )
        
        with col2:
            st.metric(
                "Ventas",
                formato_moneda(eerr['ventas_pesos'], decimales=0),
                help="Total de ventas del período"
            )
        
        with col3:
            st.metric(
                "Egresos",
                formato_moneda(eerr['total_egresos'], decimales=0),
                help="Gastos bancarios + Pagos en efectivo"
            )
        
        with col4:
            resultado = eerr['resultado_operativo']
            st.metric(
                "Resultado Operativo",
                formato_moneda(resultado, decimales=0),
                delta=formato_porcentaje(eerr['margen_operativo']) + " margen" if eerr['ventas_pesos'] > 0 else None
            )
        
        # Alerta si no hay ventas cargadas
        if eerr['ventas_pesos'] == 0:
            st.warning("⚠️ No hay ventas cargadas para el último período. Usá 'Carga Manual' para registrar las ventas.")
    else:
        st.info("📭 No hay datos cargados. Usá la página 'Cargar Datos' para comenzar.")
        
except Exception as e:
    st.info("📊 Cargá datos para ver el resumen")

st.markdown("---")

# Navegación
st.subheader("📂 Navegación")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    ### 📥 Cargar Datos
    - Subir extractos bancarios (PDF)
    - Cargar ventas (Excel/CSV)
    - Cargar pagos en efectivo
    
    **Ir a:** `pages/1_Cargar_Datos.py`
    """)
    
    st.markdown("""
    ### 📊 EERR Mensual
    - Estado de Resultados por mes
    - Detalle de movimientos
    - Exportar a Excel
    
    **Ir a:** `pages/2_EERR_Mensual.py`
    """)

with col2:
    st.markdown("""
    ### 📈 Análisis Anual
    - Evolución mensual
    - Comparativa ventas vs egresos
    - Tendencias
    
    **Ir a:** `pages/3_Analisis_Anual.py`
    """)
    
    st.markdown("""
    ### ✏️ Carga Manual
    - Agregar gastos manuales
    - Cargar ventas mensuales
    - Registrar pagos en efectivo
    
    **Ir a:** `pages/6_Carga_Manual.py`
    """)
    
    st.markdown("""
    ### 📉 Comparativas
    - Comparar períodos
    - Análisis de variaciones
    - Proyecciones
    
    **Ir a:** `pages/4_Comparativas.py`
    """)

st.markdown("---")

# Footer
st.caption("💻 Sistema de Gestión Financiera v2.0 - Desarrollado para gestión de franquicia Grido")
