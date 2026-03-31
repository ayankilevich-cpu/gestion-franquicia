"""
Parser para archivos de ventas (Excel/CSV).
"""
import re
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from .base_parser import ParserExcel


class ParserVentas(ParserExcel):
    """
    Parser para archivos Excel/CSV de ventas.
    
    Espera columnas como:
    - Fecha (o fecha, FECHA)
    - Venta Pesos (o venta_pesos, monto, importe, total)
    - Venta Kgs (o venta_kgs, kilos, kg, cantidad)
    - Sucursal (opcional)
    """
    
    def __init__(self):
        super().__init__()
        self.nombre = "Ventas"
        
        # Mapeo de posibles nombres de columnas
        self.columnas_fecha = ['fecha', 'Fecha', 'FECHA', 'date', 'Date']
        self.columnas_pesos = ['venta_pesos', 'Venta Pesos', 'monto', 'Monto', 'importe', 'Importe', 'total', 'Total', 'venta', 'Venta']
        self.columnas_kgs = ['venta_kgs', 'Venta Kgs', 'kilos', 'Kilos', 'kg', 'Kg', 'KG', 'cantidad', 'Cantidad']
        self.columnas_sucursal = ['sucursal', 'Sucursal', 'local', 'Local', 'tienda', 'Tienda']
    
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parsea un archivo de ventas.
        
        Args:
            file_path: Ruta al archivo Excel o CSV
            
        Returns:
            Lista de ventas
        """
        # Detectar tipo de archivo
        if file_path.endswith('.csv'):
            df = self.leer_csv(file_path)
        else:
            df = self.leer_excel(file_path)
        
        return self.procesar_dataframe(df)
    
    def parse_dataframe(self, df: pd.DataFrame) -> List[Dict]:
        """
        Procesa un DataFrame de ventas (útil para archivos subidos).
        """
        return self.procesar_dataframe(df)
    
    def procesar_dataframe(self, df: pd.DataFrame) -> List[Dict]:
        """Procesa el DataFrame y extrae las ventas."""
        ventas = []
        
        # Identificar columnas
        col_fecha = self._encontrar_columna(df.columns, self.columnas_fecha)
        col_pesos = self._encontrar_columna(df.columns, self.columnas_pesos)
        col_kgs = self._encontrar_columna(df.columns, self.columnas_kgs)
        col_sucursal = self._encontrar_columna(df.columns, self.columnas_sucursal)
        
        if not col_fecha:
            raise ValueError("No se encontró columna de fecha. Columnas disponibles: " + str(list(df.columns)))
        
        if not col_pesos and not col_kgs:
            raise ValueError("No se encontró columna de venta (pesos o kgs). Columnas disponibles: " + str(list(df.columns)))
        
        for _, row in df.iterrows():
            # Parsear fecha
            fecha = self._parsear_fecha_flexible(row[col_fecha])
            if not fecha:
                continue
            
            venta = {
                'fecha': fecha,
                'venta_pesos': self._parsear_numero(row[col_pesos]) if col_pesos else 0,
                'venta_kgs': self._parsear_numero(row[col_kgs]) if col_kgs else 0,
                'sucursal': str(row[col_sucursal]).strip() if col_sucursal and pd.notna(row[col_sucursal]) else '',
            }
            
            # Solo agregar si tiene algún valor
            if venta['venta_pesos'] > 0 or venta['venta_kgs'] > 0:
                ventas.append(venta)
        
        return ventas
    
    def extraer_periodo(self, texto: str) -> Optional[Dict]:
        """No aplica para archivos de ventas."""
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
    
    def obtener_resumen(self, ventas: List[Dict]) -> Dict:
        """Genera un resumen de las ventas."""
        if not ventas:
            return {
                'total_pesos': 0,
                'total_kgs': 0,
                'dias': 0,
                'promedio_diario_pesos': 0,
                'promedio_diario_kgs': 0,
            }
        
        total_pesos = sum(v.get('venta_pesos', 0) for v in ventas)
        total_kgs = sum(v.get('venta_kgs', 0) for v in ventas)
        dias = len(ventas)
        
        return {
            'total_pesos': total_pesos,
            'total_kgs': total_kgs,
            'dias': dias,
            'promedio_diario_pesos': total_pesos / dias if dias > 0 else 0,
            'promedio_diario_kgs': total_kgs / dias if dias > 0 else 0,
        }
