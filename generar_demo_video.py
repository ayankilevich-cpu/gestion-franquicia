"""
Script para generar un video de demostración de la app de Gestión Financiera.

OPCIÓN 1 - Automático con Playwright:
    Requisitos:
        pip install playwright
        playwright install chromium
    
    Ejecutar:
        python generar_demo_video.py

OPCIÓN 2 - Guión para grabación manual (QuickTime/OBS):
    Si preferís grabar vos mismo, ejecutá:
        python generar_demo_video.py --guion
    
    Te muestra un guión paso a paso con tiempos sugeridos.

OPCIÓN 3 - Screenshots automáticos:
    python generar_demo_video.py --screenshots
    Genera capturas de cada pantalla que podés usar con iMovie/CapCut.
"""

import os
import sys
from datetime import datetime

# Verificar instalación de Playwright (solo si se usa modo automático)
PLAYWRIGHT_DISPONIBLE = False
try:
    from playwright.async_api import async_playwright
    import asyncio
    PLAYWRIGHT_DISPONIBLE = True
except ImportError:
    pass


# =============================================================================
# CONFIGURACIÓN DEL VIDEO
# =============================================================================

VIDEO_OUTPUT = "demo_gestion_financiera.webm"
STREAMLIT_URL = "http://localhost:8501"

# Tamaño del viewport (pantalla que se graba)
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720

# Velocidad de las animaciones (segundos de pausa entre acciones)
VELOCIDAD = "normal"  # "lento", "normal", "rapido"

PAUSAS = {
    "lento": {"corta": 2.0, "media": 3.5, "larga": 5.0},
    "normal": {"corta": 1.0, "media": 2.0, "larga": 3.5},
    "rapido": {"corta": 0.5, "media": 1.0, "larga": 2.0},
}

pausa = PAUSAS[VELOCIDAD]


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

async def esperar(page, tipo="media"):
    """Pausa visual para que el espectador vea el contenido."""
    await asyncio.sleep(pausa[tipo])


async def scroll_suave(page, distancia=300, pasos=3):
    """Realiza scroll suave para mostrar contenido."""
    paso = distancia // pasos
    for _ in range(pasos):
        await page.mouse.wheel(0, paso)
        await asyncio.sleep(0.3)


async def mover_mouse_a_elemento(page, selector, descripcion=""):
    """Mueve el mouse a un elemento para resaltarlo visualmente."""
    try:
        elemento = page.locator(selector).first
        if await elemento.is_visible():
            await elemento.hover()
            await asyncio.sleep(0.5)
            return True
    except:
        pass
    return False


async def click_sidebar_page(page, nombre_pagina):
    """Navega a una página del sidebar de Streamlit."""
    # En Streamlit, los links del sidebar tienen formato específico
    try:
        # Buscar el link en el sidebar
        sidebar = page.locator('[data-testid="stSidebar"]')
        link = sidebar.locator(f'a:has-text("{nombre_pagina}")')
        
        if await link.count() > 0:
            await link.first.click()
            await page.wait_for_load_state("networkidle")
            await esperar(page, "media")
            return True
    except Exception as e:
        print(f"  ⚠️ No se encontró: {nombre_pagina}")
    return False


# =============================================================================
# SCRIPT PRINCIPAL DE GRABACIÓN
# =============================================================================

