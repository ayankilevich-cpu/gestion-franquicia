"""
Página para carga manual de gastos y ventas mensuales.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
import hashlib

st.set_page_config(page_title="Carga Manual", page_icon="✏️", layout="wide")

st.title("✏️ Carga Manual de Datos")

# Verificar conexión
from db.connection import test_connection, get_connection
from config import CATEGORIAS_EGRESOS, CATEGORIAS_INGRESOS

# Definir categorías globalmente
categorias_egresos = list(CATEGORIAS_EGRESOS.keys()) + ['Otros Egresos']
categorias_ingresos = list(CATEGORIAS_INGRESOS.keys()) + ['Otros Ingresos']

if not test_connection():
    st.error("❌ No hay conexión a la base de datos")
    st.stop()

# Definir cuentas bancarias disponibles
CUENTAS_BANCARIAS = {
    'MACRO': 'Banco Macro',
    'NACION': 'Banco Nación',
    'SANTANDER': 'Banco Santander',
    'MERCADOPAGO': 'Mercado Pago',
    'EFECTIVO': 'Efectivo/Caja',
}

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "💸 Movimientos Manuales", 
    "🔄 Traspasos entre Cuentas", 
    "💵 Ingresos Efectivo (Retiros)",
    "📊 Ventas Mensuales"
])

# ============================================
# TAB 1: MOVIMIENTOS MANUALES (Gastos/Ingresos)
# ============================================
with tab1:
    st.subheader("Agregar Gasto o Ingreso Manual")
    st.caption("Para gastos o ingresos que no aparecen en extractos bancarios")
    
    with st.form("form_movimiento_manual"):
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_movimiento = st.radio(
                "Tipo de movimiento",
                options=["Gasto (Egreso)", "Ingreso (Crédito)"],
                horizontal=True
            )
            
            fecha_mov = st.date_input(
                "Fecha",
                value=date.today(),
                format="DD/MM/YYYY"
            )
            
            monto_mov = st.number_input(
                "Monto ($)",
                min_value=0.0,
                step=100.0,
                format="%.2f"
            )
        
        with col2:
            descripcion_mov = st.text_input(
                "Descripción",
                placeholder="Ej: Compra de insumos de limpieza"
            )
            
            referencia_mov = st.text_input(
                "Referencia (opcional)",
                placeholder="Ej: Factura #123"
            )
            
            # Categoría según tipo
            if tipo_movimiento == "Gasto (Egreso)":
                categoria_mov = st.selectbox(
                    "Categoría",
                    options=categorias_egresos
                )
            else:
                categoria_mov = st.selectbox(
                    "Categoría",
                    options=categorias_ingresos
                )
        
        submitted_mov = st.form_submit_button("💾 Guardar Movimiento", type="primary")
        
        if submitted_mov:
            if monto_mov <= 0:
                st.error("El monto debe ser mayor a 0")
            elif not descripcion_mov:
                st.error("Ingresá una descripción")
            else:
                try:
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    
                    # Obtener o crear período
                    anio = fecha_mov.year
                    mes = fecha_mov.month
                    
                    cursor.execute(
                        "SELECT id FROM periodos WHERE anio = %s AND mes = %s",
                        (anio, mes)
                    )
                    periodo = cursor.fetchone()
                    
                    if not periodo:
                        cursor.execute(
                            "INSERT INTO periodos (anio, mes) VALUES (%s, %s)",
                            (anio, mes)
                        )
                        periodo_id = cursor.lastrowid
                    else:
                        periodo_id = periodo['id']
                    
                    # Determinar tipo y montos
                    es_ingreso = tipo_movimiento == "Ingreso (Crédito)"
                    tipo_db = 'CREDITO' if es_ingreso else 'DEBITO'
                    
                    debito = monto_mov if not es_ingreso else 0
                    credito = monto_mov if es_ingreso else 0
                    
                    # Generar hash único
                    hash_str = f"{fecha_mov}{descripcion_mov}{monto_mov}MANUAL{datetime.now()}"
                    hash_mov = hashlib.sha256(hash_str.encode()).hexdigest()[:32]
                    
                    # Insertar movimiento
                    cursor.execute("""
                        INSERT INTO movimientos_bancarios 
                        (periodo_id, banco, fecha, descripcion, referencia, categoria, tipo, 
                         debito, credito, saldo, es_traspaso_interno, hash_movimiento)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        periodo_id,
                        'MANUAL',
                        fecha_mov,
                        descripcion_mov,
                        referencia_mov,
                        categoria_mov,
                        tipo_db,
                        debito,
                        credito,
                        0,
                        False,  # No es traspaso
                        hash_mov
                    ))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    tipo_texto = "Ingreso" if es_ingreso else "Gasto"
                    st.success(f"✅ {tipo_texto} guardado: ${monto_mov:,.2f} - {descripcion_mov}")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    st.divider()
    
    # Mostrar movimientos manuales recientes
    st.subheader("📋 Movimientos Manuales Recientes")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, fecha, tipo, descripcion, referencia, categoria, debito, credito
            FROM movimientos_bancarios
            WHERE banco = 'MANUAL'
            ORDER BY fecha DESC, created_at DESC
            LIMIT 20
        """)
        movimientos_manuales = cursor.fetchall()
        
        if movimientos_manuales:
            df_mov = pd.DataFrame(movimientos_manuales)
            df_mov['monto'] = df_mov.apply(
                lambda x: float(x['credito']) if float(x['credito']) > 0 else float(x['debito']),
                axis=1
            )
            df_mov['tipo_display'] = df_mov['tipo'].map({
                'CREDITO': '📈 Ingreso',
                'DEBITO': '📉 Egreso',
                'TRASPASO_INTERNO': '🔄 Traspaso'
            })
            
            st.dataframe(
                df_mov[['fecha', 'tipo_display', 'descripcion', 'categoria', 'monto']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "tipo_display": "Tipo",
                    "monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
                }
            )
            
            # Opción de eliminar
            st.subheader("🗑️ Eliminar Movimiento Manual")
            ids_disponibles = [m['id'] for m in movimientos_manuales]
            descripciones = {m['id']: f"{m['fecha']} - {m['descripcion'][:30]}..." for m in movimientos_manuales}
            
            mov_eliminar = st.selectbox(
                "Seleccionar movimiento a eliminar",
                options=ids_disponibles,
                format_func=lambda x: descripciones.get(x, str(x))
            )
            
            if st.button("🗑️ Eliminar", key="btn_eliminar_mov_manual"):
                cursor.execute("DELETE FROM movimientos_bancarios WHERE id = %s AND banco = 'MANUAL'", (mov_eliminar,))
                conn.commit()
                st.success("✅ Movimiento eliminado")
                st.rerun()
        else:
            st.info("No hay movimientos manuales cargados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# TAB 2: TRASPASOS ENTRE CUENTAS
# ============================================
with tab2:
    st.subheader("🔄 Registrar Traspaso entre Cuentas")
    st.caption("Movimiento de dinero entre cuentas propias (no afecta el resultado operativo)")
    
    with st.form("form_traspaso"):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_traspaso = st.date_input(
                "Fecha del traspaso",
                value=date.today(),
                format="DD/MM/YYYY",
                key="fecha_traspaso"
            )
            
            monto_traspaso = st.number_input(
                "Monto ($)",
                min_value=0.0,
                step=1000.0,
                format="%.2f",
                key="monto_traspaso"
            )
            
            cuenta_origen = st.selectbox(
                "Cuenta ORIGEN (sale el dinero)",
                options=list(CUENTAS_BANCARIAS.keys()),
                format_func=lambda x: CUENTAS_BANCARIAS[x],
                key="cuenta_origen"
            )
        
        with col2:
            descripcion_traspaso = st.text_input(
                "Descripción/Motivo",
                placeholder="Ej: Pago a proveedor desde cta Macro",
                key="desc_traspaso"
            )
            
            referencia_traspaso = st.text_input(
                "Referencia (opcional)",
                placeholder="Ej: Transferencia #123",
                key="ref_traspaso"
            )
            
            cuenta_destino = st.selectbox(
                "Cuenta DESTINO (entra el dinero)",
                options=list(CUENTAS_BANCARIAS.keys()),
                format_func=lambda x: CUENTAS_BANCARIAS[x],
                key="cuenta_destino"
            )
        
        submitted_traspaso = st.form_submit_button("💾 Registrar Traspaso", type="primary")
        
        if submitted_traspaso:
            if monto_traspaso <= 0:
                st.error("El monto debe ser mayor a 0")
            elif cuenta_origen == cuenta_destino:
                st.error("La cuenta origen y destino deben ser diferentes")
            elif not descripcion_traspaso:
                st.error("Ingresá una descripción")
            else:
                try:
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    
                    # Obtener o crear período
                    anio = fecha_traspaso.year
                    mes = fecha_traspaso.month
                    
                    cursor.execute(
                        "SELECT id FROM periodos WHERE anio = %s AND mes = %s",
                        (anio, mes)
                    )
                    periodo = cursor.fetchone()
                    
                    if not periodo:
                        cursor.execute(
                            "INSERT INTO periodos (anio, mes) VALUES (%s, %s)",
                            (anio, mes)
                        )
                        periodo_id = cursor.lastrowid
                    else:
                        periodo_id = periodo['id']
                    
                    # Crear descripción detallada
                    desc_completa = f"{descripcion_traspaso} | {CUENTAS_BANCARIAS[cuenta_origen]} → {CUENTAS_BANCARIAS[cuenta_destino]}"
                    
                    # Generar hash único para el par de movimientos
                    hash_base = f"{fecha_traspaso}{monto_traspaso}{cuenta_origen}{cuenta_destino}{datetime.now()}"
                    
                    # 1. Movimiento de SALIDA (débito en cuenta origen)
                    hash_salida = hashlib.sha256(f"{hash_base}SALIDA".encode()).hexdigest()[:32]
                    cursor.execute("""
                        INSERT INTO movimientos_bancarios 
                        (periodo_id, banco, fecha, descripcion, referencia, categoria, tipo, 
                         debito, credito, saldo, es_traspaso_interno, hash_movimiento)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        periodo_id,
                        cuenta_origen,
                        fecha_traspaso,
                        f"TRASPASO A {CUENTAS_BANCARIAS[cuenta_destino]}: {descripcion_traspaso}",
                        referencia_traspaso,
                        '*** Traspasos entre Cuentas Propias ***',
                        'TRASPASO_INTERNO',
                        monto_traspaso,  # Débito (sale)
                        0,
                        0,
                        True,
                        hash_salida
                    ))
                    
                    # 2. Movimiento de ENTRADA (crédito en cuenta destino)
                    hash_entrada = hashlib.sha256(f"{hash_base}ENTRADA".encode()).hexdigest()[:32]
                    cursor.execute("""
                        INSERT INTO movimientos_bancarios 
                        (periodo_id, banco, fecha, descripcion, referencia, categoria, tipo, 
                         debito, credito, saldo, es_traspaso_interno, hash_movimiento)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        periodo_id,
                        cuenta_destino,
                        fecha_traspaso,
                        f"TRASPASO DE {CUENTAS_BANCARIAS[cuenta_origen]}: {descripcion_traspaso}",
                        referencia_traspaso,
                        '*** Traspasos entre Cuentas Propias ***',
                        'TRASPASO_INTERNO',
                        0,
                        monto_traspaso,  # Crédito (entra)
                        0,
                        True,
                        hash_entrada
                    ))
                    
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    st.success(f"✅ Traspaso registrado: ${monto_traspaso:,.2f} de {CUENTAS_BANCARIAS[cuenta_origen]} a {CUENTAS_BANCARIAS[cuenta_destino]}")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    st.divider()
    
    # Mostrar traspasos recientes
    st.subheader("📋 Traspasos Recientes")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, fecha, banco, descripcion, debito, credito
            FROM movimientos_bancarios
            WHERE es_traspaso_interno = TRUE
            ORDER BY fecha DESC, created_at DESC
            LIMIT 30
        """)
        traspasos = cursor.fetchall()
        
        if traspasos:
            df_traspasos = pd.DataFrame(traspasos)
            df_traspasos['tipo'] = df_traspasos.apply(
                lambda x: '📤 Salida' if float(x['debito'] or 0) > 0 else '📥 Entrada',
                axis=1
            )
            df_traspasos['monto'] = df_traspasos.apply(
                lambda x: float(x['debito'] or 0) if float(x['debito'] or 0) > 0 else float(x['credito'] or 0),
                axis=1
            )
            
            st.dataframe(
                df_traspasos[['fecha', 'banco', 'tipo', 'descripcion', 'monto']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                    "banco": "Cuenta",
                    "monto": st.column_config.NumberColumn("Monto", format="$%.2f"),
                }
            )
            
            # Opción de eliminar traspasos
            st.subheader("🗑️ Eliminar Traspaso")
            ids_traspasos = [t['id'] for t in traspasos]
            desc_traspasos = {t['id']: f"{t['fecha']} - {t['banco']} - {t['descripcion'][:30]}..." for t in traspasos}
            
            traspaso_eliminar = st.selectbox(
                "Seleccionar traspaso a eliminar",
                options=ids_traspasos,
                format_func=lambda x: desc_traspasos.get(x, str(x)),
                key="traspaso_eliminar"
            )
            
            if st.button("🗑️ Eliminar Traspaso", key="btn_eliminar_traspaso"):
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM movimientos_bancarios WHERE id = %s", (traspaso_eliminar,))
                    conn.commit()
                    cursor.close()
                    st.success("✅ Traspaso eliminado")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {str(e)}")
        else:
            st.info("No hay traspasos registrados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# TAB 3: INGRESOS EFECTIVO / RETIROS
# ============================================
with tab3:
    st.subheader("💵 Registrar Ingresos en Efectivo (Retiros)")
    st.caption("Total de dinero en efectivo recibido por ventas en el período")
    
    st.info("""
    **¿Qué son los Retiros?**
    Es el dinero en efectivo que se retira de caja por ventas realizadas.
    Este ingreso NO pasa por bancos, pero es parte del flujo de caja.
    """)
    
    with st.form("form_ingreso_efectivo"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Selector de mes y año
            anio_retiro = st.selectbox(
                "Año",
                options=list(range(datetime.now().year, datetime.now().year - 3, -1)),
                index=0,
                key="anio_retiro"
            )
            
            mes_retiro = st.selectbox(
                "Mes",
                options=list(range(1, 13)),
                format_func=lambda x: [
                    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
                ][x-1],
                index=datetime.now().month - 1,
                key="mes_retiro"
            )
        
        with col2:
            monto_retiro = st.number_input(
                "Total Retiros del Mes ($)",
                min_value=0.0,
                step=10000.0,
                format="%.2f",
                key="monto_retiro",
                help="Total de efectivo retirado de caja en el mes"
            )
            
            descripcion_retiro = st.text_input(
                "Descripción (opcional)",
                value="Retiro mensual por ventas en efectivo",
                key="desc_retiro"
            )
        
        submitted_retiro = st.form_submit_button("💾 Registrar Ingreso Efectivo", type="primary")
        
        if submitted_retiro:
            if monto_retiro <= 0:
                st.error("El monto debe ser mayor a 0")
            else:
                try:
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    
                    # Buscar o crear período
                    cursor.execute("""
                        SELECT id FROM periodos 
                        WHERE anio = %s AND mes = %s
                    """, (anio_retiro, mes_retiro))
                    
                    periodo = cursor.fetchone()
                    
                    if not periodo:
                        # Crear período
                        from datetime import date as date_class
                        import calendar
                        ultimo_dia = calendar.monthrange(anio_retiro, mes_retiro)[1]
                        
                        cursor.execute("""
                            INSERT INTO periodos (anio, mes, fecha_inicio, fecha_fin)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            anio_retiro, mes_retiro,
                            date_class(anio_retiro, mes_retiro, 1),
                            date_class(anio_retiro, mes_retiro, ultimo_dia)
                        ))
                        conn.commit()
                        periodo_id = cursor.lastrowid
                    else:
                        periodo_id = periodo['id']
                    
                    # Verificar si ya existe un registro de retiro para este mes
                    cursor.execute("""
                        SELECT id, credito FROM movimientos_bancarios 
                        WHERE periodo_id = %s AND banco = 'EFECTIVO' 
                        AND categoria = 'Retiros Ventas Efectivo'
                    """, (periodo_id,))
                    
                    retiro_existente = cursor.fetchone()
                    
                    # Generar hash único
                    hash_str = f"RETIRO_EFECTIVO_{anio_retiro}_{mes_retiro}_{monto_retiro}"
                    hash_mov = hashlib.md5(hash_str.encode()).hexdigest()
                    
                    # Fecha del movimiento (último día del mes)
                    import calendar
                    from datetime import date as date_class
                    ultimo_dia = calendar.monthrange(anio_retiro, mes_retiro)[1]
                    fecha_retiro = date_class(anio_retiro, mes_retiro, ultimo_dia)
                    
                    if retiro_existente:
                        # Actualizar existente
                        cursor.execute("""
                            UPDATE movimientos_bancarios 
                            SET credito = %s, descripcion = %s, fecha = %s
                            WHERE id = %s
                        """, (monto_retiro, descripcion_retiro, fecha_retiro, retiro_existente['id']))
                        conn.commit()
                        st.success(f"✅ Retiro actualizado: ${monto_retiro:,.2f} (anterior: ${float(retiro_existente['credito']):,.2f})")
                    else:
                        # Crear nuevo
                        cursor.execute("""
                            INSERT INTO movimientos_bancarios
                            (periodo_id, banco, fecha, descripcion, referencia, categoria, tipo,
                             debito, credito, saldo, es_traspaso_interno, hash_movimiento)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            periodo_id, 'EFECTIVO', fecha_retiro,
                            descripcion_retiro, '', 'Retiros Ventas Efectivo', 'CREDITO',
                            0, monto_retiro, 0, False, hash_mov
                        ))
                        conn.commit()
                        st.success(f"✅ Retiro registrado: ${monto_retiro:,.2f}")
                    
                    cursor.close()
                    conn.close()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error al guardar: {str(e)}")
    
    # Mostrar retiros registrados
    st.markdown("---")
    st.subheader("📋 Retiros Registrados")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT m.id, p.anio, p.mes, m.credito, m.descripcion, m.fecha
            FROM movimientos_bancarios m
            JOIN periodos p ON m.periodo_id = p.id
            WHERE m.banco = 'EFECTIVO' AND m.categoria = 'Retiros Ventas Efectivo'
            ORDER BY p.anio DESC, p.mes DESC
        """)
        
        retiros = cursor.fetchall()
        
        if retiros:
            df_retiros = pd.DataFrame(retiros)
            df_retiros['periodo'] = df_retiros.apply(lambda r: f"{r['mes']:02d}/{r['anio']}", axis=1)
            
            st.dataframe(
                df_retiros[['periodo', 'credito', 'descripcion']].rename(columns={
                    'periodo': 'Período',
                    'credito': 'Monto',
                    'descripcion': 'Descripción'
                }),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Monto": st.column_config.NumberColumn(format="$%.2f"),
                }
            )
            
            total_retiros = sum(float(r['credito']) for r in retiros)
            st.metric("Total Retiros Registrados", f"${total_retiros:,.2f}")
            
            # Opción de eliminar retiro
            st.subheader("🗑️ Eliminar Retiro")
            ids_retiros = [r['id'] for r in retiros]
            desc_retiros = {r['id']: f"{r['mes']:02d}/{r['anio']} - ${float(r['credito']):,.2f}" for r in retiros}
            
            retiro_eliminar = st.selectbox(
                "Seleccionar retiro a eliminar",
                options=ids_retiros,
                format_func=lambda x: desc_retiros.get(x, str(x)),
                key="retiro_eliminar"
            )
            
            if st.button("🗑️ Eliminar Retiro", key="btn_eliminar_retiro"):
                try:
                    cursor.execute("DELETE FROM movimientos_bancarios WHERE id = %s", (retiro_eliminar,))
                    conn.commit()
                    st.success("✅ Retiro eliminado")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {str(e)}")
        else:
            st.info("No hay retiros registrados")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# TAB 4: VENTAS MENSUALES
# ============================================
with tab4:
    st.subheader("Cargar Venta Mensual")
    st.caption("Un solo registro por mes con el total de ventas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Selector de mes y año
        anio_venta = st.selectbox(
            "Año",
            options=list(range(datetime.now().year, datetime.now().year - 3, -1)),
            index=0
        )
        
        mes_venta = st.selectbox(
            "Mes",
            options=list(range(1, 13)),
            format_func=lambda x: [
                "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
            ][x-1],
            index=datetime.now().month - 1
        )
    
    with col2:
        venta_pesos = st.number_input(
            "Venta Total en Pesos ($)",
            min_value=0.0,
            step=1000.0,
            format="%.2f"
        )
        
        venta_kgs = st.number_input(
            "Venta Total en Kilogramos (kg)",
            min_value=0.0,
            step=10.0,
            format="%.2f"
        )
    
    # Mostrar precio promedio calculado
    if venta_kgs > 0 and venta_pesos > 0:
        precio_promedio = venta_pesos / venta_kgs
        st.info(f"💰 **Precio promedio por kg:** ${precio_promedio:,.2f}")
    
    sucursal_venta = st.text_input(
        "Sucursal (opcional)",
        value="PILAR",
        placeholder="Nombre de la sucursal"
    )
    
    # Verificar si ya existe venta para ese mes
    venta_existente = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT v.id, v.venta_pesos, v.venta_kgs 
            FROM ventas_mensuales v
            JOIN periodos p ON v.periodo_id = p.id
            WHERE p.anio = %s AND p.mes = %s
            LIMIT 1
        """, (anio_venta, mes_venta))
        
        venta_existente = cursor.fetchone()
        cursor.close()
        conn.close()
    except:
        pass
    
    # Mostrar advertencia si existe
    reemplazar = False
    if venta_existente:
        st.warning(f"""
        ⚠️ Ya existe una venta para {mes_venta:02d}/{anio_venta}:
        - Pesos: ${float(venta_existente['venta_pesos']):,.2f}
        - Kgs: {float(venta_existente['venta_kgs']):,.2f}
        """)
        reemplazar = st.checkbox("Reemplazar venta existente", key="confirm_replace_venta")
    
    # Botón guardar
    btn_label = "🔄 Actualizar Venta" if venta_existente else "💾 Guardar Venta Mensual"
    btn_disabled = bool(venta_existente) and not reemplazar
    
    if st.button(btn_label, type="primary", disabled=btn_disabled):
        if venta_pesos <= 0 and venta_kgs <= 0:
            st.error("Ingresá al menos venta en pesos o en kgs")
        else:
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                
                if venta_existente:
                    # Actualizar existente
                    cursor.execute("""
                        UPDATE ventas_mensuales 
                        SET venta_pesos = %s, venta_kgs = %s, sucursal = %s, fecha = %s
                        WHERE id = %s
                    """, (
                        venta_pesos,
                        venta_kgs,
                        sucursal_venta,
                        date(anio_venta, mes_venta, 1),
                        venta_existente['id']
                    ))
                    conn.commit()
                    st.success(f"✅ Venta actualizada para {mes_venta:02d}/{anio_venta}")
                else:
                    # Crear período si no existe
                    cursor.execute(
                        "SELECT id FROM periodos WHERE anio = %s AND mes = %s",
                        (anio_venta, mes_venta)
                    )
                    periodo = cursor.fetchone()
                    
                    if not periodo:
                        cursor.execute(
                            "INSERT INTO periodos (anio, mes) VALUES (%s, %s)",
                            (anio_venta, mes_venta)
                        )
                        periodo_id = cursor.lastrowid
                    else:
                        periodo_id = periodo['id']
                    
                    # Insertar venta
                    cursor.execute("""
                        INSERT INTO ventas_mensuales 
                        (periodo_id, fecha, venta_pesos, venta_kgs, sucursal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        periodo_id,
                        date(anio_venta, mes_venta, 1),
                        venta_pesos,
                        venta_kgs,
                        sucursal_venta
                    ))
                    conn.commit()
                    st.success(f"✅ Venta guardada para {mes_venta:02d}/{anio_venta}")
                
                cursor.close()
                conn.close()
                st.rerun()
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    st.divider()
    
    # Mostrar ventas cargadas
    st.subheader("📊 Ventas Mensuales Cargadas")
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                v.id,
                p.anio,
                p.mes,
                v.venta_pesos,
                v.venta_kgs,
                CASE 
                    WHEN v.venta_kgs > 0 THEN v.venta_pesos / v.venta_kgs 
                    ELSE 0 
                END as precio_promedio_kg,
                v.sucursal
            FROM ventas_mensuales v
            JOIN periodos p ON v.periodo_id = p.id
            ORDER BY p.anio DESC, p.mes DESC
        """)
        ventas = cursor.fetchall()
        
        if ventas:
            df_ventas = pd.DataFrame(ventas)
            df_ventas['periodo'] = df_ventas.apply(
                lambda x: f"{x['mes']:02d}/{x['anio']}", axis=1
            )
            
            st.dataframe(
                df_ventas[['periodo', 'venta_pesos', 'venta_kgs', 'precio_promedio_kg', 'sucursal']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "periodo": "Período",
                    "venta_pesos": st.column_config.NumberColumn("Venta ($)", format="$%.2f"),
                    "venta_kgs": st.column_config.NumberColumn("Venta (kg)", format="%.2f kg"),
                    "precio_promedio_kg": st.column_config.NumberColumn("$/kg Promedio", format="$%.2f"),
                    "sucursal": "Sucursal"
                }
            )
            
            # Opción de eliminar venta
            st.subheader("🗑️ Eliminar Venta Mensual")
            ids_ventas = [v['id'] for v in ventas]
            desc_ventas = {v['id']: f"{v['mes']:02d}/{v['anio']} - ${float(v['venta_pesos']):,.2f}" for v in ventas}
            
            venta_eliminar = st.selectbox(
                "Seleccionar venta a eliminar",
                options=ids_ventas,
                format_func=lambda x: desc_ventas.get(x, str(x)),
                key="venta_eliminar"
            )
            
            if st.button("🗑️ Eliminar Venta", key="btn_eliminar_venta"):
                try:
                    cursor.execute("DELETE FROM ventas_mensuales WHERE id = %s", (venta_eliminar,))
                    conn.commit()
                    st.success("✅ Venta eliminada")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {str(e)}")
            
            # Gráfico de evolución
            if len(ventas) > 1:
                st.subheader("📈 Evolución de Ventas")
                
                df_chart = df_ventas.copy()
                df_chart = df_chart.sort_values(['anio', 'mes'])
                df_chart['periodo_orden'] = df_chart['periodo']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Ventas en Pesos**")
                    st.bar_chart(df_chart.set_index('periodo_orden')['venta_pesos'])
                
                with col2:
                    st.write("**Ventas en Kg**")
                    st.bar_chart(df_chart.set_index('periodo_orden')['venta_kgs'])
        else:
            st.info("No hay ventas cargadas")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================
# INFORMACIÓN
# ============================================
st.divider()

with st.expander("ℹ️ Ayuda"):
    st.markdown("""
    ### Gastos Manuales
    Usá esta opción para agregar gastos que no aparecen en los extractos bancarios:
    - Pagos en efectivo
    - Gastos menores
    - Compras sin factura
    - Cualquier egreso que quieras registrar manualmente
    
    Los gastos manuales aparecen con banco = "MANUAL" y se incluyen en el EERR.
    
    ### Ventas Mensuales
    Cargá el total de ventas del mes:
    - Solo un registro por mes
    - Podés actualizar si ya existe
    - El precio promedio por kg se calcula automáticamente
    
    ### Categorías Disponibles
    
    **Egresos:**
    """)
    
    for cat in categorias_egresos:
        st.write(f"- {cat}")
    
    st.markdown("**Ingresos:**")
    for cat in categorias_ingresos:
        st.write(f"- {cat}")
