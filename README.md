# Notas de Pedido — A4 GROUP S.A.

Web app en Django para cargar **notas de pedido (órdenes de compra)** de una
constructora, replicando la estructura de la planilla Excel
`plantillas/formato_nota_pedido.xlsx`.

## Funcionalidades

- 📝 **Formulario de carga** que sigue la estructura del Excel:
  obra, encargado, etapa, fecha, solicitante, prioridad, límite,
  proveedor, vendedor/a, tabla de mercaderías (**hasta 11 ítems** con
  agregar/quitar filas), observaciones, para envío / a retirar / retira.
- 🧾 **N.P. N°** autogenerado (secuencial, a prueba de colisiones).
- 🔐 **Dos roles** con permisos independientes (ver *Roles y usuarios*).
- 🚦 **Estados** por nota: `Pendiente`, `Aprobada` y `Cerrado` (ver *Estados de
  la nota*), con quién aprobó y quién cerró.
- 📦 **Consolidado de compras** que suma lo pedido por material y lo desglosa
  por obra, contra un **catálogo maestro de materiales**, y genera **órdenes de
  compra por proveedor** descargables en Excel (ver *Compras*).
- 🎛️ **Panel del administrador**: ver, editar, eliminar, **aprobar/cerrar**
  (completa "APROBADO POR" / "CERRADO POR" con el usuario de la sesión) y
  **descargar** cada nota en **Excel idéntico al formato** (`.xlsx`), o **todas
  juntas en un `.zip`**.
- 🏗️ Gestión de **Obras**, **Proveedores** y **Usuarios** desde la web.
- 🖨️ Vista imprimible de cada nota.

## Estados de la nota

Cada nota está en `Pendiente`, `Aprobada` o `Cerrado`, definidos en
`ESTADOS_NOTA` (`config/settings.py`). El flujo normal es:

```
Pendiente ──aprobar──► Aprobada ──cerrar──► Cerrado
    ▲                                         │
    └──────────── reabrir ◄───────────────────┘
```

- **Aprobar** y **cerrar** son acciones del administrador; además pueden cambiar
  el estado editando la nota. `Cerrado` es terminal: no se puede aprobar ni
  editar sin reabrir.
- Al cerrar se guarda **quién** cerró (`cerrado_por`) y al aprobar **quién**
  aprobó (`aprobado_por`); ambos aparecen en el Excel.
- **Anular una orden de compra** reabre las notas que esa orden cerró (para que
  la demanda vuelva al consolidado). Las que ya estaban cerradas antes de
  crearla, o que pertenecen a otra orden, quedan como estaban.
- El panel y la exportación a `.zip` filtran por los tres estados.

## Consolidado de compras y órdenes al proveedor

`/compras/` responde "¿qué hay que comprar?" sin repetir lo ya pedido.

1. **Consolida** los ítems de todas las notas **abiertas** (`pendiente` y
   `aprobada`) agrupados por material del catálogo, sumando cantidades y
   **desglosando por obra**. Se pueden filtrar por obra, estado, rango de
   fechas, proveedor, texto libre (`q`) y marcar *incluir lo ya pedido*.
2. Los ítems **sin catalogar** se listan aparte: no se pueden agrupar hasta que
   el administrador les cree un material.
3. Al tildar materiales, elegir un **proveedor** y la fecha, se crea una
   **Orden de Compra**: el servidor **recalcula** las cantidades con los mismos
   filtros y registra de qué notas salen (no confía en lo que manda el
   formulario). Se puede cargar el **precio unitario** por línea y marcar las
   notas como Cerrado.
4. La orden se **descarga en Excel** para mandársela al proveedor, y se puede
   **anular** (eso devuelve sus notas al consolidado).

Al crear una orden, sus notas quedan excluidas del consolidado mientras siga
vigente; al anularla, vuelven a aparecer.

## Catálogo de materiales

El consolidado agrupa por material del **catálogo**, no por el texto libre de
cada nota: así `"CEMENTO"`, `"  cemento "` y `"Cemento"` cuentan como un mismo
material.

- El catálogo se administra en `/materiales/`. Al guardar una nota, el ítem se
  enlaza solo al material cuya clave normalizada coincide con su detalle.