async def grabar_demo():
    """Graba el video de demostración de la app."""
    
    print("=" * 60)
    print("🎬 GENERADOR DE VIDEO DEMO - Gestión Financiera")
    print("=" * 60)
    print()
    
    # Verificar que Streamlit esté corriendo
    print(f"📡 Conectando a: {STREAMLIT_URL}")
    print("   (Asegurate de que la app esté corriendo con 'streamlit run app.py')")
    print()
    
    async with async_playwright() as p:
        # Crear directorio para video
        video_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Lanzar navegador con grabación de video
        browser = await p.chromium.launch(headless=False)  # headless=False para ver la grabación
        
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            record_video_dir=video_dir,
            record_video_size={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
        )
        
        page = await context.new_page()
        
        try:
            # =================================================================
            # INICIO: Página Principal
            # =================================================================
            print("📍 1/6 - Página Principal")
            
            await page.goto(STREAMLIT_URL)
            await page.wait_for_load_state("networkidle")
            await esperar(page, "larga")
            
            # Mostrar métricas principales
            await scroll_suave(page, 200)
            await esperar(page, "media")
            
            # =================================================================
            # SECCIÓN: EERR Mensual
            # =================================================================
            print("📍 2/6 - Estado de Resultados Mensual")
            
            await click_sidebar_page(page, "EERR_Mensual")
            await esperar(page, "larga")
            
            # Scroll para mostrar el contenido
            await scroll_suave(page, 400)
            await esperar(page, "media")
            
            # Mostrar detalle de egresos si hay expander
            try:
                expander = page.locator('button:has-text("Ver detalle")')
                if await expander.count() > 0:
                    await expander.first.click()
                    await esperar(page, "media")
            except:
                pass
            
            # =================================================================
            # SECCIÓN: Análisis Anual
            # =================================================================
            print("📍 3/6 - Análisis Anual")
            
            await click_sidebar_page(page, "Analisis_Anual")
            await esperar(page, "larga")
            
            # Mostrar gráficos
            await scroll_suave(page, 500)
            await esperar(page, "media")
            
            # =================================================================
            # SECCIÓN: Flujo de Caja
            # =================================================================
            print("📍 4/6 - Flujo de Caja")
            
            await click_sidebar_page(page, "Flujo_Caja")
            await esperar(page, "larga")
            
            await scroll_suave(page, 400)
            await esperar(page, "media")
            
            # =================================================================
            # SECCIÓN: Comparativas
            # =================================================================
            print("📍 5/6 - Comparativas entre Períodos")
            
            await click_sidebar_page(page, "Comparativas")
            await esperar(page, "larga")
            
            # =================================================================
            # SECCIÓN: Carga de Datos
            # =================================================================
            print("📍 6/6 - Carga de Datos")
            
            await click_sidebar_page(page, "Cargar_Datos")
            await esperar(page, "larga")
            
            # Mostrar opciones de carga
            await scroll_suave(page, 300)
            await esperar(page, "media")
            
            # =================================================================
            # CIERRE: Volver a página principal
            # =================================================================
            print("📍 Finalizando...")
            
            # Volver al inicio
            await page.goto(STREAMLIT_URL)
            await page.wait_for_load_state("networkidle")
            await esperar(page, "larga")
            
            print()
            print("✅ Grabación completada!")
            
        except Exception as e:
            print(f"❌ Error durante la grabación: {e}")
            
        finally:
            # Cerrar contexto para guardar el video
            await context.close()
            await browser.close()
            
            # El video se guarda automáticamente
            # Buscar el archivo de video generado
            import glob
            videos = glob.glob(os.path.join(video_dir, "*.webm"))
            if videos:
                # Renombrar al nombre deseado
                ultimo_video = max(videos, key=os.path.getctime)
                output_path = os.path.join(video_dir, VIDEO_OUTPUT)
                
                # Si ya existe, eliminarlo
                if os.path.exists(output_path) and output_path != ultimo_video:
                    os.remove(output_path)
                
                if ultimo_video != output_path:
                    os.rename(ultimo_video, output_path)
                
                print()
                print("=" * 60)
                print(f"🎬 Video guardado en: {output_path}")
                print("=" * 60)
                print()
                print("💡 Tips para el video:")
                print("   - Podés editarlo con iMovie, CapCut o similar")
                print("   - Agregá música de fondo y títulos")
                print("   - Convertí a MP4 si es necesario")
            else:
                print("⚠️ No se encontró el archivo de video generado")


# =============================================================================
# FUNCIÓN ALTERNATIVA: Generar con capturas de pantalla
# =============================================================================

async def generar_con_screenshots():
    """
    Alternativa: genera capturas de pantalla que luego se pueden
    convertir en un video con herramientas externas.
    """
    print("=" * 60)
    print("📸 GENERADOR DE SCREENSHOTS - Gestión Financiera")
    print("=" * 60)
    print()
    
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots_demo")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
        )
        page = await context.new_page()
        
        try:
            pages_to_capture = [
                ("", "01_inicio"),
                ("EERR_Mensual", "02_eerr"),
                ("Analisis_Anual", "03_analisis"),
                ("Flujo_Caja", "04_flujo_caja"),
                ("Comparativas", "05_comparativas"),
                ("Cargar_Datos", "06_cargar_datos"),
            ]
            
            await page.goto(STREAMLIT_URL)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            for page_name, filename in pages_to_capture:
                if page_name:
                    await click_sidebar_page(page, page_name)
                
                screenshot_path = os.path.join(screenshots_dir, f"{filename}.png")
                await page.screenshot(path=screenshot_path, full_page=False)
                print(f"  ✅ Capturado: {filename}.png")
            
            print()
            print(f"📁 Screenshots guardados en: {screenshots_dir}")
            print()
            print("💡 Para convertir a video, usá:")
            print("   ffmpeg -framerate 0.5 -pattern_type glob -i 'screenshots_demo/*.png' \\")
            print("          -c:v libx264 -pix_fmt yuv420p demo_video.mp4")
            
        finally:
            await browser.close()


# =============================================================================
# GUIÓN PARA GRABACIÓN MANUAL
# =============================================================================

