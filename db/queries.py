"""
Consultas SQL para el sistema de gestión financiera.
"""
import hashlib
import os
import sys
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CATEGORIAS_EGRESO_EXCLUIDAS_EERR

from .connection import get_connection


def generar_hash_movimiento(fecha, descripcion: str, monto: float) -> str:
    """Genera un hash único para identificar un movimiento."""
    texto = f"{fecha}|{descripcion}|{monto:.2f}"
    return hashlib.sha256(texto.encode()).hexdigest()[:64]


# =============================================================================
# PERÍODOS
# =============================================================================

def obtener_o_crear_periodo(anio: int, mes: int, fecha_inicio: date = None, fecha_fin: date = None) -> int:
    """Obtiene o crea un período y devuelve su ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar si existe
        cursor.execute(
            "SELECT id FROM periodos WHERE anio = %s AND mes = %s",
            (anio, mes)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
        
        # Crear nuevo período
        cursor.execute(
            """INSERT INTO periodos (anio, mes, fecha_inicio, fecha_fin) 
               VALUES (%s, %s, %s, %s)""",
            (anio, mes, fecha_inicio, fecha_fin)
        )
        conn.commit()
        return cursor.lastrowid
        
    finally:
        cursor.close()
        conn.close()


def obtener_periodos() -> List[Dict]:
    """Obtiene todos los períodos disponibles."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                p.*,
                COUNT(DISTINCT m.id) as total_movimientos,
                COALESCE(SUM(m.credito), 0) as total_creditos,
                COALESCE(SUM(m.debito), 0) as total_debitos
            FROM periodos p
            LEFT JOIN movimientos_bancarios m ON p.id = m.periodo_id
            GROUP BY p.id
            ORDER BY p.anio DESC, p.mes DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def crear_periodo(anio: int, mes: int, fecha_inicio: date = None, fecha_fin: date = None) -> int:
    """Crea un nuevo período."""
    return obtener_o_crear_periodo(anio, mes, fecha_inicio, fecha_fin)


