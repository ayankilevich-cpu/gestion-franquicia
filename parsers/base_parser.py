"""
Clase base para parsers de extractos bancarios y otros documentos.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import re


class BaseParser(ABC):
    """
    Clase base abstracta para todos los parsers.
    Define la interfaz común que deben implementar.
    """
    
    def __init__(self):
        self.nombre = "BaseParser"
        self.banco = None
    
    @abstractmethod
    def parse(self, file_path: str) -> List[Dict]:
        """
        Parsea un archivo y retorna lista de movimientos.
        
        Args:
            file_path: Ruta al archivo a parsear
            
        Returns:
            Lista de diccionarios con los movimientos
        """
        pass
    
    @abstractmethod
    def extraer_periodo(self, texto: str) -> Optional[Dict]:
        """
        Extrae información del período del documento.
        
        Returns:
            Dict con 'fecha_inicio', 'fecha_fin', 'anio', 'mes'
        """
        pass
    
    def parsear_monto(self, valor_str: str) -> float:
        """
        Convierte un string de monto argentino (1.234,56) a float.
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
    
    def parsear_fecha(self, fecha_str: str, formato: str = '%d/%m/%y') -> Optional[datetime]:
        """
        Parsea una fecha string a datetime.
        """
        try:
            return datetime.strptime(fecha_str.strip(), formato)
        except ValueError:
            # Intentar con año de 4 dígitos
            try:
                return datetime.strptime(fecha_str.strip(), '%d/%m/%Y')
            except ValueError:
                return None
    
    def limpiar_texto(self, texto: str) -> str:
        """Limpia y normaliza un texto."""
        if not texto:
            return ''
        # Remover espacios múltiples
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()
    
    def validar_movimiento(self, movimiento: Dict) -> bool:
        """
        Valida que un movimiento tenga los campos mínimos necesarios.
        """
        campos_requeridos = ['fecha', 'descripcion']
        
        for campo in campos_requeridos:
            if campo not in movimiento or movimiento[campo] is None:
                return False
        
        # Debe tener al menos débito o crédito
        debito = movimiento.get('debito', 0) or 0
        credito = movimiento.get('credito', 0) or 0
        
        if debito == 0 and credito == 0:
            return False
        
        return True


class ParserPDF(BaseParser):
    """
    Clase base para parsers de archivos PDF.
    """
    
    def __init__(self):
        super().__init__()
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
        except ImportError:
            raise ImportError("Necesitas instalar pdfplumber: pip install pdfplumber")
    
    def leer_pdf(self, pdf_path: str) -> str:
        """Lee el PDF y extrae todo el texto."""
        texto_completo = []
        with self.pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    texto_completo.append(texto)
        return '\n'.join(texto_completo)


class ParserExcel(BaseParser):
    """
    Clase base para parsers de archivos Excel/CSV.
    """
    
    def __init__(self):
        super().__init__()
        import pandas as pd
        self.pd = pd
    
    def leer_excel(self, file_path: str, **kwargs) -> 'pd.DataFrame':
        """Lee un archivo Excel."""
        return self.pd.read_excel(file_path, **kwargs)
    
    def leer_csv(self, file_path: str, **kwargs) -> 'pd.DataFrame':
        """Lee un archivo CSV."""
        return self.pd.read_csv(file_path, **kwargs)
