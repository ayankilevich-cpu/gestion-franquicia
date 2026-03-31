"""
Parser para archivos de pagos en efectivo (Excel/CSV desde Google Sheets).
"""
import re
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from .base_parser import ParserExcel
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.categorias import categorizar_pago_efectivo


class ParserEfectivo(ParserExcel):
    """
    Parser para archivos Excel/CSV de pagos en efectivo.
    
    Espera columnas como:
    - Fecha
    - Concepto (o descripcion, detalle)
    - Monto (o importe, valor, total)
    """
    
    def __init__(self):
        super().__init__()
        self.nombre = "Pagos Efectivo"
        
        # Mapeo de posibles nombres de columnas
        self.columnas_fecha = ['fecha', 'Fecha', 'FECHA', 'date', 'Date']
        self.columnas_concepto = ['concepto', 'Concepto', 'descripcion', 'Descripcion', 'detalle', 'Detalle', 'descripción', 'Descripción']
        self.columnas_monto = ['monto', 'Monto', 'importe', 'Importe', 'valor', 'Valor', 'total', 'Total']
        self.columnas_categoria = ['categoria', 'Categoria', 'categoría', 'Categoría', 'tipo', 'Tipo']
    
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parsea un archivo de pagos en efectivo.
        
        Args:
            file_path: Ruta al archivo Excel o CSV
            
        Returns:
            Lista de pagos
        """
        # Detectar tipo de archivo
        if file_path.endswith('.csv'):
            df = self.leer_csv(file_path)
        else:
            df = self.leer_excel(file_path)
        
        return self.procesar_dataframe(df)
    
    def parse_dataframe(self, df: pd.DataFrame) -> List[Dict]:
        """
        Procesa un DataFrame de pagos (útil para archivos subidos).
        """
        return self.procesar_dataframe(df)
    
    def procesar_dataframe(self, df: pd.DataFrame) -> List[Dict]:
        """Procesa el DataFrame y extrae los pagos."""
        pagos = []
        
        # Identificar columnas
        col_fecha = self._encontrar_columna(df.columns, self.columnas_fecha)
        col_concepto = self._encontrar_columna(df.columns, self.columnas_concepto)
        col_monto = self._encontrar_columna(df.columns, self.columnas_monto)
        col_categoria = self._encontrar_columna(df.columns, self.columnas_categoria)
        
        if not col_fecha:
            raise ValueError("No se encontró columna de fecha. Columnas disponibles: " + str(list(df.columns)))
        
        if not col_monto:
            raise ValueError("No se encontró columna de monto. Columnas disponibles: " + str(list(df.columns)))
        
        for _, row in df.iterrows():
            # Parsear fecha
            fecha = self._parsear_fecha_flexible(row[col_fecha])
            if not fecha:
                continue
            
            # Obtener concepto
            concepto = ''
            if col_concepto and pd.notna(row[col_concepto]):
                concepto = str(row[col_concepto]).strip()
            
            # Obtener monto
            monto = self._parsear_numero(row[col_monto])
            if monto == 0:
                continue
            
            # Obtener o calcular categoría
            if col_categoria and pd.notna(row[col_categoria]):
                categoria = str(row[col_categoria]).strip()
            else:
                categoria = categorizar_pago_efectivo(concepto)
            
            pago = {
                'fecha': fecha,
                'concepto': concepto,
                'monto': monto,
                'categoria': categoria,
            }
            
            pagos.append(pago)
        
        return pagos
    
    def extraer_periodo(self, texto: str) -> Optional[Dict]:
        """No aplica para archivos de pagos."""
        return None
    
    def _encontrar_columna(self, columnas, posibles_nombres: List[str]) -> Optional[str]:
        """Encuentra una columna por nombre flexible."""
        columnas_lower = {c.lower(): c for c in columnas}
        
        for nombre in posibles_nombres:
            if nombre in columnas:
                return nombre
            if nombre.lower() in columnas_lower:
                return columnas_lower[nombre.lower()]
        
        return None
    
    def _parsear_fecha_flexible(self, valor) -> Optional[datetime]:
        """Parsea una fecha de manera flexible."""
        if pd.isna(valor):
            return None
        
        # Si ya es datetime
        if isinstance(valor, (datetime, pd.Timestamp)):
            return valor if isinstance(valor, datetime) else valor.to_pydatetime()
        
        # Intentar parsear string
        valor_str = str(valor).strip()
        
        formatos = [
            '%d/%m/%Y',
            '%d/%m/%y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d-%m-%y',
        ]
        
        for formato in formatos:
            try:
                return datetime.strptime(valor_str, formato)
            except ValueError:
                continue
        
        return None
    
    def _parsear_numero(self, valor) -> float:
        """Parsea un número de manera flexible."""
        if pd.isna(valor):
            return 0.0
        
        if isinstance(valor, (int, float)):
            return float(valor)
        
        # Intentar parsear string
        valor_str = str(valor).strip()
        
        # Remover símbolos de moneda
        valor_str = re.sub(r'[$€]', '', valor_str)
        
        # Formato argentino: 1.234,56
        if ',' in valor_str and '.' in valor_str:
            valor_str = valor_str.replace('.', '').replace(',', '.')
        elif ',' in valor_str:
            valor_str = valor_str.replace(',', '.')
        
        try:
            return float(valor_str)
        except ValueError:
            return 0.0
    
    def obtener_resumen(self, pagos: List[Dict]) -> Dict:
        """Genera un resumen de los pagos por categoría."""
        from collections import defaultdict
        
        if not pagos:
            return {
                'total': 0,
                'cantidad': 0,
                'por_categoria': {},
            }
        
        total = sum(p.get('monto', 0) for p in pagos)
        por_categoria = defaultdict(float)
        
        for pago in pagos:
            categoria = pago.get('categoria', 'Sin categoría')
            por_categoria[categoria] += pago.get('monto', 0)
        
        return {
            'total': total,
            'cantidad': len(pagos),
            'por_categoria': dict(por_categoria),
        }
