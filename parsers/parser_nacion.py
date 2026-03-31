"""
Parser para extractos bancarios del Banco Nación.
"""
import re
from typing import List, Dict, Optional
from datetime import datetime

from .base_parser import ParserPDF
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CUIT_EMPRESA


class ParserNacion(ParserPDF):
    """
    Parser específico para extractos del Banco Nación.
    
    Formato del extracto (texto extraído):
    Línea 1: DD/MM $
    Línea 2: COMPROBANTE CONCEPTO $ IMPORTE
    Línea 3: /YYYY SALDO
    """
    
    def __init__(self):
        super().__init__()
        self.nombre = "Banco Nación"
        self.banco = "NACION"
        
        # Categorías específicas de Banco Nación
        self.categorias_credito = {
            'Transferencias Recibidas': [
                'C BE TR',
                'CR DEBIN SPOT',
                'CR CREDIN TRANSFERENCIA',
                'TRANSF.INT.DIST.TITULAR',
            ],
            'Liquidaciones Tarjetas': [
                'LIQ+PAGOS NACION',
                'TRANS.MIN.REC-LIQ',
            ],
            'Depósitos en Efectivo': [
                'DEP.EFECTIVO',
            ],
        }
        
        self.categorias_debito = {
            'Impuesto Débitos y Créditos (Ley 25413)': [
                'GRAVAMEN LEY 25413',
            ],
            'IVA': [
                'I.V.A.',
            ],
            'Comisiones Bancarias': [
                'COM TRANSFE',
                'COMISION',
            ],
            'Transferencias Enviadas': [
                'DEB.TRAN.INTERB',
            ],
            'Intereses Bancarios': [
                'INTERESES',
            ],
            'Pagos Tarjeta de Crédito': [
                'TARJETA DE CREDITO',
            ],
            'Préstamos Bancarios': [
                'DEBITO PAGO PRESTAMO',
            ],
        }
    
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parsea un extracto del Banco Nación.
        """
        texto = self.leer_pdf(file_path)
        return self.extraer_movimientos(texto)
    
    def extraer_periodo(self, texto: str) -> Optional[Dict]:
        """Extrae información del período del extracto."""
        # Buscar fechas en el formato DD/MM seguido de /YYYY
        fechas_encontradas = []
        lineas = texto.split('\n')
        
        fecha_actual = None
        for linea in lineas:
            # Buscar DD/MM
            match_dm = re.match(r'^(\d{2}/\d{2})\s*\$?', linea.strip())
            if match_dm:
                fecha_actual = match_dm.group(1)
                continue
            
            # Buscar /YYYY
            if fecha_actual:
                match_anio = re.match(r'^/(\d{4})', linea.strip())
                if match_anio:
                    try:
                        fecha = datetime.strptime(f"{fecha_actual}/{match_anio.group(1)}", '%d/%m/%Y')
                        fechas_encontradas.append(fecha)
                    except:
                        pass
                    fecha_actual = None
        
        if fechas_encontradas:
            fecha_inicio = min(fechas_encontradas)
            fecha_fin = max(fechas_encontradas)
            
            return {
                'fecha_inicio': fecha_inicio.date(),
                'fecha_fin': fecha_fin.date(),
                'anio': fecha_fin.year,
                'mes': fecha_fin.month,
            }
        
        return None
    
    def extraer_movimientos(self, texto: str) -> List[Dict]:
        """
        Extrae los movimientos del texto del extracto.
        
        Formato:
        Línea 1: DD/MM $ (o DD/MM CONCEPTO_PARTE1 $)
        Línea 2: COMPROBANTE CONCEPTO $ IMPORTE (o COMPROBANTE $ IMPORTE)
        Línea 3: /YYYY [CONCEPTO_PARTE2] SALDO
        """
        movimientos = []
        lineas = texto.split('\n')
        
        i = 0
        while i < len(lineas) - 2:  # Necesitamos al menos 3 líneas
            linea1 = lineas[i].strip()
            
            # Ignorar líneas de encabezado
            if self._es_linea_ignorable(linea1):
                i += 1
                continue
            
            # Buscar patrón de fecha: DD/MM
            match_fecha = re.match(r'^(\d{2}/\d{2})\s*(.*?)\s*\$?\s*$', linea1)
            if match_fecha:
                fecha_dm = match_fecha.group(1)
                concepto_extra1 = match_fecha.group(2).strip()
                
                # Obtener las siguientes líneas
                linea2 = lineas[i + 1].strip() if i + 1 < len(lineas) else ''
                linea3 = lineas[i + 2].strip() if i + 2 < len(lineas) else ''
                
                mov = self._parsear_movimiento_3lineas(fecha_dm, concepto_extra1, linea2, linea3)
                
                if mov:
                    movimientos.append(mov)
                    i += 3
                    continue
            
            i += 1
        
        return movimientos
    
    def _es_linea_ignorable(self, linea: str) -> bool:
        """Determina si una línea debe ignorarse."""
        patrones_ignorar = [
            'Últimos movimientos',
            'Fecha Comprobante',
            '-- ',
            'Viernes',
            'Lunes',
            'Martes',
            'Miércoles',
            'Jueves',
            'Sábado',
            'Domingo',
        ]
        
        for patron in patrones_ignorar:
            if patron in linea:
                return True
        
        return len(linea) < 3
    
    def _parsear_movimiento_3lineas(self, fecha_dm: str, concepto_extra1: str, linea2: str, linea3: str) -> Optional[Dict]:
        """
        Parsea un movimiento de 3 líneas.
        
        Args:
            fecha_dm: DD/MM
            concepto_extra1: Parte extra del concepto en línea 1 (puede estar vacío)
            linea2: COMPROBANTE CONCEPTO $ IMPORTE
            linea3: /YYYY [CONCEPTO_EXTRA] SALDO
        """
        # Verificar que linea3 empieza con /YYYY
        match_anio = re.match(r'^/(\d{4})\s*(.*)', linea3)
        if not match_anio:
            return None
        
        anio = match_anio.group(1)
        resto_linea3 = match_anio.group(2).strip()
        
        # Construir fecha
        try:
            fecha = datetime.strptime(f"{fecha_dm}/{anio}", '%d/%m/%Y')
        except ValueError:
            return None
        
        # Extraer importe de linea2 (último número con formato X.XXX,XX o -X.XXX,XX)
        match_importe = re.search(r'\$?\s*(-?[\d.,]+)\s*$', linea2)
        if not match_importe:
            return None
        
        importe = self._parsear_monto_nacion(match_importe.group(1))
        if importe == 0:
            return None
        
        # Extraer comprobante y concepto de linea2
        parte_concepto = linea2[:match_importe.start()].strip()
        
        # Remover $ sueltos
        parte_concepto = re.sub(r'\s*\$\s*', ' ', parte_concepto).strip()
        
        # El comprobante es el primer elemento
        partes = parte_concepto.split(None, 1)
        if len(partes) >= 2:
            comprobante = partes[0]
            concepto = partes[1]
        elif len(partes) == 1:
            comprobante = partes[0]
            concepto = ''
        else:
            comprobante = ''
            concepto = ''
        
        # Agregar concepto extra de línea 1 si existe
        if concepto_extra1:
            concepto = f"{concepto_extra1} {concepto}".strip()
        
        # Extraer CUIT de cualquier parte
        cuit_encontrado = ''
        texto_completo = f"{concepto} {resto_linea3}"
        match_cuit = re.search(r'(\d{11})', texto_completo)
        if match_cuit:
            cuit_encontrado = match_cuit.group(1)
        
        # Agregar información extra de linea3 al concepto si es relevante
        if resto_linea3 and not re.match(r'^-?[\d.,]+$', resto_linea3):
            # Remover el saldo del final
            resto_sin_saldo = re.sub(r'-?[\d.,]+\s*$', '', resto_linea3).strip()
            if resto_sin_saldo and resto_sin_saldo not in concepto:
                concepto = f"{concepto} {resto_sin_saldo}".strip()
        
        # Limpiar concepto
        concepto = re.sub(r'\s+', ' ', concepto).strip()
        
        # Extraer saldo de linea3
        match_saldo = re.search(r'(-?[\d.,]+)\s*$', resto_linea3)
        saldo = self._parsear_monto_nacion(match_saldo.group(1)) if match_saldo else 0
        
        # Determinar débito o crédito según el signo del importe
        es_debito = importe < 0
        importe_abs = abs(importe)
        
        debito = importe_abs if es_debito else 0
        credito = importe_abs if not es_debito else 0
        
        # Verificar si es traspaso interno
        es_traspaso = cuit_encontrado == CUIT_EMPRESA
        
        # Categorizar
        categoria = self._categorizar(concepto, es_debito)
        
        if es_traspaso:
            categoria = '*** Traspasos entre Cuentas Propias ***'
        
        return {
            'fecha': fecha,
            'descripcion': concepto,
            'referencia': comprobante,
            'debito': debito,
            'credito': credito,
            'saldo': saldo,
            'categoria': categoria,
            'es_traspaso_interno': es_traspaso,
            'tipo': 'TRASPASO_INTERNO' if es_traspaso else ('DEBITO' if es_debito else 'CREDITO'),
            'cuit_relacionado': cuit_encontrado,
        }
    
    def _parsear_monto_nacion(self, monto_str: str) -> float:
        """
        Parsea un monto del formato del Banco Nación.
        Formato: -1.234,56 o 1.234,56 o 1234,56
        """
        if not monto_str:
            return 0.0
        
        monto_str = monto_str.strip()
        
        # Detectar signo negativo
        es_negativo = monto_str.startswith('-')
        if es_negativo:
            monto_str = monto_str[1:]
        
        # Convertir formato argentino a float
        # Remover puntos de miles, cambiar coma por punto
        monto_str = monto_str.replace('.', '').replace(',', '.')
        
        try:
            monto = float(monto_str)
            return -monto if es_negativo else monto
        except ValueError:
            return 0.0
    
    def _categorizar(self, concepto: str, es_debito: bool) -> str:
        """Categoriza un movimiento según el concepto."""
        concepto_upper = concepto.upper()
        
        if es_debito:
            categorias = self.categorias_debito
        else:
            categorias = self.categorias_credito
        
        for categoria, patrones in categorias.items():
            for patron in patrones:
                if patron.upper() in concepto_upper:
                    return categoria
        
        return 'Otros Egresos' if es_debito else 'Otros Ingresos'
    
    def generar_eerr(self, movimientos: List[Dict]) -> Dict:
        """
        Genera el Estado de Resultados a partir de los movimientos.
        """
        from collections import defaultdict
        
        ingresos = defaultdict(float)
        egresos = defaultdict(float)
        traspasos_entrada = 0.0
        traspasos_salida = 0.0
        
        for mov in movimientos:
            if mov.get('es_traspaso_interno'):
                if mov['credito'] > 0:
                    traspasos_entrada += mov['credito']
                if mov['debito'] > 0:
                    traspasos_salida += mov['debito']
            else:
                categoria = mov.get('categoria', 'Sin categoría')
                if mov['credito'] > 0:
                    ingresos[categoria] += mov['credito']
                if mov['debito'] > 0:
                    egresos[categoria] += mov['debito']
        
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
