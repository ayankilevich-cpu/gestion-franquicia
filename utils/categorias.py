"""
Funciones de categorización de movimientos.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CUIT_EMPRESA, CATEGORIAS_INGRESOS, CATEGORIAS_EGRESOS


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


def es_credito_por_descripcion(descripcion: str) -> bool:
    """
    Determina si un movimiento es crédito (entrada de dinero) basándose en la descripción.
    """
    descripcion_upper = descripcion.upper()
    
    # Patrones que SIEMPRE indican CRÉDITO
    patrones_credito = [
        'PAGO PCT',
        'PAGO63796',
        'LIQ COMER PRISMA',
        'TEF DATANET',
        'DEPOSITO',
        'TRANSF:',
        'TPUSH',
        'CCERR',
        'N/C ',
        '- NUMERO DE OPERACION',
    ]
    
    for patron in patrones_credito:
        if patron in descripcion_upper:
            return True
    
    # Patrones que SIEMPRE indican DÉBITO
    patrones_debito = [
        'N/D ',
        'PAGO DE CHEQUE',
        'DB TARJETA',
        'TRF MO CCDO',
        'COMISION',
        'MANTENIMIENTO',
        'RETENCION',
        'DEBITO FISCAL',
        'DEV.COMPRA',
        'DISNEY',
        'SPOTIFY',
        'NETFLIX',
        'BANNER',
    ]
    
    for patron in patrones_debito:
        if patron in descripcion_upper:
            return False
    
    return False


def categorizar_movimiento(descripcion: str, es_debito: bool, referencia: str = '') -> str:
    """Categoriza un movimiento según su descripción."""
    descripcion_upper = descripcion.upper()
    
    # Primero verificar si es un traspaso interno
    if es_traspaso_interno(descripcion, referencia):
        return '*** Traspasos entre Cuentas Propias ***'
    
    if es_debito:
        categorias = CATEGORIAS_EGRESOS
    else:
        categorias = CATEGORIAS_INGRESOS
    
    for categoria, patrones in categorias.items():
        for patron in patrones:
            if patron.upper() in descripcion_upper:
                return categoria
    
    return 'Otros Egresos' if es_debito else 'Otros Ingresos'


def categorizar_pago_efectivo(concepto: str) -> str:
    """Categoriza un pago en efectivo según el concepto."""
    from config import CATEGORIAS_EFECTIVO
    
    concepto_upper = concepto.upper()
    
    for categoria, patrones in CATEGORIAS_EFECTIVO.items():
        for patron in patrones:
            if patron.upper() in concepto_upper:
                return categoria
    
    return 'Gastos Varios'
