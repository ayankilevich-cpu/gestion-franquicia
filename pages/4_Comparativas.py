"""
Página de Comparativas entre Períodos.
Permite comparar el desempeño entre diferentes meses/años.

EERR Operativo:
- Ingresos = Ventas del período
- Egresos = Gastos bancarios + Pagos en efectivo
"""
import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NOMBRE_EMPRESA
from utils.formato import formato_moneda, formato_porcentaje, formato_df_moneda, formato_df_porcentaje, formato_numero
from utils.charts import grafico_barras_agrupadas_moneda

st.set_page_config(page_title="Comparativas", page_icon="📉", layout="wide")

# CSS para ajustar tamaño de métricas (números grandes)
st.markdown("""
<style>
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

st.title("📉 Comparativas entre Períodos")
st.markdown(f"**{NOMBRE_EMPRESA}** - Análisis de variaciones")

try:
    from db.queries import obtener_periodos, obtener_comparativa_periodos
    
    # Obtener períodos disponibles
    periodos = obtener_periodos()
    
    if not periodos or len(periodos) < 2:
        st.info("📭 Se necesitan al menos 2 períodos para comparar. Cargá más datos.")
        st.stop()
    
    # Selector de períodos a comparar
    opciones_periodo = {
        f"{p['mes']:02d}/{p['anio']}": p['id']
        for p in periodos
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        periodo1_label = st.selectbox(
            "Período 1 (Base):",
            options=list(opciones_periodo.keys()),
            index=1 if len(opciones_periodo) > 1 else 0
        )
    
    with col2:
        periodo2_label = st.selectbox(
            "Período 2 (Comparar):",
            options=list(opciones_periodo.keys()),
            index=0
        )
    
    if periodo1_label == periodo2_label:
        st.warning("⚠️ Seleccioná períodos diferentes para comparar")
        st.stop()
    
    # Obtener datos comparativos
    periodos_ids = [opciones_periodo[periodo1_label], opciones_periodo[periodo2_label]]
    datos = obtener_comparativa_periodos(periodos_ids)
    
    if len(datos) < 2:
        st.error("No se pudieron obtener datos de ambos períodos")
        st.stop()
    
    p1 = datos[0]  # Base
    p2 = datos[1]  # Comparar
    
    st.markdown("---")
    
    # =========================================
    # COMPARATIVA DE MÉTRICAS PRINCIPALES
    # =========================================
    st.subheader("📊 Comparativa Operativa")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        var_ventas = ((p2['ventas'] - p1['ventas']) / p1['ventas'] * 100) if p1['ventas'] > 0 else (100 if p2['ventas'] > 0 else 0)
        st.metric(
            "Ventas",
            formato_moneda(p2['ventas'], decimales=0),
            delta=f"{var_ventas:+.1f}% vs {periodo1_label}".replace(".", ",")
        )
    
    with col2:
        var_egresos = ((p2['egresos'] - p1['egresos']) / p1['egresos'] * 100) if p1['egresos'] > 0 else (100 if p2['egresos'] > 0 else 0)
        st.metric(
            "Egresos Totales",
            formato_moneda(p2['egresos'], decimales=0),
            delta=f"{var_egresos:+.1f}% vs {periodo1_label}".replace(".", ","),
            delta_color="inverse"  # Menor es mejor para egresos
        )
    
    with col3:
        var_resultado = p2['resultado'] - p1['resultado']
        st.metric(
            "Resultado Operativo",
            formato_moneda(p2['resultado'], decimales=0),
            delta=f"{formato_moneda(var_resultado, 0)} vs {periodo1_label}"
        )
    
    with col4:
        var_margen = p2['margen'] - p1['margen']
        st.metric(
            "Margen Operativo",
            formato_porcentaje(p2['margen']),
            delta=f"{var_margen:+.1f}pp vs {periodo1_label}".replace(".", ",")
        )
    
    # Alertas si no hay ventas
    if p1['ventas'] == 0 or p2['ventas'] == 0:
        st.warning("⚠️ Uno o ambos períodos no tienen ventas cargadas. La comparativa puede no reflejar la situación real.")
    
    st.markdown("---")
    
    # =========================================
    # TABLA COMPARATIVA DETALLADA
    # =========================================
    st.subheader("📋 Comparativa de Egresos por Categoría")
    
    # Combinar todas las categorías de egresos
    todas_categorias_egr = set(p1['egresos'].keys()) | set(p2['egresos'].keys())
    
    data_egresos = []
    for cat in sorted(todas_categorias_egr):
        val1 = p1['egresos'].get(cat, 0)
        val2 = p2['egresos'].get(cat, 0)
        var = ((val2 - val1) / val1 * 100) if val1 > 0 else (100 if val2 > 0 else 0)
        data_egresos.append({
            'Categoría': cat,
            periodo1_label: val1,
            periodo2_label: val2,
            'Variación $': val2 - val1,
            'Variación %': var
        })
    
    if data_egresos:
        df_egr = pd.DataFrame(data_egresos)
        
        # Agregar fila de totales
        total_row = pd.DataFrame([{
            'Categoría': 'TOTAL EGRESOS',
            periodo1_label: p1['egresos'] if isinstance(p1['egresos'], (int, float)) else sum(p1['egresos'].values()),
            periodo2_label: p2['egresos'] if isinstance(p2['egresos'], (int, float)) else sum(p2['egresos'].values()),
            'Variación $': sum(p2['egresos'].values()) - sum(p1['egresos'].values()) if isinstance(p1['egresos'], dict) else 0,
            'Variación %': var_egresos
        }])
        df_egr = pd.concat([df_egr, total_row], ignore_index=True)
        
        def formato_variacion_moneda(x):
            if x >= 0:
                return "+" + formato_moneda(x)
            else:
                return formato_moneda(x)
        
        def formato_variacion_pct(x):
            signo = "+" if x >= 0 else ""
            return f"{signo}{x:.1f}%".replace(".", ",")
        
        st.dataframe(
            df_egr.style.format({
                periodo1_label: formato_df_moneda,
                periodo2_label: formato_df_moneda,
                'Variación $': formato_variacion_moneda,
                'Variación %': formato_variacion_pct
            }),
            use_container_width=True,
            hide_index=True
        )
    
    # =========================================
    # GRÁFICO COMPARATIVO
    # =========================================
    st.markdown("---")
    st.subheader("📊 Gráfico Comparativo")
    
    df_chart = pd.DataFrame({
        'Concepto': ['Ventas', 'Egresos', 'Resultado'],
        periodo1_label: [p1['ventas'], p1['egresos'], p1['resultado']],
        periodo2_label: [p2['ventas'], p2['egresos'], p2['resultado']]
    })
    st.caption("Montos en tooltip con **$** y separador de miles.")
    grafico_barras_agrupadas_moneda(
        df_chart, 'Concepto', [periodo1_label, periodo2_label], titulo='Comparativa por concepto'
    )
    
    # =========================================
    # RESUMEN DE VARIACIONES
    # =========================================
    st.markdown("---")
    st.subheader("📈 Resumen de Variaciones")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**{periodo1_label} (Base)**")
        st.write(f"- Ventas: {formato_moneda(p1['ventas'])}")
        st.write(f"- Egresos: {formato_moneda(p1['egresos'])}")
        st.write(f"- Resultado: {formato_moneda(p1['resultado'])}")
        st.write(f"- Margen: {formato_porcentaje(p1['margen'])}")
    
    with col2:
        st.markdown(f"**{periodo2_label} (Comparar)**")
        st.write(f"- Ventas: {formato_moneda(p2['ventas'])}")
        st.write(f"- Egresos: {formato_moneda(p2['egresos'])}")
        st.write(f"- Resultado: {formato_moneda(p2['resultado'])}")
        st.write(f"- Margen: {formato_porcentaje(p2['margen'])}")

except ImportError as e:
    st.error(f"Error de importación: {str(e)}")
except Exception as e:
    st.error(f"Error: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
