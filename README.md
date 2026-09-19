# Notas de Pedido — A4 GROUP S.A.

Web app en Django para cargar **notas de pedido (órdenes de compra)** de una
constructora, replicando la estructura de la planilla Excel
`FORMATO PARA NOTA DE PEDIDO.xlsx`.

## Funcionalidades

- 📝 **Formulario de carga** que sigue la estructura del Excel:
  obra, encargado, etapa, fecha, solicitante, prioridad, límite,
  proveedor, vendedor/a, tabla de mercaderías (**hasta 11 ítems** con
  agregar/quitar filas), observaciones, para envío / a retirar / retira.
- 🧾 **N.P. N°** autogenerado (secuencial).
- 🎛️ **Panel del encargado de compras**: ver, editar, eliminar, **aprobar**
  (completa "APROBADO POR") y **descargar** cada nota en **Excel idéntico
  al formato** (`.xlsx`), o **todas juntas en un `.zip`**.
- 🏗️ Gestión de **Obras** y **Proveedores** desde la web.
- 🖨️ Vista imprimible de cada nota.

## Requisitos

- Python 3.12 o superior.

## Puesta en marcha (local)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # acceso a /admin/
python manage.py runserver 0.0.0.0:8000
```

Abrir `http://127.0.0.1:8000`. En la red local se accede con la IP de la PC
(por ejemplo `http://192.168.0.247:8000`).

> Los valores sensibles de producción se manejan con **variables de
> entorno** (ver sección de despliegue). En local `DEBUG=True` y no es
> necesario configurarlas.

## Despliegue en PythonAnywhere (link público)

### 1. Subir el código a GitHub

En esta carpeta (primera vez):

```bash
git init
git add .
git commit -m "Notas de Pedido - A4 GROUP S.A."
git branch -M main
git remote add origin https://github.com/TUUSUARIO/ordenpedido2.git
git push -u origin main
```

> `.gitignore` ya excluye `db.sqlite3`, `.venv/` y `staticfiles/` (no se
> suben; la base de PythonAnywhere se crea limpia con `migrate`).

### 2. Crear el sitio en PythonAnywhere

1. Crear cuenta en [pythonanywhere.com](https://www.pythonanywhere.com) con
   usuario `tuusuario` → el link será `https://tuusuario.pythonanywhere.com`.
2. Pestaña **Web** → **Add a new web app** → *Manual configuration* →
   **Python 3.12** → **Next**.
3. Apertura de una **Bash console** (pestaña Consoles) y clonar el repo:

   ```bash
   git clone https://github.com/TUUSUARIO/ordenpedido2.git ~/ordenpedido2
   cd ~/ordenpedido2
   mkvirtualenv --python=3.12 pedidos
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic
   python manage.py createsuperuser
   ```

4. Pestaña **Web** → **Code** → crear una **Environment variable** con cada
   línea:

   ```text
   DJANGO_DEBUG=False
   DJANGO_SECRET_KEY=<clave secreta larga y única>
   DJANGO_ALLOWED_HOSTS=tuusuario.pythonanywhere.com
   ```

   Para generar una clave segura:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

5. Pestaña **Web** → **Code** → **WSGI configuration file**, reemplazar todo
   por:

   ```python
   import os, sys
   sys.path.insert(0, '/home/tuusuario/ordenpedido2')
   os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

6. Pestaña **Web** → **Static files**:
   - URL: `/static/` → Directorio: `/home/tuusuario/ordenpedido2/staticfiles/`.
7. **Reload** el Web App. Listo: `https://tuusuario.pythonanywhere.com`.

> En el plan gratuito la app se pausa cuando no recibe visitas y despierta
> con la primera visita (tarda unos segundos). Para uso continuo se
> recomienda un plan de pago.

### 3. Actualizar el sitio después de cambios

```bash
git add . && git commit -m "cambios" && git push
```

Y en la **Bash console** de PythonAnywhere:

```bash
cd ~/ordenpedido2 && git pull
source ~/.virtualenvs/pedidos/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic
```

Luego **Reload** el web app.

## Datos de la empresa

Los datos del encabezado (razón social, RUC, dirección, teléfono) están en
`config/settings.py` → diccionario `COMPANY`.

## Plantilla de exportación

La exportación `.xlsx` usa la plantilla original
`plantillas/formato_nota_pedido.xlsx` (mantiene el diseño y celdas
combinadas). Para modificar el diseño, editar ese archivo.