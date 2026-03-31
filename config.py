"""
Configuración centralizada del Sistema de Gestión Financiera.
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# =============================================================================
# CONFIGURACIÓN DE LA EMPRESA
# =============================================================================

CUIT_EMPRESA = '30717192822'
NOMBRE_EMPRESA = 'BLEMA SAS'
SUCURSAL = 'La Falda'

# =============================================================================
# CONFIGURACIÓN DE BASE DE DATOS MYSQL
# =============================================================================

def _get_streamlit_secrets():
    """
    Secrets de Streamlit solo cuando corre el servidor Streamlit (no en scripts/CLI).
    Evita importar streamlit.runtime en el arranque (lento) y no usa bool(st.secrets).
    """
    if not any(
        os.environ.get(k)
        for k in (
            "STREAMLIT_SERVER_PORT",
            "STREAMLIT_SERVER_ADDRESS",
        )
    ):
        return {}
    try:
        import streamlit as st
        return st.secrets
    except Exception:
        return {}


def _get_secret_or_env(secrets_obj, key: str, default=None):
    """Prioriza st.secrets y luego variables de entorno."""
    # No usar `if secrets_obj`: en Streamlit, bool(st.secrets) dispara carga y puede fallar.
    try:
        return secrets_obj[key]
    except Exception:
        pass
    return os.getenv(key, default)


_SECRETS = _get_streamlit_secrets()

DB_CONFIG = {
    'host': _get_secret_or_env(_SECRETS, 'MYSQL_HOST', 'localhost'),
    'port': int(_get_secret_or_env(_SECRETS, 'MYSQL_PORT', 3306)),
    'user': _get_secret_or_env(_SECRETS, 'MYSQL_USER', 'root'),
    'password': _get_secret_or_env(_SECRETS, 'MYSQL_PASSWORD', ''),
    'database': _get_secret_or_env(_SECRETS, 'MYSQL_DATABASE', 'gestion_franquicia'),
}

# =============================================================================
# CATEGORÍAS DE INGRESOS (Créditos)
# =============================================================================

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
        # Se detecta automáticamente por descripción numérica larga (>= 15 dígitos)
        # Son adelantos de dinero por cheques cedidos al banco
    ],
}

# =============================================================================
# CATEGORÍAS DE EGRESOS (Débitos)
# =============================================================================

CATEGORIAS_EGRESOS = {
    'Pago a Proveedores (Cheques)': [
        'PAGO DE CHEQUE',
        'CHEQUE CANJE',
    ],
    'Pago a Proveedores (Efectivo)': [
        'PAGO EFECTIVO PROVEEDOR',
        'PROVEEDOR CONTADO',
    ],
    'Pagos Tarjeta de Crédito': [
        'DB TARJETA DE CREDITO',
    ],
    'Transferencias Enviadas': [
        'N/D TRANSF',
        'TRF MO CCDO',
        'COMISION TRANSFERE',
        'N/D COMISION TRF',
        'TRANSF 2',
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
        'Cobro de prestamo',
    ],
    'Intereses Bancarios': [
        'N/D INTER.ADEL.CC',
        'INTER.ADEL',
        'INTERESES',
        'INT.ADEL',
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
    'Energía Eléctrica': [
        'EPEC',
        'EDENOR',
        'EDESUR',
        'ENERGIA',
        'LUZ',
        'ELECTRICIDAD',
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
    'Retiros Personales': [
        'RETIRO PERSONAL',
        'RETIRO SOCIO',
        'DISTRIBUCION UTILIDADES',
    ],
    'Otros Egresos': [],
}

# =============================================================================
# CATEGORÍAS DE PAGOS EN EFECTIVO
# =============================================================================

CATEGORIAS_EFECTIVO = {
    'Compras Mercadería': ['MERCADERIA', 'COMPRA', 'PROVEEDOR'],
    'Sueldos y Jornales': ['SUELDO', 'JORNAL', 'EMPLEADO'],
    'Servicios': ['LUZ', 'GAS', 'AGUA', 'INTERNET', 'TELEFONO'],
    'Alquiler': ['ALQUILER'],
    'Gastos Varios': ['VARIOS', 'OTRO'],
}

# =============================================================================
# BANCOS SOPORTADOS
# =============================================================================

BANCOS = {
    'MACRO': {
        'nombre': 'Banco Macro',
        'parser': 'parser_macro',
    },
    'SANTANDER': {
        'nombre': 'Banco Santander',
        'parser': 'parser_santander',
    },
    'NACION': {
        'nombre': 'Banco Nación',
        'parser': 'parser_nacion',
    },
    'MERCADOPAGO': {
        'nombre': 'Mercado Pago',
        'parser': 'parser_mercadopago',
    },
}
