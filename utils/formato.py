"""
Funciones de formateo para números en formato argentino.
Separador de miles: . (punto)
Separador decimal: , (coma)
"""


def formato_moneda(valor: float, decimales: int = 2, con_signo: bool = True) -> str:
    """
    Formatea un número como moneda en formato argentino.
    
    Args:
        valor: Número a formatear
        decimales: Cantidad de decimales (default 2)
        con_signo: Si incluir el signo $ (default True)
    
    Returns:
        String formateado: "$1.234.567,89"
    
    Examples:
        formato_moneda(1234567.89) -> "$1.234.567,89"
        formato_moneda(1234567.89, 0) -> "$1.234.568"
        formato_moneda(1234567.89, con_signo=False) -> "1.234.567,89"
    """
    if valor is None:
        return "-"
    
    try:
        valor = float(valor)
    except (ValueError, TypeError):
        return "-"
    
    # Formatear con separador de miles y decimales
    if decimales > 0:
        # Formato con decimales
        formato = f"{abs(valor):,.{decimales}f}"
    else:
        # Formato sin decimales (redondeado)
        formato = f"{abs(valor):,.0f}"
    
    # Cambiar separadores: , -> TEMP, . -> ,, TEMP -> .
    formato = formato.replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Agregar signo negativo si corresponde
    if valor < 0:
        formato = f"-{formato}"
    
    # Agregar símbolo de moneda
    if con_signo:
        return f"${formato}"
    else:
        return formato


def formato_numero(valor: float, decimales: int = 2) -> str:
    """
    Formatea un número sin símbolo de moneda.
    
    Args:
        valor: Número a formatear
        decimales: Cantidad de decimales (default 2)
    
    Returns:
        String formateado: "1.234.567,89"
    """
    return formato_moneda(valor, decimales, con_signo=False)


def formato_porcentaje(valor: float, decimales: int = 1) -> str:
    """
    Formatea un porcentaje.
    
    Args:
        valor: Porcentaje a formatear (ej: 15.5 para 15.5%)
        decimales: Cantidad de decimales (default 1)
    
    Returns:
        String formateado: "15,5%"
    """
    if valor is None:
        return "-"
    
    try:
        valor = float(valor)
    except (ValueError, TypeError):
        return "-"
    
    formato = f"{valor:.{decimales}f}".replace(".", ",")
    return f"{formato}%"


# Función para usar en DataFrames con .style.format()
def formato_df_moneda(valor):
    """Formateador para usar en pandas DataFrame.style.format()"""
    return formato_moneda(valor, decimales=2)


def formato_df_moneda_entero(valor):
    """Formateador para usar en pandas DataFrame.style.format() sin decimales"""
    return formato_moneda(valor, decimales=0)


def formato_df_porcentaje(valor):
    """Formateador para usar en pandas DataFrame.style.format()"""
    return formato_porcentaje(valor, decimales=1)