def cerrar_periodo(periodo_id: int) -> bool:
    """Cierra un período para evitar modificaciones."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE periodos SET cerrado = TRUE WHERE id = %s",
            (periodo_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# MOVIMIENTOS BANCARIOS
# =============================================================================

def guardar_movimientos(movimientos: List[Dict], banco: str, periodo_id: int) -> Tuple[int, int]:
    """
    Guarda movimientos bancarios en la base de datos.
    Detecta duplicados por hash.
    
    Returns:
        Tuple[int, int]: (nuevos insertados, duplicados ignorados)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    nuevos = 0
    duplicados = 0
    
    try:
        for mov in movimientos:
            # Generar hash para detectar duplicados
            monto = mov.get('credito', 0) or mov.get('debito', 0)
            hash_mov = generar_hash_movimiento(mov['fecha'], mov['descripcion'], monto)
            
            # Verificar si ya existe
            cursor.execute(
                "SELECT id FROM movimientos_bancarios WHERE hash_movimiento = %s",
                (hash_mov,)
            )
            
            if cursor.fetchone():
                duplicados += 1
                continue
            
            # Insertar nuevo movimiento
            cursor.execute("""
                INSERT INTO movimientos_bancarios 
                (periodo_id, banco, fecha, descripcion, referencia, categoria, tipo, 
                 debito, credito, saldo, es_traspaso_interno, hash_movimiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                periodo_id,
                banco,
                mov['fecha'],
                mov.get('descripcion', ''),
                mov.get('referencia', ''),
                mov.get('categoria', ''),
                mov.get('tipo', 'CREDITO' if mov.get('credito', 0) > 0 else 'DEBITO'),
                mov.get('debito', 0),
                mov.get('credito', 0),
                mov.get('saldo', 0),
                mov.get('es_traspaso_interno', False),
                hash_mov
            ))
            nuevos += 1
        
        conn.commit()
        return nuevos, duplicados
        
    finally:
        cursor.close()
        conn.close()


def obtener_movimientos_periodo(
    periodo_id: int = None,
    anio: int = None,
    mes: int = None,
    banco: str = None,
    incluir_traspasos: bool = True
) -> List[Dict]:
    """Obtiene movimientos de un período."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT m.*, p.anio, p.mes
            FROM movimientos_bancarios m
            JOIN periodos p ON m.periodo_id = p.id
            WHERE 1=1
        """
        params = []
        
        if periodo_id:
            query += " AND m.periodo_id = %s"
            params.append(periodo_id)
        
        if anio:
            query += " AND p.anio = %s"
            params.append(anio)
        
        if mes:
            query += " AND p.mes = %s"
            params.append(mes)
        
        if banco:
            query += " AND m.banco = %s"
            params.append(banco)
        
        if not incluir_traspasos:
            query += " AND m.es_traspaso_interno = FALSE"
        
        query += " ORDER BY m.fecha, m.id"
        
        cursor.execute(query, params)
        return cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()


def obtener_eerr_periodo(
    periodo_id: int = None,
    anio: int = None,
    mes: int = None
) -> Dict:
    """
    Genera el EERR (Estado de Resultados) para un período.
    """
    movimientos = obtener_movimientos_periodo(
        periodo_id=periodo_id,
        anio=anio,
        mes=mes
    )
    
    ingresos = defaultdict(float)
    egresos = defaultdict(float)
    traspasos_entrada = 0.0
    traspasos_salida = 0.0
    
    for mov in movimientos:
        if mov['es_traspaso_interno']:
            if mov['credito'] > 0:
                traspasos_entrada += float(mov['credito'])
            if mov['debito'] > 0:
                traspasos_salida += float(mov['debito'])
        else:
            categoria = mov.get('categoria', 'Sin categoría')
            if mov['credito'] > 0:
                ingresos[categoria] += float(mov['credito'])
            if mov['debito'] > 0:
                egresos[categoria] += float(mov['debito'])
    
    total_ingresos = sum(ingresos.values())
    total_egresos = sum(egresos.values())
    
    return {
        'ingresos': dict(ingresos),
        'egresos': dict(egresos),
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'resultado_neto': total_ingresos - total_egresos,
        'traspasos_entrada': traspasos_entrada,
        'traspasos_salida': traspasos_salida,
        'traspasos_neto': traspasos_entrada - traspasos_salida,
    }


# =============================================================================
# VENTAS
# =============================================================================

def guardar_ventas(ventas: List[Dict], periodo_id: int) -> Tuple[int, int]:
    """Guarda ventas en la base de datos."""
    conn = get_connection()
    cursor = conn.cursor()
    
    nuevos = 0
    
    try:
        for venta in ventas:
            cursor.execute("""
                INSERT INTO ventas_mensuales 
                (periodo_id, fecha, venta_pesos, venta_kgs, sucursal)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                periodo_id,
                venta['fecha'],
                venta.get('venta_pesos', 0),
                venta.get('venta_kgs', 0),
                venta.get('sucursal', '')
            ))
            nuevos += 1
        
        conn.commit()
        return nuevos, 0
        
    finally:
        cursor.close()
        conn.close()


def obtener_ventas_periodo(periodo_id: int = None, anio: int = None, mes: int = None) -> List[Dict]:
    """Obtiene ventas de un período."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT v.*, p.anio, p.mes
            FROM ventas_mensuales v
            JOIN periodos p ON v.periodo_id = p.id
            WHERE 1=1
        """
        params = []
        
        if periodo_id:
            query += " AND v.periodo_id = %s"
            params.append(periodo_id)
        
        if anio:
            query += " AND p.anio = %s"
            params.append(anio)
        
        if mes:
            query += " AND p.mes = %s"
            params.append(mes)
        
        query += " ORDER BY v.fecha"
        
        cursor.execute(query, params)
        return cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# PAGOS EN EFECTIVO
