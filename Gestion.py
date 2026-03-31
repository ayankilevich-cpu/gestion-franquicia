from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# 🔐 Tus credenciales
USUARIO = "ayankilevich@gmail.com"
CONTRASENA = "211083"

 # Inicializar navegador
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.maximize_window()

# Ir al login
driver.get("https://api.gestionfranquicias.com.ar/Account/Login?app_uniqueId=4E04802B-A830-45A7-8047-C2391414F067")

# Esperar carga visual
time.sleep(4)

# Ingresar datos
usuario_input = driver.find_element(By.ID, "MainContent_txtUsuario")
password_input = driver.find_element(By.ID, "MainContent_txtPassword")
usuario_input.send_keys(USUARIO)
password_input.send_keys(CONTRASENA)

# Enviar formulario presionando Enter
password_input.send_keys(Keys.RETURN)

# Esperar que cargue la siguiente pantalla
time.sleep(7)
driver.save_screenshot("login_correcto.png")

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd

# --- Configuración de descarga ---
download_dir = os.path.join(os.path.expanduser("~"), "Downloads")

chrome_options = Options()
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True
})

# --- Iniciar navegador ---
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.maximize_window()

# --- Login ---
driver.get("https://api.gestionfranquicias.com.ar/Account/Login?app_uniqueId=4E04802B-A830-45A7-8047-C2391414F067")
time.sleep(3)

driver.find_element(By.ID, "MainContent_txtUsuario").send_keys("ayankilevich@gmail.com")
driver.find_element(By.ID, "MainContent_txtPassword").send_keys("211083")
driver.find_element(By.ID, "MainContent_txtPassword").send_keys(Keys.RETURN)
time.sleep(5)

# Después del login...

# Ir directamente a la URL de movimientos de Helacor
driver.get("https://gestionfranquicias.com.ar/helacor/franquiciados/cuenta-corriente/SAP/default2.aspx?sociedad=1000")
time.sleep(5)

# Hacer clic en botón Excel
driver.find_element(By.XPATH, '//button[contains(text(), "Excel")]').click()
time.sleep(7)