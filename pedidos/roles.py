"""Definición de los roles de la aplicación y sus permisos.

Los roles se implementan con ``django.contrib.auth`` Groups para poder
reutilizar el panel de permisos nativo y mantenerlos auditables desde /admin/.
Cada grupo tiene un conjunto fijo de permisos ``app_label.codename`` que se
materializa con el comando ``crear_roles``.
"""

from django.contrib.auth.models import Group
from django.db.models import Q

GRUPO_SOLICITANTE = 'Solicitante'
GRUPO_ADMINISTRADOR = 'Administrador'

ROLES = [GRUPO_SOLICITANTE, GRUPO_ADMINISTRADOR]

# El solicitante únicamente genera notas de pedido y consulta las propias.
# No tiene ``view_obra``/``view_proveedor`` a propósito: el listado de obras y
# proveedores es exclusivo del administrador (las sugerencias del formulario
# se resuelven en el servidor, sin exponer esas vistas).
PERMISOS_SOLICITANTE = [
    'pedidos.add_notapedido',
    'pedidos.view_notapedido',
    'pedidos.add_itemnotapedido',
    'pedidos.view_itemnotapedido',
]

# El administrador gestiona todo: notas, obras, proveedores y usuarios.
PERMISOS_ADMINISTRADOR = [
    'pedidos.add_notapedido',
    'pedidos.view_notapedido',
    'pedidos.change_notapedido',
    'pedidos.delete_notapedido',
    'pedidos.add_itemnotapedido',
    'pedidos.view_itemnotapedido',
    'pedidos.change_itemnotapedido',
    'pedidos.delete_itemnotapedido',
    'pedidos.add_obra',
    'pedidos.view_obra',
    'pedidos.change_obra',
    'pedidos.delete_obra',
    'pedidos.add_proveedor',
    'pedidos.view_proveedor',
    'pedidos.change_proveedor',
    'pedidos.delete_proveedor',
    # Catálogo maestro de materiales (consolidado de compras).
    'pedidos.view_material',
    'pedidos.add_material',
    'pedidos.change_material',
    'pedidos.delete_material',
    # Órdenes de compra al proveedor.
    'pedidos.view_ordencompra',
    'pedidos.add_ordencompra',
    'pedidos.change_ordencompra',
    'pedidos.view_ordencompralinea',
    'pedidos.add_ordencompralinea',
    'pedidos.change_ordencompralinea',
    'pedidos.delete_ordencompralinea',
    'auth.add_user',
    'auth.view_user',
    'auth.change_user',
    'auth.delete_user',
]

PERMISOS_POR_ROL = {
    GRUPO_SOLICITANTE: PERMISOS_SOLICITANTE,
    GRUPO_ADMINISTRADOR: PERMISOS_ADMINISTRADOR,
}


def _grupos_activos(user):
    if not user or not user.is_authenticated:
        return set()
    return set(user.groups.values_list('name', flat=True))


def es_admin(user):
    """True si el usuario administra la aplicación (o es superusuario)."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or GRUPO_ADMINISTRADOR in _grupos_activos(user)


def es_solicitante(user):
    """True si el usuario puede generar notas de pedido.

    Un administrador también puede generarlas, por eso no se lo considera
    "solo solicitante".
    """
    if not user or not user.is_authenticated:
        return False
    if es_admin(user):
        return False
    return GRUPO_SOLICITANTE in _grupos_activos(user)


def roles_de(user):
    """Roles asignados al usuario, en el orden de ``ROLES``."""
    activos = _grupos_activos(user)
    return [rol for rol in ROLES if rol in activos]


def _q_permisos(codigos):
    """Combina ``app_label.codename`` en un único ``Q`` (evita homónimos)."""
    q = Q()
    for codigo in codigos:
        app_label, codename = codigo.split('.', 1)
        q |= Q(content_type__app_label=app_label, codename=codename)
    return q


def asegurar_grupos():
    """Crea los grupos con sus permisos. Devuelve ``{rol: Group}``.

    Es idempotente y también corrige permisos agregados al código después de
    haber creado el grupo.
    """
    from django.contrib.auth.models import Permission

    grupos = {}
    for rol, codigos in PERMISOS_POR_ROL.items():
        grupo, _ = Group.objects.get_or_create(name=rol)
        grupo.permissions.set(Permission.objects.filter(_q_permisos(codigos)))
        grupos[rol] = grupo
    return grupos