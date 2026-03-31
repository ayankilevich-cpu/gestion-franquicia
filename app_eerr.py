"""
Aplicación web para procesar extractos bancarios del Banco Macro.
Genera automáticamente un EERR (Estado de Resultados) con el flujo de caja.

Ejecutar con: streamlit run app_eerr.py
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import io

# Importar funciones del módulo principal
from resumen_macro import (
    leer_pdf_texto,
    extraer_movimientos,
    generar_eerr,
    categorizar_movimiento,
    CUIT_EMPRESA,
)
from utils.formato import formato_moneda
from utils.charts import grafico_barras_moneda, grafico_lineas_multiserie_moneda

# Configuración de la página
st.set_page_config(
    page_title="EERR Banco Macro",
    page_icon="📊",
    layout="wide"
)

# Título principal
st.title("📊 Análisis de Extractos Bancarios - Banco Macro")
st.markdown(f"**CUIT Empresa:** {CUIT_EMPRESA} (los traspasos con este CUIT se excluyen del resultado operativo)")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Opción para cambiar el CUIT si es necesario
    cuit_custom = st.text_input(
        "CUIT de la empresa (para detectar traspasos internos):",
        value=CUIT_EMPRESA,
        help="Los movimientos con este CUIT se considerarán traspasos internos"
    )
    
    st.markdown("---")
    st.markdown("### 📁 Instrucciones")
    st.markdown("""
    1. Cargá el PDF del extracto bancario
    2. El sistema procesará automáticamente los movimientos
    3. Descargá el Excel con el análisis completo
    """)

# Área principal
st.header("📄 Cargar Extracto Bancario")

uploaded_file = st.file_uploader(
    "Arrastrá o seleccioná el PDF del extracto",
    type=['pdf'],
    help="Formato: Extracto de cuenta del Banco Macro"
)

if uploaded_file is not None:
    # Guardar el archivo temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    
    # Procesar el PDF
    with st.spinner("🔄 Procesando extracto bancario..."):
        try:
            # Leer y extraer movimientos
            texto = leer_pdf_texto(tmp_path)
            movimientos = extraer_movimientos(texto)
            
            if not movimientos:
                st.error("❌ No se encontraron movimientos en el PDF. Verificá que sea un extracto del Banco Macro.")
            else:
                # Generar EERR
                eerr = generar_eerr(movimientos)
                
                # Extraer período
                import re
                match_periodo = re.search(r'Periodo del Extracto:\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})', texto)
                periodo = f"{match_periodo.group(1)} al {match_periodo.group(2)}" if match_periodo else "No detectado"
                
                # Mostrar resumen
                st.success(f"✅ Procesados **{len(movimientos)}** movimientos")
                st.info(f"📅 **Período:** {periodo}")
                
                # Tabs para organizar la información
                tab1, tab2, tab3, tab4 = st.tabs(["📊 EERR", "📋 Movimientos", "📈 Gráficos", "⬇️ Descargar"])
                
                with tab1:
                    st.header("Estado de Resultados - Flujo de Caja")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📈 Ingresos Operativos")
                        ingresos_df = pd.DataFrame([
                            {"Categoría": k, "Monto": v}
                            for k, v in sorted(eerr['ingresos'].items(), key=lambda x: -x[1])
                        ])
                        if not ingresos_df.empty:
                            ingresos_df["Monto"] = ingresos_df["Monto"].apply(formato_moneda)
                            st.dataframe(ingresos_df, hide_index=True, use_container_width=True)
                        st.metric("Total Ingresos", formato_moneda(eerr["total_ingresos"]))
                    
                    with col2:
                        st.subheader("📉 Egresos Operativos")
                        egresos_df = pd.DataFrame([
                            {"Categoría": k, "Monto": v}
                            for k, v in sorted(eerr['egresos'].items(), key=lambda x: -x[1])
                        ])
                        if not egresos_df.empty:
                            egresos_df["Monto"] = egresos_df["Monto"].apply(formato_moneda)
                            st.dataframe(egresos_df, hide_index=True, use_container_width=True)
                        st.metric("Total Egresos", formato_moneda(eerr["total_egresos"]))
                    
                    st.markdown("---")
                    
                    # Resultado principal
                    resultado = eerr['resultado_neto']
                    col_res1, col_res2, col_res3 = st.columns(3)
                    
                    with col_res2:
                        if resultado >= 0:
                            st.success(
                                f"### ✅ Resultado Operativo Neto\n## {formato_moneda(resultado)}"
                            )
                        else:
                            st.error(
                                f"### ❌ Resultado Operativo Neto\n## {formato_moneda(resultado)}"
                            )
                    
                    # Traspasos internos
                    if eerr.get('traspasos_entrada', 0) > 0 or eerr.get('traspasos_salida', 0) > 0:
                        st.markdown("---")
                        st.subheader("🔄 Traspasos entre Cuentas Propias")
                        st.caption("Estos movimientos NO afectan el resultado operativo")
                        
                        col_t1, col_t2, col_t3 = st.columns(3)
                        with col_t1:
                            st.metric("Entradas", formato_moneda(eerr.get("traspasos_entrada", 0)))
                        with col_t2:
                            st.metric("Salidas", formato_moneda(eerr.get("traspasos_salida", 0)))
                        with col_t3:
                            st.metric("Neto", formato_moneda(eerr.get("traspasos_neto", 0)))
                
                with tab2:
                    st.header("Detalle de Movimientos")
                    
                    # Crear DataFrame
                    df_mov = pd.DataFrame(movimientos)
                    df_mov['categoria'] = df_mov.apply(
                        lambda row: categorizar_movimiento(
                            row['descripcion'],
                            es_debito=(row['debito'] > 0),
                            referencia=row.get('referencia', '')
                        ),
                        axis=1
                    )
                    df_mov['tipo'] = df_mov.apply(
                        lambda row: 'Crédito' if row['credito'] > 0 else 'Débito',
                        axis=1
                    )
                    df_mov['monto'] = df_mov.apply(
                        lambda row: row['credito'] if row['credito'] > 0 else row['debito'],
                        axis=1
                    )
                    
                    # Filtros
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        tipo_filtro = st.multiselect(
                            "Filtrar por tipo:",
                            options=['Crédito', 'Débito'],
                            default=['Crédito', 'Débito']
                        )
                    with col_f2:
                        cat_filtro = st.multiselect(
                            "Filtrar por categoría:",
                            options=sorted(df_mov['categoria'].unique()),
                            default=[]
                        )
                    
                    # Aplicar filtros
                    df_filtrado = df_mov[df_mov['tipo'].isin(tipo_filtro)]
                    if cat_filtro:
                        df_filtrado = df_filtrado[df_filtrado['categoria'].isin(cat_filtro)]
                    
                    # Mostrar tabla (montos como texto $ argentino)
                    df_tabla = (
                        df_filtrado[
                            ["fecha", "tipo", "categoria", "descripcion", "monto", "saldo"]
                        ]
                        .sort_values("fecha")
                        .copy()
                    )
                    df_tabla["monto"] = df_tabla["monto"].apply(
                        lambda x: formato_moneda(float(x))
                    )
                    df_tabla["saldo"] = df_tabla["saldo"].apply(
                        lambda x: formato_moneda(float(x))
                    )
                    st.dataframe(
                        df_tabla,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YY"),
                            "monto": st.column_config.TextColumn("Monto"),
                            "saldo": st.column_config.TextColumn("Saldo"),
                        },
                    )
                    
                    st.caption(f"Mostrando {len(df_filtrado)} de {len(df_mov)} movimientos")
                
                with tab3:
                    st.header("Análisis Gráfico")
                    
                    # Gráfico de ingresos vs egresos
                    col_g1, col_g2 = st.columns(2)
                    
                    with col_g1:
                        st.subheader("Distribución de Ingresos")
                        if eerr["ingresos"]:
                            ing_data = pd.DataFrame(
                                [
                                    {"Categoría": k, "Monto": v}
                                    for k, v in eerr["ingresos"].items()
                                ]
                            )
                            grafico_barras_moneda(
                                ing_data, "Categoría", "Monto", "Ingresos por categoría"
                            )

                    with col_g2:
                        st.subheader("Distribución de Egresos")
                        if eerr["egresos"]:
                            egr_data = pd.DataFrame(
                                [
                                    {"Categoría": k, "Monto": v}
                                    for k, v in eerr["egresos"].items()
                                ]
                            )
                            grafico_barras_moneda(
                                egr_data, "Categoría", "Monto", "Egresos por categoría"
                            )
                    
                    # Flujo diario
                    st.subheader("Flujo de Caja Diario")
                    df_mov['fecha'] = pd.to_datetime(df_mov['fecha'])
                    
                    # Excluir traspasos del flujo diario
                    df_operativo = df_mov[df_mov['categoria'] != '*** Traspasos entre Cuentas Propias ***']
                    
                    df_diario = df_operativo.groupby(df_operativo['fecha'].dt.date).agg({
                        'debito': 'sum',
                        'credito': 'sum'
                    }).reset_index()
                    df_diario["Flujo Neto"] = df_diario["credito"] - df_diario["debito"]
                    df_diario = df_diario.rename(
                        columns={
                            "fecha": "Fecha",
                            "credito": "Ingresos",
                            "debito": "Egresos",
                        }
                    )
                    df_diario = df_diario.sort_values("Fecha")
                    df_linea = df_diario.copy()
                    df_linea["Fecha"] = df_linea["Fecha"].astype(str)
                    grafico_lineas_multiserie_moneda(
                        df_linea,
                        "Fecha",
                        ["Ingresos", "Egresos", "Flujo Neto"],
                        titulo="Flujo de caja diario",
                    )
                
                with tab4:
                    st.header("Descargar Resultados")
                    
                    # Preparar Excel en memoria
                    output = io.BytesIO()
                    
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        # Hoja de movimientos
                        df_export = df_mov[['fecha', 'tipo', 'categoria', 'descripcion', 'referencia', 'debito', 'credito', 'saldo']].copy()
                        df_export.to_excel(writer, sheet_name='Movimientos', index=False)
                        
                        # Hoja de EERR
                        eerr_data = []
                        for cat, monto in sorted(eerr['ingresos'].items(), key=lambda x: -x[1]):
                            eerr_data.append({'Tipo': 'INGRESO', 'Categoría': cat, 'Monto': monto})
                        for cat, monto in sorted(eerr['egresos'].items(), key=lambda x: -x[1]):
                            eerr_data.append({'Tipo': 'EGRESO', 'Categoría': cat, 'Monto': monto})
                        eerr_data.append({'Tipo': '---', 'Categoría': '---', 'Monto': None})
                        eerr_data.append({'Tipo': 'TOTAL', 'Categoría': 'Total Ingresos', 'Monto': eerr['total_ingresos']})
                        eerr_data.append({'Tipo': 'TOTAL', 'Categoría': 'Total Egresos', 'Monto': eerr['total_egresos']})
                        eerr_data.append({'Tipo': 'RESULTADO', 'Categoría': 'Resultado Operativo', 'Monto': eerr['resultado_neto']})
                        eerr_data.append({'Tipo': '---', 'Categoría': '---', 'Monto': None})
                        eerr_data.append({'Tipo': 'TRASPASO', 'Categoría': 'Traspasos Entrada', 'Monto': eerr.get('traspasos_entrada', 0)})
                        eerr_data.append({'Tipo': 'TRASPASO', 'Categoría': 'Traspasos Salida', 'Monto': eerr.get('traspasos_salida', 0)})
                        
                        pd.DataFrame(eerr_data).to_excel(writer, sheet_name='EERR', index=False)
                        
                        # Resumen diario
                        df_diario.to_excel(writer, sheet_name='Flujo Diario', index=False)
                    
                    # Botón de descarga
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Descargar Excel Completo",
                        data=excel_data,
                        file_name=f"EERR_{periodo.replace('/', '-').replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    st.info("El Excel incluye: Movimientos detallados, EERR por categoría, y Flujo diario")
        
        except Exception as e:
            st.error(f"❌ Error al procesar el PDF: {str(e)}")
            st.exception(e)
    
    # Limpiar archivo temporal
    Path(tmp_path).unlink(missing_ok=True)

else:
    # Mostrar instrucciones cuando no hay archivo
    st.info("👆 Cargá un PDF de extracto bancario para comenzar el análisis")
    
    # Mostrar ejemplo de qué esperar
    with st.expander("ℹ️ ¿Qué información obtengo?"):
        st.markdown("""
        ### El análisis incluye:
        
        **📊 Estado de Resultados (EERR)**
        - Ingresos operativos por categoría (ventas, cobranzas, etc.)
        - Egresos operativos por categoría (proveedores, sueldos, impuestos, etc.)
        - Resultado neto del período
        
        **🔄 Traspasos Internos**
        - Movimientos entre cuentas propias (mismo CUIT)
        - Estos NO afectan el resultado operativo
        
        **📈 Análisis Gráfico**
        - Distribución de ingresos y egresos
        - Flujo de caja diario
        
        **📥 Exportación**
        - Excel con todas las hojas de análisis
        """)

# Footer
st.markdown("---")
st.caption("💻 Desarrollado para BLEMA SAS - Gestión de Franquicia Grido")
