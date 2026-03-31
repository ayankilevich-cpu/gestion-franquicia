# Gestion Franquicia - Streamlit

Aplicacion web para gestion financiera de franquicia (EERR, flujo de caja, carga de datos y analisis).

## Ejecutar en local

1. Crear entorno virtual:
   - `python3 -m venv venv`
   - `source venv/bin/activate`
2. Instalar dependencias:
   - `pip install -r requirements.txt`
3. Configurar credenciales MySQL:
   - Copiar `.env.example` a `.env` y completar valores.
4. Ejecutar:
   - `streamlit run app.py`

## Despliegue online (Streamlit Community Cloud)

1. Subir este proyecto a GitHub.
2. En Streamlit Community Cloud:
   - New app -> seleccionar repo `ayankilevich-cpu/gestion-franquicia`
   - Branch: `main`
   - Main file path: `app.py`
3. Cargar secretos en `Settings > Secrets` con este formato:

```toml
MYSQL_HOST = "tu-host-mysql"
MYSQL_PORT = 3306
MYSQL_USER = "tu-usuario"
MYSQL_PASSWORD = "tu-password"
MYSQL_DATABASE = "gestion_franquicia"
```

## Notas importantes

- La base de datos debe aceptar conexiones remotas desde Streamlit Cloud.
- No subir `.env` ni `secrets.toml` al repositorio.
