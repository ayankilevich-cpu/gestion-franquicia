"""
Página de Análisis Anual.
Muestra evolución y tendencias a lo largo del año.

EERR Operativo:
- Ingresos = Ventas del período
- Egresos = Gastos bancarios + Pagos en efectivo
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NOMBRE_EMPRESA
from utils.formato import formato_moneda, formato_numero, formato_porcentaje, formato_df_moneda, formato_df_porcentaje
from utils.charts import (
    grafico_lineas_multiserie_moneda,
    grafico_barras_desde_serie,
    grafico_barras_apiladas_mes_moneda,
)

st.set_page_config(page_title="Análisis Anual", page_icon="📈", layout="wide")

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

st.title("📈 Análisis Anual")
st.markdown(f"**{NOMBRE_EMPRESA}** - Evolución y tendencias")

try:
    from db.queries import obtener_periodos, obtener_resumen_anual
    
    # Obtener años disponibles
    periodos = obtener_periodos()
    
    if not periodos:
        st.info("📭 No hay datos cargados. Usá la página 'Cargar Datos' para comenzar.")
        st.stop()
    
    anios_disponibles = sorted(set(p['anio'] for p in periodos), reverse=True)
    
    # Selector de año
    anio_seleccionado = st.selectbox(
        "Seleccionar Año:",
        options=anios_disponibles
    )
    
    # Obtener resumen anual
    resumen = obtener_resumen_anual(anio_seleccionado)
    
    st.markdown("---")
    
    # =========================================
    # MÉTRICAS ANUALES
    # =========================================
    st.subheader("💰 Resumen Operativo Anual")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            f"Ventas {anio_seleccionado}",
            formato_moneda(resumen['total_ventas_pesos'], decimales=0),
            help="Total de ventas del año"
        )
        if resumen['total_ventas_kgs'] > 0:
            st.caption(f"📦 {resumen['total_ventas_kgs']:,.0f} kg")
    
    with col2:
        st.metric(
            f"Egresos {anio_seleccionado}",
            formato_moneda(resumen['total_egresos'], decimales=0),
            help="Gastos bancarios + Pagos en efectivo"
        )
        st.caption(f"Bancarios: {formato_moneda(resumen['total_egresos_bancarios'], 0)} | Efectivo: {formato_moneda(resumen['total_egresos_efectivo'], 0)}")
    
    with col3:
        resultado = resumen['resultado_operativo']
        st.metric(
            "Resultado Operativo",
            formato_moneda(resultado, decimales=0),
            delta=formato_porcentaje(resumen['margen_operativo']) + " margen" if resumen['total_ventas_pesos'] > 0 else None,
            delta_color="normal" if resultado >= 0 else "inverse"
        )
    
    with col4:
        st.metric(
            "Meses con datos",
            len(resumen['meses'])
        )
    
    # Alerta si no hay ventas
    if resumen['total_ventas_pesos'] == 0:
        st.warning("⚠️ No hay ventas cargadas para este año. Cargá las ventas en 'Carga Manual' para ver el resultado operativo real.")
    
    st.markdown("---")
    
    # =========================================
    # GRÁFICOS DE EVOLUCIÓN
    # =========================================
    if resumen['meses']:
        df_meses = pd.DataFrame(resumen['meses'])
        df_meses['mes_nombre'] = df_meses['mes'].apply(
            lambda x: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][x-1]
        )
        
        # Gráfico de Ventas vs Egresos
        st.subheader("📊 Evolución Mensual: Ventas vs Egresos")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.caption("Montos en tooltip: **$** y separador de miles (formato local).")
            grafico_lineas_multiserie_moneda(
                df_meses,
                "mes_nombre",
                ["ventas_pesos", "egresos"],
                ["Ventas", "Egresos"],
                titulo="Ventas vs egresos",
            )
        
        with col2:
            st.write("**Promedio mensual:**")
            if len(df_meses) > 0:
                st.metric("Ventas", formato_moneda(df_meses['ventas_pesos'].mean(), 0))
                st.metric("Egresos", formato_moneda(df_meses['egresos'].mean(), 0))
                st.metric("Resultado", formato_moneda(df_meses['resultado'].mean(), 0))
        
        # Resultado mensual
        st.subheader("📈 Resultado Operativo Mensual")
        
        df_resultado = df_meses[['mes_nombre', 'resultado']].set_index('mes_nombre')
        df_resultado.columns = ['Resultado']
        grafico_barras_desde_serie(df_resultado['Resultado'], titulo="Resultado operativo mensual", horizontal=False)
        
        # Composición de egresos
        if resumen['total_egresos_bancarios'] > 0 or resumen['total_egresos_efectivo'] > 0:
            st.subheader("💳 Composición de Egresos por Mes")
            
            df_eg = df_meses[['mes_nombre', 'egresos_bancarios', 'egresos_efectivo']].copy()
            grafico_barras_apiladas_mes_moneda(
                df_eg,
                'mes_nombre',
                ['egresos_bancarios', 'egresos_efectivo'],
                etiquetas=['Gastos Bancarios', 'Pagos Efectivo'],
                titulo='Composición de egresos (bancarios + efectivo)',
            )
        
        # Tabla detallada
        st.subheader("📋 Detalle por Mes")
        
        df_detalle = df_meses[['mes', 'ventas_pesos', 'egresos', 'resultado', 'margen']].copy()
        # Calcular % Egresos sobre Ventas
        df_detalle['pct_egresos_ventas'] = df_detalle.apply(
            lambda row: (row['egresos'] / row['ventas_pesos'] * 100) if row['ventas_pesos'] > 0 else 0,
            axis=1
        )
        df_detalle.columns = ['Mes', 'Ventas ($)', 'Egresos ($)', 'Resultado ($)', 'Margen (%)', '% Egresos/Ventas']
        
        # Agregar totales
        total_ventas = df_detalle['Ventas ($)'].sum()
        total_egresos = df_detalle['Egresos ($)'].sum()
        pct_egresos_total = (total_egresos / total_ventas * 100) if total_ventas > 0 else 0
        
        total_row = pd.DataFrame([{
            'Mes': 'TOTAL',
            'Ventas ($)': total_ventas,
            'Egresos ($)': total_egresos,
            'Resultado ($)': df_detalle['Resultado ($)'].sum(),
            'Margen (%)': resumen['margen_operativo'],
            '% Egresos/Ventas': pct_egresos_total
        }])
        df_detalle = pd.concat([df_detalle, total_row], ignore_index=True)
        
        st.dataframe(
            df_detalle.style.format({
                'Ventas ($)': formato_df_moneda,
                'Egresos ($)': formato_df_moneda,
                'Resultado ($)': formato_df_moneda,
                'Margen (%)': formato_df_porcentaje,
                '% Egresos/Ventas': formato_df_porcentaje
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Ventas en KG si hay datos
        if resumen['total_ventas_kgs'] > 0:
            st.markdown("---")
            st.subheader("📦 Ventas en Kilogramos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Total Kg Vendidos", f"{formato_numero(resumen['total_ventas_kgs'], 2)} kg")
                
                # Precio promedio por kg
                if resumen['total_ventas_kgs'] > 0:
                    precio_promedio = resumen['total_ventas_pesos'] / resumen['total_ventas_kgs']
                    st.metric("Precio Promedio por Kg", formato_moneda(precio_promedio))
            
            with col2:
                # Gráfico de kg por mes
                df_kgs = df_meses[['mes_nombre', 'ventas_kgs']].copy()
                st.caption("Kilogramos (sin $).")
                st.bar_chart(df_kgs.set_index('mes_nombre')['ventas_kgs'])
        
        # =========================================
        # INFORMACIÓN BANCARIA (REFERENCIA)
        # =========================================
        st.markdown("---")
        
        with st.expander("📥 Ingresos Bancarios (Informativo)"):
            st.caption("Estos son los créditos bancarios - NO se consideran como ingresos operativos")
            st.metric(
                "Total Ingresos Bancarios del Año",
                formato_moneda(resumen['total_ingresos_bancarios'])
            )
            st.info("Los ingresos bancarios incluyen: transferencias recibidas, depósitos, liquidaciones de tarjetas, etc. No representan las ventas reales del negocio.")
    
    else:
        st.info(f"No hay datos mensuales para {anio_seleccionado}")

except ImportError as e:
    st.error(f"Error de importación: {str(e)}")
except Exception as e:
    st.error(f"Error: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
