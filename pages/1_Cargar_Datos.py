"""
Página de carga de datos.
Permite subir extractos bancarios, ventas y pagos en efectivo.
"""
import streamlit as st
import pandas as pd
import tempfile
from pathlib import Path
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CUIT_EMPRESA, BANCOS
from utils.formato import formato_moneda, formato_numero, formato_df_moneda
from parsers.parser_macro import ParserMacro
from parsers.parser_nacion import ParserNacion
from parsers.parser_santander import ParserSantander
from parsers.parser_mercadopago import ParserMercadoPago
from parsers.parser_ventas import ParserVentas
from parsers.parser_efectivo import ParserEfectivo

st.set_page_config(page_title="Cargar Datos", page_icon="📥", layout="wide")

st.title("📥 Cargar Datos")
st.markdown(f"**CUIT Empresa:** {CUIT_EMPRESA}")

# Tabs para diferentes tipos de carga
tab1, tab2, tab3 = st.tabs(["🏦 Extractos Bancarios", "💰 Ventas", "💵 Pagos en Efectivo"])

# =============================================================================
# TAB 1: EXTRACTOS BANCARIOS
# =============================================================================
with tab1:
    st.header("Cargar Extracto Bancario")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        banco_seleccionado = st.selectbox(
            "Seleccionar Banco:",
            options=list(BANCOS.keys()),
            format_func=lambda x: BANCOS[x]['nombre']
        )
    
    with col2:
        st.info(f"Parser: {BANCOS[banco_seleccionado]['parser']}")
    
    # Mercado Pago usa Excel, los demás PDF
    if banco_seleccionado == 'MERCADOPAGO':
        uploaded_file = st.file_uploader(
            "Subir extracto de Mercado Pago (Excel)",
            type=['xlsx', 'xls'],
            key="banco_upload"
        )
        file_suffix = '.xlsx'
    else:
        uploaded_file = st.file_uploader(
            "Subir extracto bancario (PDF)",
            type=['pdf'],
            key="banco_upload"
        )
        file_suffix = '.pdf'
    
    if uploaded_file:
        # Guardar archivo temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        try:
            with st.spinner("Procesando extracto..."):
                # Seleccionar parser según banco
                if banco_seleccionado == 'MACRO':
                    parser = ParserMacro()
                elif banco_seleccionado == 'NACION':
                    parser = ParserNacion()
                elif banco_seleccionado == 'SANTANDER':
                    parser = ParserSantander()
                elif banco_seleccionado == 'MERCADOPAGO':
                    parser = ParserMercadoPago()
                else:
                    st.warning(f"⚠️ Parser de {BANCOS[banco_seleccionado]['nombre']} no implementado aún")
                    parser = None
                
                if parser:
                    # Mercado Pago no usa leer_pdf
                    if banco_seleccionado == 'MERCADOPAGO':
                        periodo_info = parser.extraer_periodo(tmp_path)
                        movimientos = parser.parse(tmp_path)
                    else:
                        texto = parser.leer_pdf(tmp_path)
                        periodo_info = parser.extraer_periodo(texto)
                        movimientos = parser.parse(tmp_path)
                    
                    if movimientos:
                        st.success(f"✅ {len(movimientos)} movimientos encontrados")
                        
                        # Mostrar período
                        if periodo_info:
                            st.info(f"📅 Período: {periodo_info['fecha_inicio']} al {periodo_info['fecha_fin']}")
                        
                        # Mostrar resumen
                        eerr = parser.generar_eerr(movimientos)
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Ingresos Operativos", formato_moneda(eerr['total_ingresos']))
                        with col2:
                            st.metric("Egresos Operativos", formato_moneda(eerr['total_egresos']))
                        with col3:
                            resultado = eerr['resultado_neto']
                            st.metric("Resultado Neto", formato_moneda(resultado))
                        
                        # Traspasos
                        if eerr['traspasos_entrada'] > 0 or eerr['traspasos_salida'] > 0:
                            st.warning(
                                f"🔄 Traspasos internos detectados: Entrada {formato_moneda(eerr['traspasos_entrada'])} | "
                                f"Salida {formato_moneda(eerr['traspasos_salida'])}"
                            )
                        
                        # Preview de movimientos
                        st.subheader("Vista previa de movimientos")
                        df_preview = pd.DataFrame(movimientos[:20])
                        if 'fecha' in df_preview.columns:
                            df_preview['fecha'] = pd.to_datetime(df_preview['fecha']).dt.strftime('%d/%m/%Y')
                        _fmt_prev = {
                            c: formato_df_moneda
                            for c in ('debito', 'credito', 'saldo')
                            if c in df_preview.columns
                        }
                        if _fmt_prev:
                            st.dataframe(
                                df_preview.style.format(_fmt_prev),
                                use_container_width=True,
                            )
                        else:
                            st.dataframe(df_preview, use_container_width=True)
                        
                        # Botón para guardar
                        if st.button("💾 Guardar en Base de Datos", key="save_banco"):
                            try:
                                from db.queries import obtener_o_crear_periodo, guardar_movimientos
                                
                                # Crear/obtener período
                                periodo_id = obtener_o_crear_periodo(
                                    anio=periodo_info['anio'] if periodo_info else datetime.now().year,
                                    mes=periodo_info['mes'] if periodo_info else datetime.now().month,
                                    fecha_inicio=periodo_info['fecha_inicio'] if periodo_info else None,
                                    fecha_fin=periodo_info['fecha_fin'] if periodo_info else None
                                )
                                
                                # Guardar movimientos
                                nuevos, duplicados = guardar_movimientos(movimientos, banco_seleccionado, periodo_id)
                                
                                st.success(f"✅ Guardados: {nuevos} nuevos | {duplicados} duplicados ignorados")
                                
                            except Exception as e:
                                st.error(f"Error guardando: {str(e)}")
                    else:
                        st.warning("⚠️ No se encontraron movimientos")
        
        except Exception as e:
            st.error(f"Error procesando archivo: {str(e)}")
        
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# =============================================================================
# TAB 2: VENTAS
# =============================================================================
with tab2:
    st.header("Cargar Ventas Mensuales")
    
    st.info("""
    **Formato esperado del archivo:**
    - Columnas: Fecha, Venta Pesos (o Monto), Venta Kgs (opcional), Sucursal (opcional)
    - Formatos de fecha: DD/MM/YYYY o DD/MM/YY
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        anio_ventas = st.number_input("Año:", min_value=2020, max_value=2030, value=datetime.now().year, key="anio_ventas")
    with col2:
        mes_ventas = st.selectbox("Mes:", range(1, 13), format_func=lambda x: f"{x:02d}", key="mes_ventas")
    
    uploaded_ventas = st.file_uploader(
        "Subir archivo de ventas (Excel/CSV)",
        type=['xlsx', 'xls', 'csv'],
        key="ventas_upload"
    )
    
    if uploaded_ventas:
        try:
            # Leer archivo
            if uploaded_ventas.name.endswith('.csv'):
                df_ventas = pd.read_csv(uploaded_ventas)
            else:
                df_ventas = pd.read_excel(uploaded_ventas)
            
            st.subheader("Vista previa del archivo")
            st.dataframe(df_ventas.head(10), use_container_width=True)
            
            # Procesar con parser
            parser_ventas = ParserVentas()
            
            try:
                ventas = parser_ventas.parse_dataframe(df_ventas)
                
                if ventas:
                    st.success(f"✅ {len(ventas)} registros de venta encontrados")
                    
                    # Resumen
                    resumen = parser_ventas.obtener_resumen(ventas)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ventas $", formato_moneda(resumen['total_pesos']))
                    with col2:
                        st.metric("Total Ventas Kg", f"{formato_numero(resumen['total_kgs'], 2)} kg")
                    with col3:
                        st.metric("Días", resumen['dias'])
                    
                    # Botón para guardar
                    if st.button("💾 Guardar Ventas", key="save_ventas"):
                        try:
                            from db.queries import obtener_o_crear_periodo, guardar_ventas
                            
                            periodo_id = obtener_o_crear_periodo(anio_ventas, mes_ventas)
                            nuevos, _ = guardar_ventas(ventas, periodo_id)
                            
                            st.success(f"✅ {nuevos} registros de venta guardados")
                            
                        except Exception as e:
                            st.error(f"Error guardando: {str(e)}")
                else:
                    st.warning("⚠️ No se encontraron ventas válidas")
                    
            except ValueError as e:
                st.error(f"Error en formato: {str(e)}")
                
        except Exception as e:
            st.error(f"Error leyendo archivo: {str(e)}")


# =============================================================================
# TAB 3: PAGOS EN EFECTIVO
# =============================================================================
with tab3:
    st.header("Cargar Pagos en Efectivo")
    
    st.info("""
    **Formato esperado del archivo (Google Sheets exportado):**
    - Columnas: Fecha, Concepto (o Descripción), Monto
    - La categoría se asigna automáticamente o puede estar en una columna
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        anio_efectivo = st.number_input("Año:", min_value=2020, max_value=2030, value=datetime.now().year, key="anio_efectivo")
    with col2:
        mes_efectivo = st.selectbox("Mes:", range(1, 13), format_func=lambda x: f"{x:02d}", key="mes_efectivo")
    
    uploaded_efectivo = st.file_uploader(
        "Subir archivo de pagos (Excel/CSV)",
        type=['xlsx', 'xls', 'csv'],
        key="efectivo_upload"
    )
    
    if uploaded_efectivo:
        try:
            # Leer archivo
            if uploaded_efectivo.name.endswith('.csv'):
                df_efectivo = pd.read_csv(uploaded_efectivo)
            else:
                df_efectivo = pd.read_excel(uploaded_efectivo)
            
            st.subheader("Vista previa del archivo")
            st.dataframe(df_efectivo.head(10), use_container_width=True)
            
            # Procesar con parser
            parser_efectivo = ParserEfectivo()
            
            try:
                pagos = parser_efectivo.parse_dataframe(df_efectivo)
                
                if pagos:
                    st.success(f"✅ {len(pagos)} pagos encontrados")
                    
                    # Resumen
                    resumen = parser_efectivo.obtener_resumen(pagos)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Pagos Efectivo", formato_moneda(resumen['total']))
                    with col2:
                        st.metric("Cantidad", resumen['cantidad'])
                    
                    # Por categoría
                    if resumen['por_categoria']:
                        st.subheader("Por Categoría")
                        df_cat = pd.DataFrame([
                            {"Categoría": k, "Monto": v}
                            for k, v in sorted(resumen['por_categoria'].items(), key=lambda x: -x[1])
                        ])
                        st.dataframe(
                            df_cat.style.format({"Monto": formato_df_moneda}),
                            use_container_width=True,
                            hide_index=True,
                        )
                    
                    # Botón para guardar
                    if st.button("💾 Guardar Pagos", key="save_efectivo"):
                        try:
                            from db.queries import obtener_o_crear_periodo, guardar_pagos_efectivo
                            
                            periodo_id = obtener_o_crear_periodo(anio_efectivo, mes_efectivo)
                            nuevos, duplicados = guardar_pagos_efectivo(pagos, periodo_id)
                            
                            st.success(f"✅ {nuevos} pagos guardados | {duplicados} duplicados ignorados")
                            
                        except Exception as e:
                            st.error(f"Error guardando: {str(e)}")
                else:
                    st.warning("⚠️ No se encontraron pagos válidos")
                    
            except ValueError as e:
                st.error(f"Error en formato: {str(e)}")
                
        except Exception as e:
            st.error(f"Error leyendo archivo: {str(e)}")
