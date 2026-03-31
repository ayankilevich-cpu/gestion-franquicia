"""
Parser para extractos de Mercado Pago (Excel).
"""
import re
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime

from .base_parser import ParserExcel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CUIT_EMPRESA


class ParserMercadoPago(ParserExcel):
    """
    Parser para extractos de Mercado Pago exportados desde la app.
    
    El archivo Excel tiene:
    - Headers en fila 3 (índice 3)
    - Columnas: Número de operación, Fecha de la compra, Estado, Cobro, Total a recibir, etc.
    """
    
    def __init__(self):
        super().__init__()
        self.nombre = "Mercado Pago"
        self.banco = "MERCADOPAGO"
        
        self.categorias_credito = {
            'Ventas Mercado Pago': [
                'Aprobado',
            ],
            'Cobros en Efectivo (MP)': [
                'Cobro registrado',
            ],
        }
    
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parsea un extracto de Mercado Pago.
        """
        # Primero extraer período para obtener el año
        periodo = self.extraer_periodo(file_path)
        anio_default = periodo['anio'] if periodo else datetime.now().year
        
        # Leer Excel con header en fila 3
        df = pd.read_excel(file_path, header=3)
        
        movimientos = []
        
        for _, row in df.iterrows():
            estado = row.get('Estado', '')
            
            # Solo procesar aprobados y cobros registrados
            if estado not in ['Aprobado', 'Cobro registrado']:
                continue
            
            # Parsear fecha (pasando año default para fechas sin año)
            fecha = self._parsear_fecha(row.get('Fecha de la compra', ''), anio_default)
            if not fecha:
                continue
            
            # Parsear monto
            monto = self._parsear_monto(row.get('Total a recibir', ''))
            if monto <= 0:
                continue
            
            # Determinar categoría
            if estado == 'Cobro registrado':
                categoria = 'Cobros en Efectivo (MP)'
            else:
                categoria = 'Ventas Mercado Pago'
            
            # Descripción
            descripcion = f"Venta MP - {row.get('Herramienta de cobro', 'QR')}"
            if pd.notna(row.get('Medio de pago')):
                descripcion += f" - {row['Medio de pago']}"
            
            referencia = str(int(row.get('Número de operación', 0))) if pd.notna(row.get('Número de operación')) else ''
            
            movimientos.append({
                'fecha': fecha,
                'descripcion': descripcion[:100],
                'referencia': referencia,
                'debito': 0,
                'credito': monto,
                'saldo': 0,
                'categoria': categoria,
                'es_traspaso_interno': False,
                'tipo': 'CREDITO',
                'cuit_relacionado': '',
            })
        
        return movimientos
    
    def extraer_periodo(self, file_path: str) -> Optional[Dict]:
        """Extrae información del período del extracto."""
        try:
            # Leer primera fila para obtener período
            df_raw = pd.read_excel(file_path, header=None, nrows=2)
            
            # Buscar texto con período en fila 1
            texto = str(df_raw.iloc[1, 0]) if len(df_raw) > 1 else ''
            
            # Buscar patrón "desde el X dic. 2025 hasta el Y dic. 2025"
            match = re.search(r'desde el (\d+) (\w+)\.? (\d{4}) hasta el (\d+) (\w+)\.? (\d{4})', texto, re.IGNORECASE)
            
            if match:
                dia_fin = int(match.group(4))
                mes_fin = self._mes_a_numero(match.group(5))
                anio_fin = int(match.group(6))
                
                dia_ini = int(match.group(1))
                mes_ini = self._mes_a_numero(match.group(2))
                anio_ini = int(match.group(3))
                
                return {
                    'fecha_inicio': datetime(anio_ini, mes_ini, dia_ini).date(),
                    'fecha_fin': datetime(anio_fin, mes_fin, dia_fin).date(),
                    'anio': anio_fin,
                    'mes': mes_fin,
                }
        except Exception as e:
            print(f"Error extrayendo período: {e}")
        
        return None
    
    def _parsear_fecha(self, fecha_str: str, anio_default: int = None) -> Optional[datetime]:
        """Parsea fecha en formatos:
        - '31 dic 2025 21:06 hs' (con año)
        - '31 ene 23:59 hs' (sin año, usa anio_default)
        """
        if pd.isna(fecha_str):
            return None
        
        try:
            fecha_str = str(fecha_str).strip()
            
            # Patrón 1: DD mes YYYY HH:MM hs (con año)
            match = re.match(r'(\d{1,2}) (\w+) (\d{4}) (\d{1,2}):(\d{2}) hs', fecha_str)
            if match:
                dia = int(match.group(1))
                mes = self._mes_a_numero(match.group(2))
                anio = int(match.group(3))
                hora = int(match.group(4))
                minuto = int(match.group(5))
                
                return datetime(anio, mes, dia, hora, minuto)
            
            # Patrón 2: DD mes HH:MM hs (sin año)
            match = re.match(r'(\d{1,2}) (\w+) (\d{1,2}):(\d{2}) hs', fecha_str)
            if match:
                dia = int(match.group(1))
                mes = self._mes_a_numero(match.group(2))
                hora = int(match.group(3))
                minuto = int(match.group(4))
                
                # Usar año default o el actual
                anio = anio_default or datetime.now().year
                
                return datetime(anio, mes, dia, hora, minuto)
                
        except Exception as e:
            pass
        
        return None
    
    def _mes_a_numero(self, mes_str: str) -> int:
        """Convierte nombre de mes a número."""
        meses = {
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
        }
        return meses.get(mes_str.lower().replace('.', ''), 1)
    
    def _parsear_monto(self, monto_str) -> float:
        """Parsea monto en formato argentino '$ 1.234,56'."""
        if pd.isna(monto_str):
            return 0.0
        
        try:
            s = str(monto_str).replace('$', '').strip()
            s = s.replace('.', '').replace(',', '.')
            return float(s)
        except:
            return 0.0
    
    def generar_eerr(self, movimientos: List[Dict]) -> Dict:
        """Genera resumen de ingresos."""
        from collections import defaultdict
        
        ingresos = defaultdict(float)
        
        for mov in movimientos:
            if mov['credito'] > 0:
                categoria = mov.get('categoria', 'Ventas Mercado Pago')
                ingresos[categoria] += mov['credito']
        
        total_ingresos = sum(ingresos.values())
        
        return {
            'ingresos': dict(ingresos),
            'egresos': {},
            'total_ingresos': total_ingresos,
            'total_egresos': 0,
            'resultado_neto': total_ingresos,
            'traspasos_entrada': 0,
            'traspasos_salida': 0,
        }