def mostrar_guion():
    """
    Muestra un guión detallado para grabar el video manualmente
    con QuickTime, OBS, Loom u otra herramienta de grabación de pantalla.
    """
    guion = """
╔══════════════════════════════════════════════════════════════════════════════╗
║           🎬 GUIÓN DE VIDEO DEMO - GESTIÓN FINANCIERA                        ║
║                     Duración objetivo: 30-45 segundos                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

PREPARACIÓN ANTES DE GRABAR:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Abrí la app: streamlit run app.py
✓ Verificá que haya datos cargados (al menos 1 período)
✓ Usá QuickTime (Archivo > Nueva grabación de pantalla) o Loom
✓ Seleccioná solo la ventana del navegador
✓ Cerrá notificaciones y apps que puedan interrumpir

═══════════════════════════════════════════════════════════════════════════════

ESCENA 1: PÁGINA PRINCIPAL (0:00 - 0:07)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Mostrar: Panel principal con métricas
📍 Acción: Dejá la pantalla estática 2-3 segundos
📍 Destacar: Logo, ventas, egresos, resultado operativo

💬 Texto sugerido para voz en off:
   "Sistema de gestión financiera integrado que consolida
    toda la información de tu negocio en un solo lugar."

═══════════════════════════════════════════════════════════════════════════════

ESCENA 2: EERR MENSUAL (0:07 - 0:15)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Click en: "EERR_Mensual" en el sidebar
📍 Acción: Scroll suave hacia abajo
📍 Destacar: Métricas de ventas vs egresos, gráfico de composición

💬 Texto sugerido:
   "Estado de Resultados mensual con análisis automático
    de cada categoría de gasto."

═══════════════════════════════════════════════════════════════════════════════

ESCENA 3: ANÁLISIS ANUAL (0:15 - 0:22)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Click en: "Analisis_Anual" en el sidebar
📍 Acción: Mostrar gráficos de evolución
📍 Destacar: Tendencia de ventas y egresos en el tiempo

💬 Texto sugerido:
   "Visualización de tendencias anuales para tomar
    decisiones basadas en datos."

═══════════════════════════════════════════════════════════════════════════════

ESCENA 4: FLUJO DE CAJA (0:22 - 0:30)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Click en: "Flujo_Caja" en el sidebar
📍 Acción: Mostrar ingresos vs egresos bancarios
📍 Destacar: Diferencia entre lo facturado y lo cobrado

💬 Texto sugerido:
   "Control de flujo de caja real: sabé exactamente
    cuánto dinero entra y sale de tus cuentas."

═══════════════════════════════════════════════════════════════════════════════

ESCENA 5: CARGA DE DATOS (0:30 - 0:37)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Click en: "Cargar_Datos" en el sidebar
📍 Acción: Mostrar opciones de carga (bancos soportados)
📍 Destacar: Soporte multi-banco

💬 Texto sugerido:
   "Cargá extractos de Macro, Santander, Nación y Mercado Pago
    de forma automática."

═══════════════════════════════════════════════════════════════════════════════

ESCENA 6: CIERRE (0:37 - 0:45)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Volver a: Página principal
📍 Acción: Dejar métricas visibles
📍 Agregar: Slide final con datos de contacto

💬 Texto sugerido:
   "Automatizá tu gestión financiera.
    Contactame para más información."

═══════════════════════════════════════════════════════════════════════════════

POST-PRODUCCIÓN (OPCIONAL):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Agregá música de fondo (libre de derechos)
• Añadí títulos en cada escena
• Incluí logo y datos de contacto al final
• Exportá en 1080p para mejor calidad

HERRAMIENTAS RECOMENDADAS:
• iMovie (Mac) - Gratis, fácil de usar
• CapCut - Gratis, muchos efectos
• Canva - Para crear intro/outro
• Loom - Graba y comparte rápido

═══════════════════════════════════════════════════════════════════════════════
"""
    print(guion)


# =============================================================================
# EJECUCIÓN
# =============================================================================

if __name__ == "__main__":
    # Verificar argumentos de línea de comandos
    if "--guion" in sys.argv or "-g" in sys.argv:
        mostrar_guion()
        sys.exit(0)
    
    if "--screenshots" in sys.argv or "-s" in sys.argv:
        if not PLAYWRIGHT_DISPONIBLE:
            print("❌ Playwright no está instalado.")
            print("   Instalá con: pip install playwright")
            print("   Luego ejecutá: playwright install chromium")
            sys.exit(1)
        import asyncio
        asyncio.run(generar_con_screenshots())
        sys.exit(0)
    
    print()
    print("🎬 GENERADOR DE VIDEO DEMO - Gestión Financiera")
    print("=" * 55)
    print()
    print("Seleccioná el modo de generación:")
    print()
    if PLAYWRIGHT_DISPONIBLE:
        print("  1. Video automático (Playwright instalado ✓)")
        print("  2. Screenshots automáticos")
    else:
        print("  1. Video automático (requiere Playwright - NO instalado)")
        print("  2. Screenshots automáticos (requiere Playwright)")
    print("  3. Ver guión para grabación manual (RECOMENDADO)")
    print()
    
    try:
        opcion = input("Opción [3]: ").strip() or "3"
    except:
        opcion = "3"
    
    if opcion == "1":
        if not PLAYWRIGHT_DISPONIBLE:
            print()
            print("❌ Playwright no está instalado.")
            print("   Instalá con: pip install playwright")
            print("   Luego ejecutá: playwright install chromium")
            print()
            print("💡 Mientras tanto, usá la opción 3 (guión manual)")
            sys.exit(1)
        import asyncio
        asyncio.run(grabar_demo())
    elif opcion == "2":
        if not PLAYWRIGHT_DISPONIBLE:
            print()
            print("❌ Playwright no está instalado.")
            print("   Instalá con: pip install playwright")
            sys.exit(1)
        import asyncio
        asyncio.run(generar_con_screenshots())
    else:
        mostrar_guion()
