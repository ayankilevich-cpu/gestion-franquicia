"""
Parser para extractos bancarios del Banco Macro.
"""
import re
from typing import List, Dict, Optional
from datetime import datetime

from .base_parser import ParserPDF
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.categorias import categorizar_movimiento, es_credito_por_descripcion, es_traspaso_interno


class ParserMacro(ParserPDF):
    """
    Parser específico para extractos del Banco Macro.
    """
    
    def __init__(self):
        super().__init__()
        self.nombre = "Banco Macro"
        self.banco = "MACRO"
    
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parsea un extracto del Banco Macro.
        
        Args:
            file_path: Ruta al archivo PDF
            
        Returns:
            Lista de movimientos
        """
        texto = self.leer_pdf(file_path)
        return self.extraer_movimientos(texto)
    
    def extraer_periodo(self, texto: str) -> Optional[Dict]:
        """Extrae información del período del extracto."""
        match = re.search(
            r'Periodo del Extracto:\s*(\d{2}/\d{2}/\d{4})\s*al\s*(\d{2}/\d{2}/\d{4})',
            texto
        )
        
        if match:
            fecha_inicio = datetime.strptime(match.group(1), '%d/%m/%Y')
            fecha_fin = datetime.strptime(match.group(2), '%d/%m/%Y')
            
            return {
                'fecha_inicio': fecha_inicio.date(),
                'fecha_fin': fecha_fin.date(),
                'anio': fecha_fin.year,
                'mes': fecha_fin.month,
            }
        
        return None
    
    def extraer_movimientos(self, texto: str) -> List[Dict]:
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
            
            mov = self._parsear_linea(linea)
            if mov and self.validar_movimiento(mov):
                movimientos.append(mov)
        
        return movimientos
    
    def _parsear_linea(self, linea: str) -> Optional[Dict]:
        """
        Parsea una línea de movimiento bancario del Banco Macro.
        """
        # Extraer fecha
        match_fecha = re.match(r'^(\d{2}/\d{2}/\d{2})\s+(.+)', linea)
        if not match_fecha:
            return None
        
        fecha_str = match_fecha.group(1)
        resto = match_fecha.group(2)
        
        # Buscar todos los números con formato de monto (tienen coma decimal)
        patron_monto = r'-?\d{1,3}(?:\.\d{3})*,\d{2}'
        montos_encontrados = re.findall(patron_monto, resto)
        
        if len(montos_encontrados) < 2:
            return None
        
        # El último monto es el saldo
        saldo_str = montos_encontrados[-1]
        saldo = self.parsear_monto(saldo_str)
        
        # El penúltimo es el monto de la transacción
        monto_str = montos_encontrados[-2]
        monto = self.parsear_monto(monto_str)
        
        if monto == 0:
            return None
        
        # Extraer la descripción
        primer_monto_pos = resto.find(montos_encontrados[0])
        if primer_monto_pos == -1:
            primer_monto_pos = resto.find(monto_str)
        
        descripcion_raw = resto[:primer_monto_pos].strip() if primer_monto_pos > 0 else resto
        
        # Separar referencia numérica
        match_ref = re.search(r'\s+(\d+)\s*$', descripcion_raw)
        referencia = ''
        if match_ref:
            posible_ref = match_ref.group(1)
            if len(posible_ref) >= 4:
                referencia = posible_ref
                descripcion = descripcion_raw[:match_ref.start()].strip()
            else:
                descripcion = descripcion_raw
        else:
            descripcion = descripcion_raw
        
        # Determinar si es débito o crédito
        es_credito = es_credito_por_descripcion(descripcion)
        
        debito = 0.0
        credito = 0.0
        
        if es_credito:
            credito = monto
        else:
            debito = monto
        
        # Parsear fecha
        fecha = self.parsear_fecha(fecha_str)
        if not fecha:
            return None
        
        # Verificar si es traspaso interno
        es_traspaso = es_traspaso_interno(descripcion, referencia)
        
        # Categorizar
        categoria = categorizar_movimiento(descripcion, es_debito=(debito > 0), referencia=referencia)
        
        return {
            'fecha': fecha,
            'descripcion': descripcion,
            'referencia': referencia,
            'debito': debito,
            'credito': credito,
            'saldo': saldo,
            'categoria': categoria,
            'es_traspaso_interno': es_traspaso,
            'tipo': 'TRASPASO_INTERNO' if es_traspaso else ('CREDITO' if credito > 0 else 'DEBITO'),
        }
    
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