- La normalización (minúsculas, sin tildes, sin puntuación, espacios colapsados)
  **no puede saber equivalencias semánticas**: `cemento 50kg` y
  `cemento 50 kilogramos` quedan separados a propósito.
- Para eso está **Unificar duplicados**: se tildan los materiales que sobran, se
  elige el que queda como oficial, y todos los ítems y líneas de orden se
  reasignan al destino.
- Un material usado en órdenes de compra no se borra: se desactiva.

## Roles y usuarios

La app usa `django.contrib.auth`. Hay dos grupos ("roles"), definidos en
`pedidos/roles.py` y materializados por un comando:

| Rol | Puede hacer |
| --- | --- |
| **Solicitante** | Crear notas de pedido y ver/descargar **solo las suyas**. No ve el panel completo ni las notas de otros. La sección *Para Administración* del formulario (proveedor, vendedor, retira, para envío) la completa el administrador. |
| **Administrador** | Ver **todas** las notas, editarlas, eliminarlas, **aprobar/revertir/cerrar**, descargar `.xlsx` y `.zip`, gestionar obras, proveedores y usuarios, administer el **catálogo de materiales** y crear/anular **órdenes de compra**. |

Los superusuarios de Django tienen acceso total automáticamente.

### Puesta en marcha

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py crear_roles       # crea los grupos con sus permisos
python manage.py createsuperuser   # acceso total a /admin/
python manage.py runserver 0.0.0.0:8000
```

Después, entrar a `/usuarios/` para crear a los solicitantes. También se
puede asignar un rol desde la línea de comandos:

```bash
python manage.py asignar_rol ana Solicitante
python manage.py asignar_rol jefe Administrador
```

> `crear_roles` es **idempotente**: se puede volver a ejecutar después de
> agregar permisos al código.

### Notas sobre el control de acceso

- Ocultar un campo en el template **no** impide enviarlo por POST. Por eso la
  sección *Para Administración* se elimina del formulario (`NotaPedidoForm.CAMPOS_ADMIN`)
  cuando el usuario no es administrador.
- La pantalla `/usuarios/` no puede conceder `is_superuser` ni `is_staff`.
- Un administrador no puede quitarse a sí mismo el rol ni desactivar al último
  administrador, para evitar quedar sin acceso.
- Desactivar un usuario le impide iniciar sesión, pero **no borra** las notas
  que ya creó.

## Tests

```bash
python manage.py test pedidos
```

Cubren la matriz de permisos (anónimo / solicitante / administrador),
aislamiento entre solicitantes, escalada de privilegios, numeración del N.P. N°
y la gestión de usuarios.

Además, en esta versión:

| Archivo | Cubre |
| --- | --- |
| `pedidos/tests/test_estados.py` | Los tres estados, transiciones, cerrado terminal, filtros del panel y `.zip` por estado. |
| `pedidos/tests/test_materiales.py` | Normalización, alta/edición/baja del catálogo, resolución automática de ítems y **unificación de duplicados**. |
| `pedidos/tests/test_compras.py` | Consolidado por material y obra, filtros (incluido `q`), creación de órdenes con precios, anulación, Excel y permisos. |

## Requisitos

- Python 3.12 o superior.

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
git remote add origin https://github.com/rodrirejala/A4.git
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
   git clone https://github.com/rodrirejala/A4.git ~/ordenpedido2
   cd ~/ordenpedido2
   mkvirtualenv --python=3.12 pedidos
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py crear_roles
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
python manage.py crear_roles
python manage.py collectstatic
```

Luego **Reload** el web app.

## Datos de la empresa

Los datos del encabezado (razón social, RUC, dirección, teléfono) están en
`config/settings.py` → diccionario `COMPANY`.

## Roles y permisos (código)

- `pedidos/roles.py` → nombres de los grupos, permisos por rol y helpers
  (`es_admin`, `es_solicitante`, `asegurar_grupos`).
- `NotaPedidoQuerySet.visibles_para(user)` → todas las notas para el
  administrador, solo las propias para el solicitante.
- `pedidos/tests/` → tests de la matriz de permisos.

## Plantilla de exportación

La exportación `.xlsx` usa la plantilla original
`plantillas/formato_nota_pedido.xlsx` (mantiene el diseño y celdas
combinadas). Para modificar el diseño, editar ese archivo.