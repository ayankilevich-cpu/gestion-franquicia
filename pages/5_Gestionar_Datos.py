"""
Página para gestionar datos cargados - ver y eliminar.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Gestionar Datos", page_icon="🗂️", layout="wide")

st.title("🗂️ Gestionar Datos Cargados")

# Verificar conexión
from db.connection import test_connection

if not test_connection():
    st.error("❌ No hay conexión a la base de datos")
    st.stop()

# Tabs para diferentes tipos de datos
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Movimientos Bancarios",
    "📈 Períodos",
    "💰 Ventas",
    "💵 Pagos Efectivo"
])

# ============================================
# TAB 1: MOVIMIENTOS BANCARIOS
# ============================================
with tab1:
    st.subheader("Movimientos Bancarios Cargados")
    
    from db.connection import get_connection
    
    # Obtener resumen de movimientos por banco y período
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                p.anio,
                p.mes,
                mb.banco,
                COUNT(*) as cantidad,
                SUM(mb.credito) as total_creditos,
                SUM(mb.debito) as total_debitos,
                MIN(mb.fecha) as fecha_desde,
                MAX(mb.fecha) as fecha_hasta,
                MIN(mb.created_at) as cargado_el
            FROM movimientos_bancarios mb
            JOIN periodos p ON mb.periodo_id = p.id
            GROUP BY p.id, p.anio, p.mes, mb.banco
            ORDER BY p.anio DESC, p.mes DESC, mb.banco
        """
        cursor.execute(query)
        resumen = cursor.fetchall()
        
        if resumen:
            df_resumen = pd.DataFrame(resumen)
            df_resumen['periodo'] = df_resumen.apply(
                lambda x: f"{x['mes']:02d}/{x['anio']}", axis=1
            )
            df_resumen['total_creditos'] = df_resumen['total_creditos'].apply(
                lambda x: f"${x:,.2f}" if x else "$0.00"
            )
            df_resumen['total_debitos'] = df_resumen['total_debitos'].apply(
                lambda x: f"${x:,.2f}" if x else "$0.00"
            )
            
            st.dataframe(
                df_resumen[['periodo', 'banco', 'cantidad', 'total_creditos', 'total_debitos', 'fecha_desde', 'fecha_hasta']],
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            
            # Eliminar movimientos
            st.subheader("🗑️ Eliminar Movimientos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Selector de período
                periodos_disponibles = df_resumen['periodo'].unique().tolist()
                periodo_eliminar = st.selectbox(
                    "Período",
                    options=periodos_disponibles,
                    key="periodo_eliminar_mov"
                )
            
            with col2:
                # Selector de banco
                bancos_periodo = df_resumen[df_resumen['periodo'] == periodo_eliminar]['banco'].unique().tolist()
                banco_eliminar = st.selectbox(
                    "Banco",
                    options=["TODOS"] + bancos_periodo,
                    key="banco_eliminar"
                )
            
            # Mostrar qué se eliminará
            if periodo_eliminar:
                mes, anio = periodo_eliminar.split('/')
                
                if banco_eliminar == "TODOS":
                    filtro = df_resumen[df_resumen['periodo'] == periodo_eliminar]
                    total_movs = filtro['cantidad'].sum()
                else:
                    filtro = df_resumen[(df_resumen['periodo'] == periodo_eliminar) & (df_resumen['banco'] == banco_eliminar)]
                    total_movs = filtro['cantidad'].sum() if len(filtro) > 0 else 0
                
                st.warning(f"⚠️ Se eliminarán **{total_movs}** movimientos de {banco_eliminar} del período {periodo_eliminar}")
                
                # Botón de confirmación
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("🗑️ Eliminar", type="primary", key="btn_eliminar_mov"):
                        try:
                            # Obtener periodo_id
                            cursor.execute(
                                "SELECT id FROM periodos WHERE anio = %s AND mes = %s",
                                (int(anio), int(mes))
                            )
                            periodo_row = cursor.fetchone()
                            
                            if periodo_row:
                                if banco_eliminar == "TODOS":
                                    cursor.execute(
                                        "DELETE FROM movimientos_bancarios WHERE periodo_id = %s",
                                        (periodo_row['id'],)
                                    )
                                else:
                                    cursor.execute(
                                        "DELETE FROM movimientos_bancarios WHERE periodo_id = %s AND banco = %s",
                                        (periodo_row['id'], banco_eliminar)
                                    )
                                
                                conn.commit()
                                st.success(f"✅ Eliminados {cursor.rowcount} movimientos")
                                st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        else:
            st.info("No hay movimientos bancarios cargados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error consultando datos: {str(e)}")

# ============================================
# TAB 2: PERÍODOS
# ============================================
with tab2:
    st.subheader("Períodos Registrados")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.*,
                (SELECT COUNT(*) FROM movimientos_bancarios WHERE periodo_id = p.id) as mov_bancarios,
                (SELECT COUNT(*) FROM ventas_mensuales WHERE periodo_id = p.id) as ventas,
                (SELECT COUNT(*) FROM pagos_efectivo WHERE periodo_id = p.id) as pagos_efectivo
            FROM periodos p
            ORDER BY p.anio DESC, p.mes DESC
        """)
        periodos = cursor.fetchall()
        
        if periodos:
            df_periodos = pd.DataFrame(periodos)
            df_periodos['periodo'] = df_periodos.apply(
                lambda x: f"{x['mes']:02d}/{x['anio']}", axis=1
            )
            
            st.dataframe(
                df_periodos[['periodo', 'fecha_inicio', 'fecha_fin', 'estado', 'mov_bancarios', 'ventas', 'pagos_efectivo']],
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            
            # Eliminar período completo
            st.subheader("🗑️ Eliminar Período Completo")
            
            periodos_lista = [f"{p['mes']:02d}/{p['anio']}" for p in periodos]
            periodo_eliminar = st.selectbox(
                "Seleccionar período a eliminar",
                options=periodos_lista,
                key="periodo_eliminar_completo"
            )
            
            if periodo_eliminar:
                mes, anio = periodo_eliminar.split('/')
                periodo_data = next(
                    (p for p in periodos if p['mes'] == int(mes) and p['anio'] == int(anio)),
                    None
                )
                
                if periodo_data:
                    st.warning(f"""
                    ⚠️ Se eliminará el período {periodo_eliminar} con:
                    - {periodo_data['mov_bancarios']} movimientos bancarios
                    - {periodo_data['ventas']} registros de ventas
                    - {periodo_data['pagos_efectivo']} pagos en efectivo
                    """)
                    
                    confirm = st.checkbox("Confirmo que quiero eliminar este período y todos sus datos", key="confirm_delete_periodo")
                    
                    if confirm:
                        if st.button("🗑️ Eliminar Período Completo", type="primary", key="btn_eliminar_periodo"):
                            try:
                                # Eliminar en cascada
                                cursor.execute("DELETE FROM movimientos_bancarios WHERE periodo_id = %s", (periodo_data['id'],))
                                cursor.execute("DELETE FROM ventas_mensuales WHERE periodo_id = %s", (periodo_data['id'],))
                                cursor.execute("DELETE FROM pagos_efectivo WHERE periodo_id = %s", (periodo_data['id'],))
                                cursor.execute("DELETE FROM periodos WHERE id = %s", (periodo_data['id'],))
                                conn.commit()
                                st.success(f"✅ Período {periodo_eliminar} eliminado completamente")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
        else:
            st.info("No hay períodos registrados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# TAB 3: VENTAS
# ============================================
with tab3:
    st.subheader("Ventas Cargadas")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.anio, p.mes,
                COUNT(*) as registros,
                SUM(v.venta_pesos) as total_pesos,
                SUM(v.venta_kgs) as total_kg,
                MIN(v.fecha) as desde,
                MAX(v.fecha) as hasta
            FROM ventas_mensuales v
            JOIN periodos p ON v.periodo_id = p.id
            GROUP BY p.id, p.anio, p.mes
            ORDER BY p.anio DESC, p.mes DESC
        """)
        ventas = cursor.fetchall()
        
        if ventas:
            df_ventas = pd.DataFrame(ventas)
            df_ventas['periodo'] = df_ventas.apply(lambda x: f"{x['mes']:02d}/{x['anio']}", axis=1)
            df_ventas['total_pesos'] = df_ventas['total_pesos'].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
            df_ventas['total_kg'] = df_ventas['total_kg'].apply(lambda x: f"{x:,.2f} kg" if x else "0 kg")
            
            st.dataframe(
                df_ventas[['periodo', 'registros', 'total_pesos', 'total_kg', 'desde', 'hasta']],
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            
            # Eliminar ventas
            st.subheader("🗑️ Eliminar Ventas")
            
            periodos_ventas = df_ventas['periodo'].tolist()
            periodo_eliminar = st.selectbox(
                "Período",
                options=periodos_ventas,
                key="periodo_eliminar_ventas"
            )
            
            if periodo_eliminar and st.button("🗑️ Eliminar Ventas del Período", key="btn_eliminar_ventas"):
                mes, anio = periodo_eliminar.split('/')
                cursor.execute(
                    """DELETE FROM ventas_mensuales 
                    WHERE periodo_id = (SELECT id FROM periodos WHERE anio = %s AND mes = %s)""",
                    (int(anio), int(mes))
                )
                conn.commit()
                st.success(f"✅ Eliminadas {cursor.rowcount} ventas")
                st.rerun()
        else:
            st.info("No hay ventas cargadas")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# TAB 4: PAGOS EFECTIVO
# ============================================
with tab4:
    st.subheader("Pagos en Efectivo Cargados")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.anio, p.mes,
                COUNT(*) as registros,
                SUM(pe.monto) as total,
                MIN(pe.fecha) as desde,
                MAX(pe.fecha) as hasta
            FROM pagos_efectivo pe
            JOIN periodos p ON pe.periodo_id = p.id
            GROUP BY p.id, p.anio, p.mes
            ORDER BY p.anio DESC, p.mes DESC
        """)
        pagos = cursor.fetchall()
        
        if pagos:
            df_pagos = pd.DataFrame(pagos)
            df_pagos['periodo'] = df_pagos.apply(lambda x: f"{x['mes']:02d}/{x['anio']}", axis=1)
            df_pagos['total'] = df_pagos['total'].apply(lambda x: f"${x:,.2f}" if x else "$0.00")
            
            st.dataframe(
                df_pagos[['periodo', 'registros', 'total', 'desde', 'hasta']],
                use_container_width=True,
                hide_index=True
            )
            
            st.divider()
            
            # Eliminar pagos
            st.subheader("🗑️ Eliminar Pagos en Efectivo")
            
            periodos_pagos = df_pagos['periodo'].tolist()
            periodo_eliminar = st.selectbox(
                "Período",
                options=periodos_pagos,
                key="periodo_eliminar_pagos"
            )
            
            if periodo_eliminar and st.button("🗑️ Eliminar Pagos del Período", key="btn_eliminar_pagos"):
                mes, anio = periodo_eliminar.split('/')
                cursor.execute(
                    """DELETE FROM pagos_efectivo 
                    WHERE periodo_id = (SELECT id FROM periodos WHERE anio = %s AND mes = %s)""",
                    (int(anio), int(mes))
                )
                conn.commit()
                st.success(f"✅ Eliminados {cursor.rowcount} pagos")
                st.rerun()
        else:
            st.info("No hay pagos en efectivo cargados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# INFORMACIÓN ADICIONAL
# ============================================
st.divider()

with st.expander("ℹ️ Información sobre la gestión de datos"):
    st.markdown("""
    ### Cómo usar esta página
    
    **Movimientos Bancarios:**
    - Podés ver todos los movimientos cargados agrupados por período y banco
    - Podés eliminar movimientos de un banco específico o de todos los bancos para un período
    
    **Períodos:**
    - Un período agrupa todos los datos de un mes (movimientos, ventas, pagos)
    - Al eliminar un período, se eliminan TODOS los datos asociados
    
    **Ventas y Pagos en Efectivo:**
    - Se pueden eliminar por período
    
    ### ⚠️ Importante
    - Las eliminaciones son **permanentes** y no se pueden deshacer
    - Si necesitás recargar datos, primero eliminá los existentes para evitar duplicados
    """)
