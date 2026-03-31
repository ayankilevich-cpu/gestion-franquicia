#!/bin/bash

# ============================================
# Ejecutar App Gestión Franquicia
# ============================================
# Doble clic en este archivo para iniciar la app
# ============================================

# Ir al directorio de la app
cd "$(dirname "$0")"

echo "============================================"
echo "  GESTIÓN FRANQUICIA - Iniciando App..."
echo "============================================"
echo ""

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual (venv)"
    echo "   Ejecuta primero: python -m venv venv"
    echo ""
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

# Activar entorno virtual
source venv/bin/activate

# Verificar que streamlit esté instalado
if ! command -v streamlit &> /dev/null; then
    echo "❌ Error: Streamlit no está instalado"
    echo "   Ejecuta: pip install streamlit"
    echo ""
    read -p "Presiona Enter para cerrar..."
    exit 1
fi

echo "✓ Entorno virtual activado"
echo "✓ Iniciando servidor Streamlit..."
echo ""
echo "La app se abrirá en tu navegador en:"
echo "   http://localhost:8501"
echo ""
echo "Para detener la app, cierra esta ventana o presiona Ctrl+C"
echo "============================================"
echo ""

# Ejecutar la app
streamlit run app.py --server.headless=false

# Mantener ventana abierta si hay error
read -p "Presiona Enter para cerrar..."
