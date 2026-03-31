"""
Parser para extractos bancarios del Banco Santander.
"""
import re
from typing import List, Dict, Optional
from datetime import datetime

from .base_parser import ParserPDF
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CUIT_EMPRESA


class ParserSantander(ParserPDF):
    """
    Parser específico para extractos del Banco Santander.
    """
    
    def __init__(self):
        super().__init__()
        self.nombre = "Banco Santander"
        self.banco = "SANTANDER"
        
        # Categorías específicas de Santander
        self.categorias_credito = {
            'Transferencias Recibidas': [
                'Transferencia recibida',
                'Transf recibida',
                'Pagos ctas propias',
            ],
        }
        
        self.categorias_debito = {
            'Préstamos Bancarios': [
                'Cobro de prestamo',
            ],
            'Impuesto Débitos y Créditos (Ley 25413)': [
                'Impuesto ley 25.413',
                'ley 25413',
            ],
            'Intereses Bancarios': [
                'Intereses por descubierto',
            ],
            'IVA': [
                'Iva 21%',
                'Iva 10,5%',
                'Iva percepcion',
                'reg trans fisc',
                'reg de transfisc',
            ],
            'Impuestos Provinciales (IIBB/Sellos)': [
                'Impuesto de sellos',
            ],
            'Comisiones Bancarias': [
                'Comision por servicio',
                'Comision',
            ],
        }
    
    def parse(self, file_path: str) -> List[Dict]:
        """Parsea un extracto del Banco Santander."""
        texto = self.leer_pdf(file_path)
        return self.extraer_movimientos(texto)
    
    def extraer_periodo(self, texto: str) -> Optional[Dict]:
        """Extrae información del período del extracto."""
        match_desde = re.search(r'Desde:\s*(\d{2}/\d{2}/\d{2})', texto)
        match_hasta = re.search(r'Hasta:\s*(\d{2}/\d{2}/\d{2})', texto)
        
        if match_desde and match_hasta:
            try:
                fecha_inicio = datetime.strptime(match_desde.group(1), '%d/%m/%y')
                fecha_fin = datetime.strptime(match_hasta.group(1), '%d/%m/%y')
                
                return {
                    'fecha_inicio': fecha_inicio.date(),
                    'fecha_fin': fecha_fin.date(),
                    'anio': fecha_fin.year,
                    'mes': fecha_fin.month,
                }
            except:
                pass
        
        return None
    
    def extraer_movimientos(self, texto: str) -> List[Dict]:
        """Extrae los movimientos del texto del extracto."""
        movimientos = []
        lineas = texto.split('\n')
        
        # Encontrar zona de movimientos (entre "Movimientos en pesos" y "Detalle impositivo")
        inicio_movimientos = 0
        fin_movimientos = len(lineas)
        
        for i, linea in enumerate(lineas):
            if 'Movimientos en pesos' in linea:
                inicio_movimientos = i
            elif 'Detalle impositivo' in linea:
                fin_movimientos = i
                break
        
        # Procesar solo la zona de movimientos
        i = inicio_movimientos
        ultima_fecha = None
        
        while i < fin_movimientos:
            linea = lineas[i].strip()
            
            # Saltar líneas irrelevantes
            if self._es_linea_irrelevante(linea):
                i += 1
                continue
            
            mov = None
            lineas_usadas = 1
            
            # Buscar la fecha en esta línea o usar la última conocida
            fecha_actual = self._extraer_fecha(linea)
            if fecha_actual:
                ultima_fecha = fecha_actual
            
            # Verificar si la línea tiene montos con símbolo $ (es un movimiento)
            if re.search(r'\$\s*[\d.,]+', linea):
                # Determinar fecha para este movimiento
                fecha_mov = fecha_actual
                
                # Si no hay fecha en esta línea, buscar en la línea siguiente
                if not fecha_mov and i + 1 < fin_movimientos:
                    siguiente = lineas[i + 1].strip()
                    fecha_sig = self._extraer_fecha_sola(siguiente)
                    if fecha_sig:
                        fecha_mov = fecha_sig
                        lineas_usadas = 2
                
                # Si aún no hay fecha, usar la última conocida
                if not fecha_mov:
                    fecha_mov = ultima_fecha
                
                if fecha_mov:
                    mov = self._parsear_movimiento(linea, fecha_mov)
            
            if mov and mov['debito'] > 0 or (mov and mov['credito'] > 0):
                # Verificar traspaso interno (CUIT en líneas cercanas)
                mov = self._verificar_traspaso(mov, lineas, i)
                movimientos.append(mov)
            
            i += lineas_usadas
        
        # Eliminar duplicados basados en fecha+descripcion+monto
        return self._eliminar_duplicados(movimientos)
    
    def _es_linea_irrelevante(self, linea: str) -> bool:
        """Determina si la línea debe saltarse."""
        patrones = [
            r'^Cuenta Corriente',
            r'^Fecha\s+Comprobante',
            r'Saldo Inicial',  # No es movimiento, es saldo de apertura
            r'^Saldo total',
            r'^De blema',
            r'^Del \d{2}/\d{2}',
            r'^\d{4}-\d{6,}',  # Referencias tipo 0456-039100...
            r'^CBU:',
            r'^\*\s*Salvo',
            r'^\d+\s*-\s*\d+$',  # Páginas tipo "3 - 7"
            r'^Blema sas 3071',  # Referencia interbanking
        ]
        
        for patron in patrones:
            if re.match(patron, linea, re.IGNORECASE):
                return True
        
        return len(linea) < 3
    
    def _extraer_fecha(self, linea: str) -> Optional[datetime]:
        """Extrae fecha si la línea comienza con DD/MM/YY."""
        match = re.match(r'^(\d{2}/\d{2}/\d{2})\s+', linea)
        if match:
            try:
                return datetime.strptime(match.group(1), '%d/%m/%y')
            except:
                pass
        return None
    
    def _extraer_fecha_sola(self, linea: str) -> Optional[datetime]:
        """Extrae fecha de una línea que es solo la fecha."""
        match = re.match(r'^(\d{2}/\d{2}/\d{2})$', linea.strip())
        if match:
            try:
                return datetime.strptime(match.group(1), '%d/%m/%y')
            except:
                pass
        return None
    
    def _parsear_movimiento(self, linea: str, fecha: datetime) -> Optional[Dict]:
        """Parsea una línea de movimiento."""
        
        # Extraer montos SOLO los que vienen después del símbolo $
        # Formato: $ 154.000,00 $ 154.791,08 o $ 154.000,00 -$ 154.791,08
        montos = re.findall(r'\$\s*([\d.,]+)', linea)
        if not montos:
            return None
        
        # El primer monto es el movimiento, el segundo es el saldo
        monto_mov = self._parsear_monto(montos[0])
        saldo = self._parsear_monto(montos[1]) if len(montos) > 1 else 0
        
        # Ignorar montos muy pequeños o cero
        if monto_mov < 1:
            return None
        
        # Limpiar descripción
        descripcion = linea
        # Quitar fecha del inicio
        descripcion = re.sub(r'^\d{2}/\d{2}/\d{2}\s*', '', descripcion)
        # Quitar comprobante si hay (número largo al inicio)
        match_comp = re.match(r'^(\d{6,})\s+(.+)', descripcion)
        comprobante = ''
        if match_comp:
            comprobante = match_comp.group(1)
            descripcion = match_comp.group(2)
        
        # Quitar montos ($ seguido de número)
        descripcion = re.sub(r'-?\$\s*[\d.,]+', '', descripcion).strip()
        
        # Determinar si es débito o crédito
        es_debito = self._es_debito(descripcion)
        
        return {
            'fecha': fecha,
            'descripcion': descripcion.strip(),
            'referencia': comprobante,
            'debito': monto_mov if es_debito else 0,
            'credito': monto_mov if not es_debito else 0,
            'saldo': saldo,
            'categoria': self._categorizar(descripcion, es_debito),
            'es_traspaso_interno': False,
            'tipo': 'DEBITO' if es_debito else 'CREDITO',
            'cuit_relacionado': '',
        }
    
    def _verificar_traspaso(self, mov: Dict, lineas: List[str], idx: int) -> Dict:
        """Verifica si el movimiento tiene CUIT propio para marcar traspaso."""
        # Buscar CUIT en las 3 líneas siguientes
        for offset in [1, 2, 3]:
            if idx + offset < len(lineas):
                linea_sig = lineas[idx + offset].strip().lower()
                # Buscar CUIT sin guiones
                if '30717192822' in linea_sig:
                    mov['es_traspaso_interno'] = True
                    mov['tipo'] = 'TRASPASO_INTERNO'
                    mov['categoria'] = '*** Traspasos entre Cuentas Propias ***'
                    mov['cuit_relacionado'] = CUIT_EMPRESA
                    break
                # Parar si encontramos otra línea con monto (nuevo movimiento)
                if re.search(r'\$\s*[\d.,]+', linea_sig):
                    break
        
        return mov
    
    def _parsear_monto(self, monto_str: str) -> float:
        """Parsea un monto del formato argentino."""
        if not monto_str:
            return 0.0
        
        monto_str = monto_str.strip().replace('-', '').replace('$', '')
        # Formato argentino: 1.234.567,89 -> 1234567.89
        monto_str = monto_str.replace('.', '').replace(',', '.')
        
        try:
            return float(monto_str)
        except ValueError:
            return 0.0
    
    def _es_debito(self, descripcion: str) -> bool:
        """Determina si una descripción corresponde a un débito."""
        patrones_debito = [
            'cobro de prestamo',
            'impuesto',
            'iva',
            'intereses',
            'comision',
            'sellos',
        ]
        
        desc_lower = descripcion.lower()
        for patron in patrones_debito:
            if patron in desc_lower:
                return True
        
        return False
    
    def _categorizar(self, descripcion: str, es_debito: bool) -> str:
        """Categoriza un movimiento según la descripción."""
        desc_lower = descripcion.lower()
        
        if es_debito:
            categorias = self.categorias_debito
        else:
            categorias = self.categorias_credito
        
        for categoria, patrones in categorias.items():
            for patron in patrones:
                if patron.lower() in desc_lower:
                    return categoria
        
        return 'Otros Egresos' if es_debito else 'Otros Ingresos'
    
    def _eliminar_duplicados(self, movimientos: List[Dict]) -> List[Dict]:
        """Elimina movimientos duplicados."""
        vistos = set()
        unicos = []
        
        for mov in movimientos:
            clave = (
                mov['fecha'].strftime('%Y%m%d'),
                mov['descripcion'][:20],
                mov['debito'],
                mov['credito']
            )
            if clave not in vistos:
                vistos.add(clave)
                unicos.append(mov)
        
        return unicos
    
    def generar_eerr(self, movimientos: List[Dict]) -> Dict:
        """Genera el Estado de Resultados."""
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
