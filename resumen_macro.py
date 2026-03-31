"""
Script para procesar extractos bancarios del Banco Macro y generar un EERR (Estado de Resultados).
Extrae créditos y débitos, los categoriza y genera un resumen financiero.
"""

import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import pandas as pd

from utils.formato import formato_moneda

# Para leer PDFs - usar pdfplumber que es más preciso con tablas
try:
    import pdfplumber
except ImportError:
    print("Instalando pdfplumber...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'pdfplumber'])
    import pdfplumber


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# CUIT de la empresa (para detectar traspasos internos entre cuentas propias)
CUIT_EMPRESA = '30717192822'

# =============================================================================
# CONFIGURACIÓN DE CATEGORÍAS
# =============================================================================

# Categorías de INGRESOS (Créditos)
CATEGORIAS_INGRESOS = {
    'Ventas Posnet (CLOVER)': [
        'PAGO PCT',
    ],
    'Liquidaciones Tarjetas (PRISMA)': [
        'PAGO63796',
        'LIQ COMER PRISMA',
    ],
    'Cobranzas Tarjeta Naranja': [
        'TEF DATANET PR TARJETA NARANJA',
    ],
    'Transferencias Recibidas': [
        'TRANSF:',
        'TPUSH',
        '- NUMERO DE OPERACION',
    ],
    'Depósitos en Efectivo': [
        'DEPOSITO EN EFECTIVO',
    ],
    'Cobranzas Circuito Cerrado (Rapipago/etc)': [
        'CCERR',
    ],
    'Ajustes y Notas de Crédito': [
        'N/C ',
    ],
    'Cesión de Cheques': [
        # Se detecta automáticamente por descripción numérica larga
    ],
}

# Categorías de EGRESOS (Débitos)
CATEGORIAS_EGRESOS = {
    'Pago a Proveedores (Cheques)': [
        'PAGO DE CHEQUE',
        'CHEQUE CANJE',
    ],
    'Pagos Tarjeta de Crédito': [
        'DB TARJETA DE CREDITO',
    ],
    'Transferencias Enviadas': [
        'N/D TRANSF',
        'TRF MO CCDO',
        'COMISION TRANSFERE',
        'N/D COMISION TRF',
        'TRANSF 2',  # Transferencias con número
        'ACREDITACION CHEQUE REMESAS',
    ],
    'Sueldos y Jornales': [
        'N/D DB PAGO REMUNERACIONES',
    ],
    'Cargas Sociales (Obra Social/Sindicato)': [
        'TRANSF UNION OBR',
    ],
    'Impuestos AFIP (Ganancias/IVA/Otros)': [
        'IMP. AFIP',
        'AFIP ',
    ],
    'Impuesto Débitos y Créditos (Ley 25413)': [
        'N/D DBCR',
    ],
    'Impuestos Provinciales (IIBB/Sellos)': [
        'N/D DGR',
        'SELLOS CORDOBA',
    ],
    'IVA - Débito Fiscal': [
        'DEBITO FISCAL IVA',
    ],
    'IVA - Retenciones/Percepciones': [
        'RETENCION IVA',
    ],
    'Préstamos Bancarios': [
        'N/D DEBITO PRESTAMOS',
        'DEBITO PAGO PRESTAMO',
        'PAGO PRESTAMO',
        'Cobro de prestamo',
    ],
    'Intereses Bancarios': [
        'N/D INTER.ADEL.CC',
        'INTER.ADEL',
        'INTERESES',
    ],
    'Comisiones Bancarias': [
        'N/D COMISION CHEQUE',
        'N/D MANTENIMIENTO',
        'N/D COM.',
        'N/D COMISION CHQ',
    ],
    'Devoluciones a Clientes': [
        'DEV.COMPRA PCT',
    ],
    'Telefonía e Internet': [
        'PERSONAL FLOW',
        'MOVISTAR',
        'CLARO',
        'TELECOM',
    ],
    'Seguros': [
        'SAN CRISTOBAL',
        'SEGUROS',
    ],
    'Suscripciones y Servicios': [
        'DISNEY PLUS',
        'SPOTIFY',
        'NETFLIX',
    ],
    'Publicidad y Marketing': [
        'BANNER DIR',
    ],
    'Otros Egresos': [],  # Categoría residual
}


# =============================================================================
# FUNCIONES DE EXTRACCIÓN
# =============================================================================

def leer_pdf_texto(pdf_path: str) -> str:
    """Lee el PDF y extrae todo el texto."""
    texto_completo = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo.append(texto)
    return '\n'.join(texto_completo)


def parsear_monto(valor_str: str) -> float:
    """
    Convierte un string de monto argentino (1.234,56) a float.
    IMPORTANTE: Debe tener coma decimal para ser considerado monto válido.
    """
    if not valor_str or valor_str.strip() == '':
        return 0.0
    
    valor_str = valor_str.strip()
    
    # Un monto válido DEBE tener coma decimal (formato argentino)
    if ',' not in valor_str:
        return 0.0
    
    # Remover puntos de miles, cambiar coma por punto
    valor_str = valor_str.replace('.', '').replace(',', '.')
    try:
        return float(valor_str)
    except ValueError:
        return 0.0


def es_monto_valido(texto: str) -> bool:
    """Verifica si un texto parece ser un monto válido (tiene formato X.XXX,XX)."""
    # Patrón: números con puntos de miles opcionales y coma decimal obligatoria
    patron = r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$'
    return bool(re.match(patron, texto.strip()))


def extraer_movimientos(texto: str) -> list:
    """
    Extrae los movimientos bancarios del texto del extracto.
    """
    movimientos = []
    lineas = texto.split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        
        # Ignorar líneas no relevantes
        if not linea:
            continue
        
        # Debe empezar con fecha DD/MM/YY
        if not re.match(r'^\d{2}/\d{2}/\d{2}\s', linea):
            continue
        
        # Ignorar líneas de saldo
        if 'SALDO ULTIMO' in linea or 'SALDO FINAL' in linea:
            continue
        
        mov = parsear_linea_movimiento(linea)
        if mov:
            movimientos.append(mov)
    
    return movimientos


def parsear_linea_movimiento(linea: str) -> dict:
    """
    Parsea una línea de movimiento bancario del Banco Macro.
    
    Formatos posibles:
    1. DD/MM/YY DESCRIPCION REFERENCIA MONTO SALDO
    2. DD/MM/YY DESCRIPCION MONTO SALDO
    
    Los montos tienen formato: X.XXX,XX (con coma decimal)
    Las referencias son números enteros sin coma
    """
    
    # Extraer fecha
    match_fecha = re.match(r'^(\d{2}/\d{2}/\d{2})\s+(.+)', linea)
    if not match_fecha:
        return None
    
    fecha_str = match_fecha.group(1)
    resto = match_fecha.group(2)
    
    # Buscar todos los números con formato de monto (tienen coma decimal)
    # Patrón: X.XXX,XX o -X.XXX,XX
    patron_monto = r'-?\d{1,3}(?:\.\d{3})*,\d{2}'
    montos_encontrados = re.findall(patron_monto, resto)
    
    if len(montos_encontrados) < 2:
        # Necesitamos al menos monto de transacción y saldo
        return None
    
    # El último monto es el saldo
    saldo_str = montos_encontrados[-1]
    saldo = parsear_monto(saldo_str)
    
    # El penúltimo es el monto de la transacción
    monto_str = montos_encontrados[-2]
    monto = parsear_monto(monto_str)
    
    if monto == 0:
        return None
    
    # Extraer la descripción (todo antes del primer monto)
    # Encontrar la posición del primer monto
    primer_monto_pos = resto.find(montos_encontrados[0])
    if primer_monto_pos == -1:
        # Si hay problemas, buscar el monto de transacción
        primer_monto_pos = resto.find(monto_str)
    
    descripcion_raw = resto[:primer_monto_pos].strip() if primer_monto_pos > 0 else resto
    
    # Limpiar la descripción - separar referencia numérica si existe
    # La referencia es el último número entero (sin coma) en la descripción
    match_ref = re.search(r'\s+(\d+)\s*$', descripcion_raw)
    referencia = ''
    if match_ref:
        posible_ref = match_ref.group(1)
        # Las referencias suelen ser números largos (> 4 dígitos) o números específicos
        # El CUIT tiene 11 dígitos, las referencias de transacción ~6 dígitos
        if len(posible_ref) >= 4:
            referencia = posible_ref
            descripcion = descripcion_raw[:match_ref.start()].strip()
        else:
            descripcion = descripcion_raw
    else:
        descripcion = descripcion_raw
    
    # Determinar si es débito o crédito según la descripción
    es_credito = es_credito_por_descripcion(descripcion)
    
    debito = 0.0
    credito = 0.0
    
    if es_credito:
        credito = monto
    else:
        debito = monto
    
    try:
        fecha = datetime.strptime(fecha_str, '%d/%m/%y')
    except ValueError:
        return None
    
    return {
        'fecha': fecha,
        'descripcion': descripcion,
        'referencia': referencia,
        'debito': debito,
        'credito': credito,
        'saldo': saldo,
    }


def es_cesion_de_cheques(descripcion: str) -> bool:
    """
    Detecta si un movimiento es una cesión de cheques.
    Las cesiones de cheques en Banco Macro aparecen con descripciones que son
    solo números largos (típicamente > 15 dígitos) sin texto descriptivo.
    
    Ejemplo: "318000790421400000000009609558"
    """
    descripcion_limpia = descripcion.strip()
    
    # La descripción debe ser puramente numérica y larga (>= 15 dígitos)
    if descripcion_limpia.isdigit() and len(descripcion_limpia) >= 15:
        return True
    
    return False


def es_credito_por_descripcion(descripcion: str) -> bool:
    """
    Determina si un movimiento es crédito (entrada de dinero) basándose en la descripción.
    En un extracto bancario, los créditos aumentan el saldo de la cuenta.
    """
    descripcion_upper = descripcion.upper()
    
    # Detectar cesiones de cheques (son créditos - dinero que entra)
    if es_cesion_de_cheques(descripcion):
        return True
    
    # Patrones que SIEMPRE indican CRÉDITO (entrada de dinero a la cuenta)
    patrones_credito = [
        'PAGO PCT',           # Pagos recibidos por posnet/tarjeta (ventas)
        'PAGO63796',          # Liquidaciones PRISMA (Visa/Mastercard)
        'LIQ COMER PRISMA',   # Liquidaciones de comercio
        'TEF DATANET',        # Pagos Tarjeta Naranja
        'DEPOSITO',           # Depósitos en efectivo
        'TRANSF:',            # Transferencias recibidas (formato específico Macro)
        'TPUSH',              # Transferencias push recibidas
        'CCERR',              # Cobranzas circuito cerrado (Rapipago, etc)
        'N/C ',               # Notas de crédito
        '- NUMERO DE OPERACION',  # Transferencias recibidas
    ]
    
    for patron in patrones_credito:
        if patron in descripcion_upper:
            return True
    
    # Patrones que SIEMPRE indican DÉBITO (salida de dinero)
    patrones_debito = [
        'N/D ',               # Notas de débito
        'PAGO DE CHEQUE',     # Cheques emitidos
        'DB TARJETA',         # Débitos de tarjeta de crédito
        'TRF MO CCDO',        # Transferencias enviadas
        'COMISION',           # Comisiones bancarias
        'MANTENIMIENTO',      # Mantenimiento de cuenta
        'RETENCION',          # Retenciones
        'DEBITO FISCAL',      # Débitos fiscales (IVA)
        'DEV.COMPRA',         # Devoluciones (débito para el comercio)
        'DISNEY',             # Suscripciones
        'SPOTIFY',
        'NETFLIX',
        'BANNER',             # Publicidad
    ]
    
    for patron in patrones_debito:
        if patron in descripcion_upper:
            return False
    
    # Si no matchea ningún patrón, asumir débito (más conservador)
    return False


def es_traspaso_interno(descripcion: str, referencia: str = '') -> bool:
    """
    Determina si un movimiento es un traspaso interno entre cuentas propias.
    Detecta transferencias que incluyen el CUIT de la empresa.
    """
    texto_completo = f"{descripcion} {referencia}".upper()
    
    # Buscar el CUIT de la empresa en la descripción
    if CUIT_EMPRESA in texto_completo:
        # Es traspaso interno si es una transferencia
        patrones_transferencia = ['TRANSF', 'TRF MO', 'TPUSH']
        for patron in patrones_transferencia:
            if patron in texto_completo:
                return True
    
    return False


def categorizar_movimiento(descripcion: str, es_debito: bool, referencia: str = '') -> str:
    """Categoriza un movimiento según su descripción."""
    descripcion_upper = descripcion.upper()
    
    # Primero verificar si es un traspaso interno
    if es_traspaso_interno(descripcion, referencia):
        return '*** Traspasos entre Cuentas Propias ***'
    
    # Detectar cesiones de cheques (son créditos con descripción numérica larga)
    if not es_debito and es_cesion_de_cheques(descripcion):
        return 'Cesión de Cheques'
    
    if es_debito:
        categorias = CATEGORIAS_EGRESOS
    else:
        categorias = CATEGORIAS_INGRESOS
    
    for categoria, patrones in categorias.items():
        for patron in patrones:
            if patron.upper() in descripcion_upper:
                return categoria
    
    return 'Otros Egresos' if es_debito else 'Otros Ingresos'


# =============================================================================
# FUNCIONES DE ANÁLISIS Y REPORTE
# =============================================================================

def generar_eerr(movimientos: list) -> dict:
    """Genera el Estado de Resultados a partir de los movimientos."""
    
    ingresos = defaultdict(float)
    egresos = defaultdict(float)
    traspasos_entrada = 0.0
    traspasos_salida = 0.0
    
    for mov in movimientos:
        referencia = mov.get('referencia', '')
        
        if mov['credito'] > 0:
            categoria = categorizar_movimiento(mov['descripcion'], es_debito=False, referencia=referencia)
            if categoria == '*** Traspasos entre Cuentas Propias ***':
                traspasos_entrada += mov['credito']
            else:
                ingresos[categoria] += mov['credito']
        
        if mov['debito'] > 0:
            categoria = categorizar_movimiento(mov['descripcion'], es_debito=True, referencia=referencia)
            if categoria == '*** Traspasos entre Cuentas Propias ***':
                traspasos_salida += mov['debito']
            else:
                egresos[categoria] += mov['debito']
    
    # Calcular totales excluyendo traspasos
    total_ingresos = sum(ingresos.values())
    total_egresos = sum(egresos.values())
    
    return {
        'ingresos': dict(ingresos),
        'egresos': dict(egresos),
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'resultado_neto': total_ingresos - total_egresos,
        # Traspasos internos (movimientos entre cuentas propias - no afectan EERR)
        'traspasos_entrada': traspasos_entrada,
        'traspasos_salida': traspasos_salida,
        'traspasos_neto': traspasos_entrada - traspasos_salida,
    }


def imprimir_eerr(eerr: dict, periodo: str = ''):
    """Imprime el Estado de Resultados de forma legible."""
    
    print("\n" + "=" * 70)
    print("ESTADO DE RESULTADOS - FLUJO DE CAJA BANCARIO")
    if periodo:
        print(f"Período: {periodo}")
    print(f"CUIT Empresa: {CUIT_EMPRESA}")
    print("=" * 70)
    
    print("\n📈 INGRESOS OPERATIVOS (Créditos de terceros)")
    print("-" * 60)
    for categoria, monto in sorted(eerr['ingresos'].items(), key=lambda x: -x[1]):
        print(f"  {categoria:<40} {formato_moneda(monto):>22}")
    print("-" * 60)
    print(f"  {'TOTAL INGRESOS OPERATIVOS':<40} {formato_moneda(eerr['total_ingresos']):>22}")
    
    print("\n📉 EGRESOS OPERATIVOS (Débitos a terceros)")
    print("-" * 60)
    for categoria, monto in sorted(eerr['egresos'].items(), key=lambda x: -x[1]):
        print(f"  {categoria:<40} {formato_moneda(monto):>22}")
    print("-" * 60)
    print(f"  {'TOTAL EGRESOS OPERATIVOS':<40} {formato_moneda(eerr['total_egresos']):>22}")
    
    print("\n" + "=" * 70)
    resultado = eerr['resultado_neto']
    emoji = "✅" if resultado >= 0 else "❌"
    print(f"  {emoji} {'RESULTADO OPERATIVO NETO':<38} {formato_moneda(resultado):>22}")
    print("=" * 70)
    
    # Mostrar traspasos internos (informativos, no afectan el resultado)
    if eerr.get('traspasos_entrada', 0) > 0 or eerr.get('traspasos_salida', 0) > 0:
        print("\n🔄 TRASPASOS ENTRE CUENTAS PROPIAS (No afectan el resultado)")
        print("-" * 60)
        print(
            f"  {'Entradas desde otras cuentas propias':<40} {formato_moneda(eerr.get('traspasos_entrada', 0)):>22}"
        )
        print(
            f"  {'Salidas hacia otras cuentas propias':<40} {formato_moneda(eerr.get('traspasos_salida', 0)):>22}"
        )
        print("-" * 60)
        neto_traspasos = eerr.get('traspasos_neto', 0)
        print(
            f"  {'Neto Traspasos (entrada - salida)':<40} {formato_moneda(neto_traspasos):>22}"
        )
        print("=" * 70)


def exportar_a_excel(movimientos: list, eerr: dict, output_path: str):
    """Exporta los movimientos y el EERR a un archivo Excel."""
    
    # Crear DataFrame de movimientos
    df_movimientos = pd.DataFrame(movimientos)
    df_movimientos['fecha'] = pd.to_datetime(df_movimientos['fecha'])
    df_movimientos['categoria'] = df_movimientos.apply(
        lambda row: categorizar_movimiento(
            row['descripcion'], 
            es_debito=(row['debito'] > 0),
            referencia=row.get('referencia', '')
        ), 
        axis=1
    )
    df_movimientos['es_traspaso_interno'] = df_movimientos['categoria'] == '*** Traspasos entre Cuentas Propias ***'
    df_movimientos['tipo'] = df_movimientos.apply(
        lambda row: 'Traspaso Interno' if row['es_traspaso_interno'] else ('Débito' if row['debito'] > 0 else 'Crédito'),
        axis=1
    )
    df_movimientos['monto'] = df_movimientos.apply(
        lambda row: row['credito'] if row['credito'] > 0 else -row['debito'],
        axis=1
    )
    
    # Reordenar columnas
    cols = ['fecha', 'tipo', 'categoria', 'descripcion', 'referencia', 'debito', 'credito', 'monto', 'saldo']
    df_movimientos = df_movimientos[cols]
    
    # Crear DataFrame de EERR
    eerr_data = []
    for cat, monto in sorted(eerr['ingresos'].items(), key=lambda x: -x[1]):
        eerr_data.append({'Tipo': 'INGRESO', 'Categoría': cat, 'Monto': monto})
    for cat, monto in sorted(eerr['egresos'].items(), key=lambda x: -x[1]):
        eerr_data.append({'Tipo': 'EGRESO', 'Categoría': cat, 'Monto': monto})
    
    df_eerr = pd.DataFrame(eerr_data)
    
    # Agregar totales
    totales = pd.DataFrame([
        {'Tipo': '---', 'Categoría': '---', 'Monto': None},
        {'Tipo': 'TOTAL', 'Categoría': 'Total Ingresos Operativos', 'Monto': eerr['total_ingresos']},
        {'Tipo': 'TOTAL', 'Categoría': 'Total Egresos Operativos', 'Monto': eerr['total_egresos']},
        {'Tipo': 'RESULTADO', 'Categoría': 'RESULTADO OPERATIVO NETO', 'Monto': eerr['resultado_neto']},
        {'Tipo': '---', 'Categoría': '---', 'Monto': None},
        {'Tipo': 'TRASPASO', 'Categoría': 'Traspasos Entrada (cuentas propias)', 'Monto': eerr.get('traspasos_entrada', 0)},
        {'Tipo': 'TRASPASO', 'Categoría': 'Traspasos Salida (cuentas propias)', 'Monto': eerr.get('traspasos_salida', 0)},
        {'Tipo': 'TRASPASO', 'Categoría': 'Neto Traspasos', 'Monto': eerr.get('traspasos_neto', 0)},
    ])
    df_eerr = pd.concat([df_eerr, totales], ignore_index=True)
    
    # Exportar a Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_movimientos.to_excel(writer, sheet_name='Movimientos', index=False)
        df_eerr.to_excel(writer, sheet_name='EERR', index=False)
        
        # Resumen por día
        df_diario = df_movimientos.groupby(df_movimientos['fecha'].dt.date).agg({
            'debito': 'sum',
            'credito': 'sum'
        }).reset_index()
        df_diario.columns = ['Fecha', 'Total Débitos', 'Total Créditos']
        df_diario['Flujo Neto'] = df_diario['Total Créditos'] - df_diario['Total Débitos']
        df_diario.to_excel(writer, sheet_name='Resumen Diario', index=False)
        
        # Resumen por categoría
        df_por_cat = df_movimientos.groupby(['tipo', 'categoria']).agg({
            'debito': 'sum',
            'credito': 'sum'
        }).reset_index()
        df_por_cat['monto'] = df_por_cat['credito'] - df_por_cat['debito']
        df_por_cat.to_excel(writer, sheet_name='Por Categoría', index=False)
    
    print(f"\n✅ Archivo Excel exportado: {output_path}")


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================

def procesar_extracto(pdf_path: str, exportar_excel: bool = True):
    """
    Procesa un extracto bancario del Banco Macro.
    
    Args:
        pdf_path: Ruta al archivo PDF del extracto
        exportar_excel: Si True, exporta los resultados a Excel
    
    Returns:
        Tupla con (movimientos, eerr)
    """
    print(f"📄 Procesando: {pdf_path}")
    
    # Leer PDF
    texto = leer_pdf_texto(pdf_path)
    
    # Extraer período del extracto
    match_periodo = re.search(r'Periodo del Extracto:\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})', texto)
    periodo = ''
    if match_periodo:
        periodo = f"{match_periodo.group(1)} al {match_periodo.group(2)}"
    
    # Extraer movimientos
    movimientos = extraer_movimientos(texto)
    print(f"📊 Movimientos encontrados: {len(movimientos)}")
    
    if not movimientos:
        print("⚠️ No se encontraron movimientos. Verificar formato del PDF.")
        return [], {}
    
    # Generar EERR
    eerr = generar_eerr(movimientos)
    
    # Imprimir resumen
    imprimir_eerr(eerr, periodo)
    
    # Exportar a Excel si se solicita
    if exportar_excel:
        output_path = Path(pdf_path).with_suffix('.xlsx')
        exportar_a_excel(movimientos, eerr, str(output_path))
    
    return movimientos, eerr


def analizar_movimientos_detalle(movimientos: list, n: int = 20):
    """Muestra un análisis detallado de los primeros N movimientos."""
    print(f"\n📋 Detalle de {min(n, len(movimientos))} movimientos:")
    print("-" * 80)
    
    for i, mov in enumerate(movimientos[:n]):
        tipo = "✅ CRÉDITO" if mov['credito'] > 0 else "❌ DÉBITO"
        monto = mov['credito'] if mov['credito'] > 0 else mov['debito']
        print(f"\n{i+1}. {mov['fecha'].strftime('%d/%m/%y')} - {tipo}")
        print(f"   Descripción: {mov['descripcion']}")
        print(f"   Monto: {formato_moneda(monto)}")
        if mov['referencia']:
            print(f"   Referencia: {mov['referencia']}")


# =============================================================================
# EJECUCIÓN
# =============================================================================

if __name__ == '__main__':
    # Ruta al PDF del extracto
    PDF_PATH = Path(__file__).parent / 'Resumen.pdf'
    
    if PDF_PATH.exists():
        movimientos, eerr = procesar_extracto(str(PDF_PATH))
        
        # Mostrar algunos movimientos de ejemplo
        if movimientos:
            print("\n📋 Primeros 15 movimientos:")
            print("-" * 80)
            for mov in movimientos[:15]:
                tipo = "+" if mov['credito'] > 0 else "-"
                monto = mov['credito'] if mov['credito'] > 0 else mov['debito']
                print(
                    f"  {mov['fecha'].strftime('%d/%m')} {tipo} {formato_moneda(monto):>18}  "
                    f"{mov['descripcion'][:45]}"
                )
    else:
        print(f"❌ No se encontró el archivo: {PDF_PATH}")
        print("   Por favor, especifica la ruta correcta al PDF del extracto.")
