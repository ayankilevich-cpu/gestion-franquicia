"""
Página de Estado de Resultados Mensual.
Muestra el EERR detallado por período.

EERR Operativo:
- Ingresos = Ventas del período
- Egresos = Gastos bancarios + Pagos en efectivo
"""
import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NOMBRE_EMPRESA, CATEGORIAS_EGRESO_EXCLUIDAS_EERR
from utils.formato import formato_moneda, formato_porcentaje, formato_df_moneda, formato_df_porcentaje

st.set_page_config(page_title="EERR Mensual", page_icon="📊", layout="wide")

# CSS para ajustar tamaño de métricas (números grandes)
st.markdown("""
<style>
    /* Reducir tamaño de valores en métricas para números de 9+ dígitos */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    /* Mantener labels legibles */
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
    }
    /* Delta (porcentajes) más pequeño */
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Estado de Resultados Mensual")
st.markdown(f"**{NOMBRE_EMPRESA}** - Análisis detallado por período")

try:
    from db.queries import (
        obtener_periodos, 
        obtener_eerr_operativo,
        obtener_movimientos_periodo,
        obtener_pagos_efectivo_periodo
    )
    from utils.exportar import exportar_eerr_excel
    
    # Obtener períodos disponibles
    periodos = obtener_periodos()
    
    if not periodos:
        st.info("📭 No hay períodos cargados. Usá la página 'Cargar Datos' para comenzar.")
        st.stop()
    
    # Selector de período
    opciones_periodo = {
        f"{p['mes']:02d}/{p['anio']} ({p['total_movimientos']} mov.)": p['id']
        for p in periodos
    }
    
    periodo_seleccionado = st.selectbox(
        "Seleccionar Período:",
        options=list(opciones_periodo.keys())
    )
    
    periodo_id = opciones_periodo[periodo_seleccionado]
    
    # Obtener datos
    eerr = obtener_eerr_operativo(periodo_id=periodo_id)
    movimientos = obtener_movimientos_periodo(periodo_id=periodo_id)
    pagos_efectivo = obtener_pagos_efectivo_periodo(periodo_id=periodo_id)
    
    st.markdown("---")
    
    # =========================================
    # MÉTRICAS PRINCIPALES
    # =========================================
    st.subheader("💰 Resultado Operativo")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Ventas del Período",
            formato_moneda(eerr['ventas_pesos']),
            help="Total de ventas cargadas para este mes"
        )
        if eerr['ventas_kgs'] > 0:
            st.caption(f"📦 {eerr['ventas_kgs']:,.2f} kg | {formato_moneda(eerr['precio_promedio_kg'])}/kg")
    
    with col2:
        st.metric(
            "Total Egresos",
            formato_moneda(eerr['total_egresos']),
            help="Gastos bancarios operativos + pagos en efectivo (sin transferencias enviadas ni traspasos internos)",
        )
    
    with col3:
        resultado = eerr['resultado_operativo']
        delta_color = "normal" if resultado >= 0 else "inverse"
        st.metric(
            "Resultado Operativo",
            formato_moneda(resultado),
            delta=formato_porcentaje(eerr['margen_operativo']) + " margen" if eerr['ventas_pesos'] > 0 else None,
            delta_color=delta_color
        )
    
    with col4:
        st.metric(
            "Movimientos",
            len(movimientos) + len(pagos_efectivo)
        )
    
    # Alerta si no hay ventas cargadas
    if eerr['ventas_pesos'] == 0:
        st.warning("⚠️ No hay ventas cargadas para este período. Cargá las ventas en 'Carga Manual' para ver el resultado operativo real.")

    excl_te = float(eerr.get('monto_transferencias_enviadas_excluido_eerr') or 0)
    if excl_te > 0:
        st.info(
            f"ℹ️ **Transferencias enviadas** no forman parte del gasto operativo en este EERR. "
            f"Monto excluido del total de egresos: **{formato_moneda(excl_te)}**."
        )

    st.markdown("---")
    
    # =========================================
    # TABS DE DETALLE
    # =========================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📉 Detalle de Egresos", 
        "📋 Movimientos Bancarios",
        "💵 Pagos en Efectivo",
        "🔄 Traspasos e Ingresos Bancarios"
    ])
    
    # TAB 1: DETALLE DE EGRESOS
    with tab1:
        st.subheader("📉 Composición de Egresos")
        
        if eerr['egresos']:
            ventas = eerr.get('ventas_pesos', 0)
            
            df_egresos = pd.DataFrame([
                {
                    "Categoría": k, 
                    "Monto": v, 
                    "% s/Egresos": v/eerr['total_egresos']*100 if eerr['total_egresos'] > 0 else 0,
                    "% s/Ventas": v/ventas*100 if ventas > 0 else 0
                }
                for k, v in sorted(eerr['egresos'].items(), key=lambda x: -x[1])
            ])
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.dataframe(
                    df_egresos.style.format({
                        "Monto": formato_df_moneda,
                        "% s/Egresos": formato_df_porcentaje,
                        "% s/Ventas": formato_df_porcentaje
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            
            with col2:
                # Separar bancarios vs efectivo
                st.write("**Por origen:**")
                total_bancario = sum(eerr['egresos_bancarios'].values())
                total_efectivo = sum(eerr['egresos_efectivo'].values())

                st.metric("Gastos Bancarios", formato_moneda(total_bancario))
                st.caption("Bancarios operativos (sin transferencias enviadas).")
                st.metric("Pagos en Efectivo", formato_moneda(total_efectivo))
            
            # Gráfico
            st.bar_chart(df_egresos.set_index('Categoría')['Monto'])
        else:
            st.info("No hay egresos en este período")
    
    # TAB 2: MOVIMIENTOS BANCARIOS
    with tab2:
        st.subheader("📋 Movimientos Bancarios")
        
        if movimientos:
            df_mov = pd.DataFrame(movimientos)
            
            # Filtros
            col1, col2, col3 = st.columns(3)
            
            with col1:
                filtro_tipo = st.multiselect(
                    "Tipo:",
                    options=['CREDITO', 'DEBITO', 'TRASPASO_INTERNO'],
                    default=['DEBITO'],
                    key="filtro_tipo_mov"
                )
            
            with col2:
                categorias_disponibles = sorted(df_mov['categoria'].unique())
                filtro_categoria = st.multiselect(
                    "Categoría:",
                    options=categorias_disponibles,
                    key="filtro_cat_mov"
                )
            
            with col3:
                filtro_banco = st.multiselect(
                    "Banco:",
                    options=sorted(df_mov['banco'].unique()),
                    key="filtro_banco_mov"
                )
            
            # Aplicar filtros
            df_filtrado = df_mov
            if filtro_tipo:
                df_filtrado = df_filtrado[df_filtrado['tipo'].isin(filtro_tipo)]
            if filtro_categoria:
                df_filtrado = df_filtrado[df_filtrado['categoria'].isin(filtro_categoria)]
            if filtro_banco:
                df_filtrado = df_filtrado[df_filtrado['banco'].isin(filtro_banco)]
            
            # Mostrar
            st.dataframe(
                df_filtrado[['fecha', 'banco', 'tipo', 'categoria', 'descripcion', 'debito', 'credito']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "debito": st.column_config.NumberColumn("Débito", format="$%.2f"),
                    "credito": st.column_config.NumberColumn("Crédito", format="$%.2f"),
                }
            )
            
            st.caption(f"Mostrando {len(df_filtrado)} de {len(df_mov)} movimientos")

            # Desglose de gastos bancarios operativos (gráficas)
            st.markdown("---")
            st.subheader("📊 Desglose de gastos bancarios (operativos)")
            st.caption(
                "Suma de **débitos** por categoría, excluyendo traspasos entre cuentas propias y "
                "transferencias enviadas (no computadas como gasto en el EERR)."
            )

            df_deb = df_mov.copy()
            df_deb["_es_tr"] = df_deb["es_traspaso_interno"].apply(
                lambda x: bool(x) if x is not None else False
            )
            df_deb["_cat"] = df_deb["categoria"].fillna("Sin categoría")
            mask_op = (
                (df_deb["debito"].fillna(0).astype(float) > 0)
                & (~df_deb["_es_tr"])
                & (~df_deb["_cat"].isin(CATEGORIAS_EGRESO_EXCLUIDAS_EERR))
            )
            df_gasto_cat = (
                df_deb.loc[mask_op]
                .groupby("_cat", as_index=False)["debito"]
                .sum()
                .sort_values("debito", ascending=False)
            )
            df_gasto_cat = df_gasto_cat.rename(columns={"_cat": "Categoría", "debito": "Monto"})

            if not df_gasto_cat.empty:
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.markdown("**Por categoría**")
                    st.bar_chart(
                        df_gasto_cat.set_index("Categoría")["Monto"],
                        use_container_width=True,
                    )
                with c2:
                    top_n = min(12, len(df_gasto_cat))
                    st.markdown(f"**Principales categorías (top {top_n})**")
                    st.bar_chart(
                        df_gasto_cat.head(top_n).set_index("Categoría")["Monto"],
                        use_container_width=True,
                    )
                st.dataframe(
                    df_gasto_cat.style.format({"Monto": formato_df_moneda}),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
                    },
                )
            else:
                st.info("No hay débitos operativos para desglosar en este período (solo traspasos o transferencias enviadas).")
        else:
            st.info("No hay movimientos bancarios en este período")
    
    # TAB 3: PAGOS EN EFECTIVO
    with tab3:
        st.subheader("💵 Pagos en Efectivo")
        
        if pagos_efectivo:
            df_efectivo = pd.DataFrame(pagos_efectivo)
            
            st.dataframe(
                df_efectivo[['fecha', 'concepto', 'categoria', 'monto']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
                }
            )
            
            total_efectivo = sum(float(p.get('monto', 0) or 0) for p in pagos_efectivo)
            st.metric("Total Pagos Efectivo", formato_moneda(total_efectivo))
        else:
            st.info("No hay pagos en efectivo cargados para este período")
    
    # TAB 4: TRASPASOS E INGRESOS BANCARIOS
    with tab4:
        st.subheader("🔄 Traspasos entre Cuentas Propias")
        st.caption("Los traspasos NO afectan el resultado operativo")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Entradas (desde otras cuentas)",
                formato_moneda(eerr.get('traspasos_entrada', 0))
            )
        
        with col2:
            st.metric(
                "Salidas (hacia otras cuentas)",
                formato_moneda(eerr.get('traspasos_salida', 0))
            )
        
        with col3:
            st.metric(
                "Neto Traspasos",
                formato_moneda(eerr.get('traspasos_neto', 0))
            )
        
        # Detalle de traspasos
        if movimientos:
            df_mov = pd.DataFrame(movimientos)
            df_traspasos = df_mov[df_mov['es_traspaso_interno'] == True]
            
            if not df_traspasos.empty:
                st.dataframe(
                    df_traspasos[['fecha', 'banco', 'descripcion', 'debito', 'credito']],
                    use_container_width=True,
                    hide_index=True
                )
        
        st.divider()
        
        # Ingresos bancarios (informativo)
        st.subheader("📥 Ingresos Bancarios (Informativo)")
        st.caption("Estos son los créditos bancarios - NO se consideran como ingresos operativos")
        
        if eerr['ingresos_bancarios']:
            df_ingresos_bancarios = pd.DataFrame([
                {"Categoría": k, "Monto": v}
                for k, v in sorted(eerr['ingresos_bancarios'].items(), key=lambda x: -x[1])
            ])
            
            st.dataframe(
                df_ingresos_bancarios.style.format({
                    "Monto": formato_df_moneda
                }),
                use_container_width=True,
                hide_index=True
            )
            
            st.metric("Total Ingresos Bancarios", formato_moneda(eerr['total_ingresos_bancarios']))
        else:
            st.info("No hay ingresos bancarios en este período")
    
    # =========================================
    # EXPORTAR
    # =========================================
    st.markdown("---")
    
    # Preparar datos para exportar
    eerr_export = {
        'ingresos': {'Ventas': eerr['ventas_pesos']},
        'egresos': eerr['egresos'],
        'total_ingresos': eerr['ventas_pesos'],
        'total_egresos': eerr['total_egresos'],
        'resultado_neto': eerr['resultado_operativo'],
        'traspasos_entrada': eerr['traspasos_entrada'],
        'traspasos_salida': eerr['traspasos_salida'],
        'traspasos_neto': eerr['traspasos_neto'],
    }
    
    excel_data = exportar_eerr_excel(movimientos, eerr_export, periodo_seleccionado)
    
    st.download_button(
        label="📥 Descargar Excel Completo",
        data=excel_data,
        file_name=f"EERR_{periodo_seleccionado.replace('/', '-')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

except ImportError as e:
    st.error(f"Error de importación: {str(e)}")
    st.info("Verificá que MySQL esté configurado correctamente")
except Exception as e:
    st.error(f"Error: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