# =============================================================================

def guardar_pagos_efectivo(pagos: List[Dict], periodo_id: int) -> Tuple[int, int]:
    """Guarda pagos en efectivo en la base de datos."""
    conn = get_connection()
    cursor = conn.cursor()
    
    nuevos = 0
    duplicados = 0
    
    try:
        for pago in pagos:
            # Generar hash para detectar duplicados
            hash_pago = generar_hash_movimiento(
                pago['fecha'],
                pago.get('concepto', ''),
                pago.get('monto', 0)
            )
            
            # Verificar si ya existe
            cursor.execute(
                "SELECT id FROM pagos_efectivo WHERE hash_pago = %s",
                (hash_pago,)
            )
            
            if cursor.fetchone():
                duplicados += 1
                continue
            
            cursor.execute("""
                INSERT INTO pagos_efectivo 
                (periodo_id, fecha, concepto, monto, categoria, hash_pago)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                periodo_id,
                pago['fecha'],
                pago.get('concepto', ''),
                pago.get('monto', 0),
                pago.get('categoria', ''),
                hash_pago
            ))
            nuevos += 1
        
        conn.commit()
        return nuevos, duplicados
        
    finally:
        cursor.close()
        conn.close()


def obtener_pagos_efectivo_periodo(periodo_id: int = None, anio: int = None, mes: int = None) -> List[Dict]:
    """Obtiene pagos en efectivo de un período."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT pe.*, p.anio, p.mes
            FROM pagos_efectivo pe
            JOIN periodos p ON pe.periodo_id = p.id
            WHERE 1=1
        """
        params = []
        
        if periodo_id:
            query += " AND pe.periodo_id = %s"
            params.append(periodo_id)
        
        if anio:
            query += " AND p.anio = %s"
            params.append(anio)
        
        if mes:
            query += " AND p.mes = %s"
            params.append(mes)
        
        query += " ORDER BY pe.fecha"
        
        cursor.execute(query, params)
        return cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# EERR OPERATIVO (Ventas vs Egresos)
# =============================================================================

def obtener_eerr_operativo(periodo_id: int = None, anio: int = None, mes: int = None) -> Dict:
    """
    Genera el EERR Operativo real:
    - Ingresos = Ventas del período
    - Egresos = Gastos bancarios (débitos operativos) + Pagos en efectivo

    NO considera ingresos bancarios como ingresos operativos.
    Las categorías en CATEGORIAS_EGRESO_EXCLUIDAS_EERR (p. ej. transferencias enviadas)
    no cuentan como gasto operativo.
    """
    from collections import defaultdict

    # Obtener ventas del período
    ventas = obtener_ventas_periodo(periodo_id=periodo_id, anio=anio, mes=mes)
    
    # Calcular total de ventas
    total_ventas_pesos = sum(float(v.get('venta_pesos', 0) or 0) for v in ventas)
    total_ventas_kgs = sum(float(v.get('venta_kgs', 0) or 0) for v in ventas)
    precio_promedio_kg = total_ventas_pesos / total_ventas_kgs if total_ventas_kgs > 0 else 0
    
    # Obtener egresos bancarios (solo débitos, sin traspasos)
    movimientos = obtener_movimientos_periodo(
        periodo_id=periodo_id, 
        anio=anio, 
        mes=mes,
        incluir_traspasos=True  # Los traemos para separarlos después
    )
    
    egresos_bancarios = defaultdict(float)
    monto_transferencias_enviadas_excluido = 0.0
    traspasos_salida = 0.0
    traspasos_entrada = 0.0
    ingresos_bancarios = defaultdict(float)  # Para mostrar aparte (informativo)

    for mov in movimientos:
        if mov.get('es_traspaso_interno'):
            if mov['debito'] and float(mov['debito']) > 0:
                traspasos_salida += float(mov['debito'])
            if mov['credito'] and float(mov['credito']) > 0:
                traspasos_entrada += float(mov['credito'])
        else:
            categoria = mov.get('categoria', 'Sin categoría')
            if mov['debito'] and float(mov['debito']) > 0:
                monto_d = float(mov['debito'])
                if categoria in CATEGORIAS_EGRESO_EXCLUIDAS_EERR:
                    monto_transferencias_enviadas_excluido += monto_d
                else:
                    egresos_bancarios[categoria] += monto_d
            if mov['credito'] and float(mov['credito']) > 0:
                ingresos_bancarios[categoria] += float(mov['credito'])
    
    # Obtener pagos en efectivo
    pagos_efectivo = obtener_pagos_efectivo_periodo(periodo_id=periodo_id, anio=anio, mes=mes)
    
    egresos_efectivo = defaultdict(float)
    for pago in pagos_efectivo:
        categoria = pago.get('categoria', 'Pagos en Efectivo')
        monto = float(pago.get('monto', 0) or 0)
        egresos_efectivo[categoria] += monto
    
    # Consolidar todos los egresos
    egresos_totales = defaultdict(float)
    for cat, monto in egresos_bancarios.items():
        egresos_totales[cat] += monto
    for cat, monto in egresos_efectivo.items():
        egresos_totales[f"{cat} (Efectivo)"] += monto
    
    total_egresos = sum(egresos_totales.values())
    total_ingresos_bancarios = sum(ingresos_bancarios.values())

    return {
        # Ingresos operativos = Ventas
        'ventas_pesos': total_ventas_pesos,
        'ventas_kgs': total_ventas_kgs,
        'precio_promedio_kg': precio_promedio_kg,

        # Egresos consolidados (sin transferencias enviadas u otras exclusiones)
        'egresos': dict(egresos_totales),
        'egresos_bancarios': dict(egresos_bancarios),
        'egresos_efectivo': dict(egresos_efectivo),
        'total_egresos': total_egresos,
        'monto_transferencias_enviadas_excluido_eerr': monto_transferencias_enviadas_excluido,
        
        # Resultado operativo
        'resultado_operativo': total_ventas_pesos - total_egresos,
        'margen_operativo': (total_ventas_pesos - total_egresos) / total_ventas_pesos * 100 if total_ventas_pesos > 0 else 0,
        
        # Información adicional (no afecta resultado operativo)
        'ingresos_bancarios': dict(ingresos_bancarios),
        'total_ingresos_bancarios': total_ingresos_bancarios,
        'traspasos_entrada': traspasos_entrada,
        'traspasos_salida': traspasos_salida,
        'traspasos_neto': traspasos_entrada - traspasos_salida,
        
        # Flujo de caja (informativo): egresos bancarios incluye solo operativos en sum(...)
        'flujo_caja': total_ingresos_bancarios - sum(egresos_bancarios.values()) + traspasos_entrada - traspasos_salida,
    }


# =============================================================================
# ANÁLISIS Y REPORTES
# =============================================================================

def obtener_resumen_anual(anio: int) -> Dict:
    """
    Obtiene un resumen de todos los meses de un año.
    
    EERR Operativo:
    - Ingresos = Ventas del período
    - Egresos = Gastos bancarios (débitos) + Pagos en efectivo
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener datos por mes
        cursor.execute("""
            SELECT 
                p.id as periodo_id,
                p.mes,
                COALESCE((
                    SELECT SUM(venta_pesos) 
                    FROM ventas_mensuales 
                    WHERE periodo_id = p.id
                ), 0) as ventas_pesos,
                COALESCE((
                    SELECT SUM(venta_kgs) 
                    FROM ventas_mensuales 
                    WHERE periodo_id = p.id
                ), 0) as ventas_kgs,
                COALESCE((
                    SELECT SUM(debito) 
                    FROM movimientos_bancarios 
                    WHERE periodo_id = p.id AND es_traspaso_interno = FALSE
                    AND (categoria IS NULL OR categoria NOT IN ('Transferencias Enviadas'))
                ), 0) as egresos_bancarios,
                COALESCE((
                    SELECT SUM(monto) 
                    FROM pagos_efectivo 
                    WHERE periodo_id = p.id
                ), 0) as egresos_efectivo,
                COALESCE((
                    SELECT SUM(credito) 
                    FROM movimientos_bancarios 
                    WHERE periodo_id = p.id AND es_traspaso_interno = FALSE
                ), 0) as ingresos_bancarios
            FROM periodos p
            WHERE p.anio = %s
            ORDER BY p.mes
        """, (anio,))
        
        meses_raw = cursor.fetchall()
        
        # Procesar datos
        meses = []
        for m in meses_raw:
            egresos_total = float(m['egresos_bancarios'] or 0) + float(m['egresos_efectivo'] or 0)
            ventas = float(m['ventas_pesos'] or 0)
            
            meses.append({
                'mes': m['mes'],
                'ventas_pesos': ventas,
                'ventas_kgs': float(m['ventas_kgs'] or 0),
                'egresos_bancarios': float(m['egresos_bancarios'] or 0),
                'egresos_efectivo': float(m['egresos_efectivo'] or 0),
                'egresos': egresos_total,
                'ingresos_bancarios': float(m['ingresos_bancarios'] or 0),
                'resultado': ventas - egresos_total,
                'margen': (ventas - egresos_total) / ventas * 100 if ventas > 0 else 0
            })
        
        total_ventas = sum(m['ventas_pesos'] for m in meses)
        total_egresos = sum(m['egresos'] for m in meses)
        
        return {
            'anio': anio,
            'meses': meses,
            'total_ventas_pesos': total_ventas,
            'total_ventas_kgs': sum(m['ventas_kgs'] for m in meses),
            'total_egresos': total_egresos,
            'total_egresos_bancarios': sum(m['egresos_bancarios'] for m in meses),
            'total_egresos_efectivo': sum(m['egresos_efectivo'] for m in meses),
            'total_ingresos_bancarios': sum(m['ingresos_bancarios'] for m in meses),
            'resultado_operativo': total_ventas - total_egresos,
            'margen_operativo': (total_ventas - total_egresos) / total_ventas * 100 if total_ventas > 0 else 0,
        }
        
    finally:
        cursor.close()
        conn.close()


def obtener_comparativa_periodos(periodos_ids: List[int]) -> List[Dict]:
    """
    Obtiene datos comparativos de múltiples períodos.
    Usa el EERR Operativo (Ventas vs Egresos).
    """
    resultados = []
    
    for periodo_id in periodos_ids:
        eerr = obtener_eerr_operativo(periodo_id=periodo_id)
        
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute(
                "SELECT anio, mes FROM periodos WHERE id = %s",
                (periodo_id,)
            )
            periodo = cursor.fetchone()
            
            if periodo:
                # Crear resultado con claves específicas para evitar sobrescritura
                resultado = {
                    'periodo': f"{periodo['mes']:02d}/{periodo['anio']}",
                    'anio': periodo['anio'],
                    'mes': periodo['mes'],
                    'ventas': eerr.get('ventas_pesos', 0),
                    'egresos': eerr.get('total_egresos', 0),
                    'resultado': eerr.get('resultado_operativo', 0),
                    'margen': eerr.get('margen_operativo', 0),
                    # Datos adicionales para detalle (con nombres distintos)
                    'egresos_detalle': eerr.get('egresos', {}),
                    'ventas_kgs': eerr.get('ventas_kgs', 0),
                    'precio_promedio_kg': eerr.get('precio_promedio_kg', 0),
                }
                resultados.append(resultado)
        finally:
            cursor.close()
            conn.close()
    
    return resultados
