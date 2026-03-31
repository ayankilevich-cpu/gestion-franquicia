"""
Funciones de exportación a Excel.
"""
import pandas as pd
from typing import Dict, List
import io


def exportar_eerr_excel(
    movimientos: List[Dict],
    eerr: Dict,
    periodo: str = ''
) -> bytes:
    """
    Exporta el EERR y movimientos a un archivo Excel en memoria.
    
    Returns:
        bytes: Contenido del archivo Excel
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja de movimientos
        if movimientos:
            df_mov = pd.DataFrame(movimientos)
            if 'fecha' in df_mov.columns:
                df_mov['fecha'] = pd.to_datetime(df_mov['fecha'])
            df_mov.to_excel(writer, sheet_name='Movimientos', index=False)
        
        # Hoja de EERR
        eerr_data = []
        
        # Ingresos
        for cat, monto in sorted(eerr.get('ingresos', {}).items(), key=lambda x: -x[1]):
            eerr_data.append({'Tipo': 'INGRESO', 'Categoría': cat, 'Monto': monto})
        
        # Egresos
        for cat, monto in sorted(eerr.get('egresos', {}).items(), key=lambda x: -x[1]):
            eerr_data.append({'Tipo': 'EGRESO', 'Categoría': cat, 'Monto': monto})
        
        # Totales
        eerr_data.append({'Tipo': '---', 'Categoría': '---', 'Monto': None})
        eerr_data.append({'Tipo': 'TOTAL', 'Categoría': 'Total Ingresos', 'Monto': eerr.get('total_ingresos', 0)})
        eerr_data.append({'Tipo': 'TOTAL', 'Categoría': 'Total Egresos', 'Monto': eerr.get('total_egresos', 0)})
        eerr_data.append({'Tipo': 'RESULTADO', 'Categoría': 'Resultado Operativo', 'Monto': eerr.get('resultado_neto', 0)})
        
        # Traspasos
        if eerr.get('traspasos_entrada', 0) > 0 or eerr.get('traspasos_salida', 0) > 0:
            eerr_data.append({'Tipo': '---', 'Categoría': '---', 'Monto': None})
            eerr_data.append({'Tipo': 'TRASPASO', 'Categoría': 'Traspasos Entrada', 'Monto': eerr.get('traspasos_entrada', 0)})
            eerr_data.append({'Tipo': 'TRASPASO', 'Categoría': 'Traspasos Salida', 'Monto': eerr.get('traspasos_salida', 0)})
        
        pd.DataFrame(eerr_data).to_excel(writer, sheet_name='EERR', index=False)
        
        # Resumen diario
        if movimientos:
            df_mov = pd.DataFrame(movimientos)
            if 'fecha' in df_mov.columns:
                df_mov['fecha'] = pd.to_datetime(df_mov['fecha'])
                df_diario = df_mov.groupby(df_mov['fecha'].dt.date).agg({
                    'debito': 'sum',
                    'credito': 'sum'
                }).reset_index()
                df_diario.columns = ['Fecha', 'Total Débitos', 'Total Créditos']
                df_diario['Flujo Neto'] = df_diario['Total Créditos'] - df_diario['Total Débitos']
                df_diario.to_excel(writer, sheet_name='Flujo Diario', index=False)
    
    return output.getvalue()


def exportar_comparativa_excel(
    datos_periodos: List[Dict],
    periodo_inicio: str,
    periodo_fin: str
) -> bytes:
    """
    Exporta una comparativa de múltiples períodos a Excel.
    """
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Crear DataFrame de comparativa
        df = pd.DataFrame(datos_periodos)
        df.to_excel(writer, sheet_name='Comparativa', index=False)
    
    return output.getvalue()
