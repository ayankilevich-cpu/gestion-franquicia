"""
Página de Flujo de Caja - Base Caja (Cash Flow)
Muestra el dinero efectivamente cobrado vs pagado.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from collections import defaultdict

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.formato import formato_moneda, formato_porcentaje, formato_df_moneda, formato_df_porcentaje
from utils.flujo_caja import es_credito_deposito_efectivo_en_banco
from db.queries import (
    obtener_periodos,
    obtener_movimientos_periodo,
    obtener_pagos_efectivo_periodo,
    obtener_ventas_periodo,
)

st.set_page_config(page_title="Flujo de Caja", page_icon="💰", layout="wide")

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

st.title("💰 Flujo de Caja")
st.markdown("**Base Caja**: Dinero efectivamente cobrado vs pagado")

# Selector de período
periodos = obtener_periodos()

if not periodos:
    st.warning("No hay períodos cargados. Subí extractos bancarios primero.")
    st.stop()

# Crear opciones de período
opciones_periodo = {
    f"{p['mes']:02d}/{p['anio']}": p['id'] 
    for p in periodos
}

periodo_seleccionado = st.selectbox(
    "Seleccionar período:",
    options=list(opciones_periodo.keys()),
    index=0
)

periodo_id = opciones_periodo[periodo_seleccionado]

# Obtener datos
movimientos = obtener_movimientos_periodo(periodo_id=periodo_id, incluir_traspasos=True)
pagos_efectivo = obtener_pagos_efectivo_periodo(periodo_id=periodo_id)
ventas = obtener_ventas_periodo(periodo_id=periodo_id)

# =============================================================================
# CALCULAR FLUJO DE CAJA
# =============================================================================

# 1. INGRESOS (Cobros)
ingresos_bancarios = defaultdict(float)
ingresos_efectivo = defaultdict(float)  # Retiros por ventas en efectivo
traspasos_entrada = 0.0
depositos_efectivo = 0.0

for mov in movimientos:
    if mov['credito'] and float(mov['credito']) > 0:
        credito = float(mov['credito'])
        categoria = mov.get('categoria', 'Otros')
        banco = mov.get('banco', '')
        
        if mov.get('es_traspaso_interno'):
            traspasos_entrada += credito
        elif es_credito_deposito_efectivo_en_banco(mov):
            depositos_efectivo += credito
        elif banco == 'EFECTIVO':
            # Ingresos en efectivo (retiros por ventas)
            ingresos_efectivo[categoria] += credito
        else:
            ingresos_bancarios[categoria] += credito

# 2. EGRESOS (Pagos)
egresos_bancarios = defaultdict(float)
traspasos_salida = 0.0

for mov in movimientos:
    if mov['debito'] and float(mov['debito']) > 0:
        debito = float(mov['debito'])
        categoria = mov.get('categoria', 'Otros')
        
        if mov.get('es_traspaso_interno'):
            traspasos_salida += debito
        else:
            egresos_bancarios[categoria] += debito

egresos_efectivo = defaultdict(float)
for pago in pagos_efectivo:
    categoria = pago.get('categoria', 'Pagos Efectivo')
    monto = float(pago.get('monto', 0) or 0)
    egresos_efectivo[categoria] += monto

# Totales
total_ingresos_bancarios = sum(ingresos_bancarios.values())
total_ingresos_efectivo = sum(ingresos_efectivo.values())  # Retiros
total_egresos_bancarios = sum(egresos_bancarios.values())
total_egresos_efectivo = sum(egresos_efectivo.values())

# Venta sistema (para referencia)
venta_sistema = sum(float(v.get('venta_pesos', 0) or 0) for v in ventas)

total_ingresos_flujo = total_ingresos_bancarios + total_ingresos_efectivo
total_egresos_flujo = total_egresos_bancarios + total_egresos_efectivo
flujo_neto = total_ingresos_flujo - total_egresos_flujo

# =============================================================================
# MOSTRAR RESULTADOS
# =============================================================================

st.markdown("---")

# Métricas principales
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "💵 Cobrado (Bancos)", 
        formato_moneda(total_ingresos_bancarios, decimales=0),
        help="Créditos bancarios sin traspasos ni depósitos de efectivo"
    )

with col2:
    st.metric(
        "🏪 Retiros (Efectivo)", 
        formato_moneda(total_ingresos_efectivo, decimales=0),
        help="Ingresos en efectivo por ventas (retiros de caja)"
    )

with col3:
    st.metric(
        "💳 Pagado (Bancos)", 
        formato_moneda(total_egresos_bancarios, decimales=0),
        help="Débitos bancarios sin traspasos"
    )

with col4:
    st.metric(
        "💸 Pagado (Efectivo)", 
        formato_moneda(total_egresos_efectivo, decimales=0),
        help="Pagos realizados en efectivo"
    )

with col5:
    st.metric(
        "📊 Flujo Neto",
        formato_moneda(flujo_neto, decimales=0),
        delta=f"{'Positivo' if flujo_neto > 0 else 'Negativo'}",
        delta_color="normal" if flujo_neto > 0 else "inverse",
    )

if venta_sistema > 0 and flujo_neto > venta_sistema * 2:
    st.warning(
        "El flujo neto es muy superior a la venta de sistema. Suele indicar **depósitos de "
        "efectivo mal clasificados** (se cuentan como cobranza) o **créditos no operativos** "
        "(préstamos, etc.). Revisá el diagnóstico abajo."
    )

with st.expander("🔍 Diagnóstico: mayores créditos bancarios del período"):
    st.caption(
        "Solo movimientos con crédito que **sí** entran en «Cobrado (Bancos)». "
        "Si ves montos enormes que son depósitos de caja, revisá la categoría/descripción en el extracto."
    )
    cred_rows = []
    for m in movimientos:
        if m.get("es_traspaso_interno"):
            continue
        if (m.get("banco") or "") == "EFECTIVO":
            continue
        cr = float(m.get("credito") or 0)
        if cr <= 0:
            continue
        if es_credito_deposito_efectivo_en_banco(m):
            continue
        cred_rows.append(
            {
                "Fecha": m.get("fecha"),
                "Banco": m.get("banco"),
                "Categoría": m.get("categoria") or "",
                "Descripción": (m.get("descripcion") or "")[:80],
                "Crédito": cr,
            }
        )
    cred_rows.sort(key=lambda r: r["Crédito"], reverse=True)
    if cred_rows:
        st.dataframe(
            pd.DataFrame(cred_rows[:25]).style.format({"Crédito": formato_df_moneda}),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            },
        )
    else:
        st.info("No hay créditos bancarios operativos en este período.")

st.markdown("---")

# Comparación con venta sistema
st.subheader("📈 Comparación con Venta Sistema")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Venta Sistema", formato_moneda(venta_sistema, decimales=0))

with col2:
    # Total cobrado = Bancos + Retiros Efectivo (sin depósitos que son traspasos)
    cobrado_total = total_ingresos_bancarios + total_ingresos_efectivo
    st.metric(
        "Total Cobrado", 
        formato_moneda(cobrado_total, decimales=0),
        help="Créditos bancarios + Retiros en efectivo"
    )

with col3:
    pct_cobrado = (cobrado_total / venta_sistema * 100) if venta_sistema > 0 else 0
    st.metric(
        "% Cobrado vs Venta",
        formato_porcentaje(pct_cobrado)
    )

with col4:
    diferencia = venta_sistema - cobrado_total
    st.metric(
        "Diferencia",
        formato_moneda(diferencia, decimales=0),
        delta="Pendiente" if diferencia > 0 else "Excedente" if diferencia < 0 else "OK"
    )

st.markdown("---")

# Tabs para detalle
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 Ingresos Bancarios",
    "🏪 Retiros Efectivo",
    "📤 Egresos Bancarios", 
    "💵 Pagos Efectivo",
    "🔄 Traspasos"
])

with tab1:
    st.subheader("📥 Ingresos Bancarios por Categoría")
    
    if ingresos_bancarios:
        df_ingresos = pd.DataFrame([
            {"Categoría": k, "Monto": v, "%": v/total_ingresos_bancarios*100}
            for k, v in sorted(ingresos_bancarios.items(), key=lambda x: -x[1])
        ])
        
        st.dataframe(
            df_ingresos.style.format({"Monto": formato_df_moneda, "%": formato_df_porcentaje}),
            use_container_width=True,
            hide_index=True
        )
        
        st.metric("Total Ingresos Bancarios", formato_moneda(total_ingresos_bancarios))
    else:
        st.info("No hay ingresos bancarios en este período")

with tab2:
    st.subheader("🏪 Retiros en Efectivo (Ventas)")
    st.caption("Dinero recibido en efectivo por ventas - registrado manualmente")
    
    if ingresos_efectivo:
        df_retiros = pd.DataFrame([
            {"Categoría": k, "Monto": v, "%": v/total_ingresos_efectivo*100}
            for k, v in sorted(ingresos_efectivo.items(), key=lambda x: -x[1])
        ])
        
        st.dataframe(
            df_retiros.style.format({"Monto": formato_df_moneda, "%": formato_df_porcentaje}),
            use_container_width=True,
            hide_index=True
        )
        
        st.metric("Total Retiros Efectivo", formato_moneda(total_ingresos_efectivo))
    else:
        st.warning("⚠️ No hay retiros de efectivo registrados. Registralos en 'Carga Manual' → 'Ingresos Efectivo'")

with tab3:
    st.subheader("📤 Egresos Bancarios por Categoría")
    
    if egresos_bancarios:
        df_egresos = pd.DataFrame([
            {"Categoría": k, "Monto": v, "%": v/total_egresos_bancarios*100}
            for k, v in sorted(egresos_bancarios.items(), key=lambda x: -x[1])
        ])
        
        st.dataframe(
            df_egresos.style.format({"Monto": formato_df_moneda, "%": formato_df_porcentaje}),
            use_container_width=True,
            hide_index=True
        )
        
        st.metric("Total Egresos Bancarios", formato_moneda(total_egresos_bancarios))
    else:
        st.info("No hay egresos bancarios en este período")

with tab4:
    st.subheader("💵 Pagos en Efectivo por Categoría")
    
    if egresos_efectivo:
        df_efectivo = pd.DataFrame([
            {"Categoría": k, "Monto": v, "%": v/total_egresos_efectivo*100}
            for k, v in sorted(egresos_efectivo.items(), key=lambda x: -x[1])
        ])
        
        st.dataframe(
            df_efectivo.style.format({"Monto": formato_df_moneda, "%": formato_df_porcentaje}),
            use_container_width=True,
            hide_index=True
        )
        
        st.metric("Total Pagos Efectivo", formato_moneda(total_egresos_efectivo))
    else:
        st.info("No hay pagos en efectivo registrados")

with tab5:
    st.subheader("🔄 Traspasos entre Cuentas Propias")
    st.caption("Estos movimientos NO afectan el flujo de caja operativo")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Traspasos Entrada", formato_moneda(traspasos_entrada))
    
    with col2:
        st.metric("Traspasos Salida", formato_moneda(traspasos_salida))
    
    with col3:
        st.metric("Depósitos Efectivo→Banco", formato_moneda(depositos_efectivo))
    
    # Mostrar detalle de traspasos
    traspasos = [m for m in movimientos if m.get('es_traspaso_interno')]
    if traspasos:
        with st.expander("Ver detalle de traspasos"):
            df_traspasos = pd.DataFrame([
                {
                    "Fecha": m['fecha'],
                    "Banco": m['banco'],
                    "Descripción": m['descripcion'][:50],
                    "Débito": float(m['debito'] or 0),
                    "Crédito": float(m['credito'] or 0)
                }
                for m in traspasos
            ])
            st.dataframe(
                df_traspasos.style.format(
                    {"Débito": formato_df_moneda, "Crédito": formato_df_moneda}
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
                },
            )

# =============================================================================
# RESUMEN FINAL
# =============================================================================
st.markdown("---")
st.subheader("📊 Resumen Flujo de Caja")

resumen_data = {
    "Concepto": [
        "Cobrado en Bancos (sin traspasos)",
        "(+) Retiros Efectivo (ventas en efectivo)",
        "(-) Pagado en Bancos (sin traspasos)",
        "(-) Pagado en Efectivo",
        "= FLUJO NETO OPERATIVO",
        "",
        "Depósitos Efectivo→Banco (informativo)",
        "Traspasos Entrada (informativo)",
        "Traspasos Salida (informativo)",
    ],
    "Monto": [
        total_ingresos_bancarios,
        total_ingresos_efectivo,
        -total_egresos_bancarios,
        -total_egresos_efectivo,
        flujo_neto,
        None,
        depositos_efectivo,
        traspasos_entrada,
        traspasos_salida,
    ]
}

df_resumen = pd.DataFrame(resumen_data)
st.dataframe(
    df_resumen.style.format({"Monto": lambda x: formato_moneda(x) if x is not None else ""}),
    use_container_width=True,
    hide_index=True
)

# Nota explicativa
with st.expander("ℹ️ ¿Cómo interpretar el Flujo de Caja?"):
    st.markdown("""
    **Flujo de Caja vs EERR Operativo:**
    
    | Concepto | EERR Operativo | Flujo de Caja |
    |----------|----------------|---------------|
    | Ingresos | Venta de sistema | Dinero cobrado |
    | Egresos | Débitos + Efectivo | Débitos + Efectivo |
    | Mide | Rentabilidad comercial | Liquidez real |
    
    **El Flujo de Caja muestra:**
    - Cuánto dinero efectivamente entró
    - Cuánto dinero efectivamente salió
    - Si tenés superávit o déficit de caja
    
    **Los traspasos y depósitos** son movimientos internos entre tus cuentas,
    no afectan el resultado operativo.
    """)
