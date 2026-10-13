"""Utilidades compartidas por los tests de permisos."""

from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase

from pedidos import roles
from pedidos.models import (
    ItemNotaPedido, Material, NotaPedido, Obra, OrdenCompra, OrdenCompraLinea, Proveedor,
)
from pedidos.roles import GRUPO_ADMINISTRADOR, GRUPO_SOLICITANTE
from pedidos.textos import normalizar


def crear_usuario(username, rol, password='clave12345', **extra):
    user = User.objects.create_user(username=username, password=password, **extra)
    roles.asegurar_grupos()
    if rol == GRUPO_ADMINISTRADOR:
        user.groups.add(Group.objects.get(name=GRUPO_ADMINISTRADOR))
    elif rol == GRUPO_SOLICITANTE:
        user.groups.add(Group.objects.get(name=GRUPO_SOLICITANTE))
    # Refresca el cache de permisos del usuario recién agregado al grupo.
    return User.objects.get(pk=user.pk)


def payload_nota(**overrides):
    """Payload POST válido para ``pedidos:nueva`` / ``pedidos:editar``."""
    data = {
        'obra_nombre': 'Obra Test',
        'proveedor_nombre': '',
        'encargado': 'Juan Perez',
        'etapa': 'Etapa 1',
        'fecha': date(2026, 3, 15).isoformat(),
        'solicitante': 'Marta',
        'prioridad': 'Media',
        'limite': '',
        'vendedor': '',
        'creado_por': '',
        'observaciones': '',
        'items-TOTAL_FORMS': '1',
        'items-INITIAL_FORMS': '0',
        'items-MIN_NUM_FORMS': '0',
        'items-MAX_NUM_FORMS': '11',
        'items-0-stock': '0',
        'items-0-cantidad': '2',
        'items-0-detalle': 'Cemento',
        'items-0-especificaciones': '50 kg',
        'items-0-estado': '',
        'items-0-precio': '50000',
    }
    data.update(overrides)
    return data


class BasePermisosTest(TestCase):
    """Crea un admin y dos solicitantes, más notas de cada uno."""

    @classmethod
    def setUpTestData(cls):
        roles.asegurar_grupos()
        cls.admin = crear_usuario('jefe', GRUPO_ADMINISTRADOR, first_name='Jefe', last_name='Compras')
        cls.ana = crear_usuario('ana', GRUPO_SOLICITANTE)
        cls.beto = crear_usuario('beto', GRUPO_SOLICITANTE)

        obra = Obra.objects.create(nombre='Obra Test')
        proveedor = Proveedor.objects.create(nombre='Proveedor Test')

        cls.nota_ana = NotaPedido.objects.create(
            numero=1, obra=obra, proveedor=proveedor, fecha=date(2026, 3, 1),
            solicitante='Ana', usuario=cls.ana,
        )
        cls.nota_beto = NotaPedido.objects.create(
            numero=2, obra=obra, fecha=date(2026, 3, 2),
            solicitante='Beto', usuario=cls.beto,
        )
        cls.nota_huerfana = NotaPedido.objects.create(
            numero=3, obra=obra, fecha=date(2026, 3, 3),
            solicitante='Legacy', usuario=None,
        )


def item(nota, detalle, cantidad, **extra):
    """Crea un ítem en ``nota`` y lo enlaza al catálogo si la clave coincide."""
    creado = ItemNotaPedido.objects.create(
        nota=nota, detalle=detalle, cantidad=cantidad, **extra
    )
    material = Material.objects.filter(
        clave=normalizar(detalle), activo=True
    ).first()
    if material:
        creado.material = material
        creado.save(update_fields=['material'])
    return creado


def material(nombre, **extra):
    return Material.objects.create(nombre=nombre, **extra)


def orden(proveedor=None, notas=(), **extra):
    """Orden de compra de prueba; ``notas`` son las que quedaron origen."""
    # ``numero`` no tiene default: en la app lo asigna la vista al crear.
    ultimo = OrdenCompra.objects.order_by('-numero').values_list('numero', flat=True).first()
    defaults = {'fecha': '2026-8-1'}
    defaults.update(extra)
    creada = OrdenCompra.objects.create(
        numero=(ultimo or 0) + 1,
        proveedor=proveedor or Proveedor.objects.first(),
        **defaults,
    )
    creada.notas.set(notas)
    return creada


def linea(orden_compra, material, cantidad, precio=None):
    return OrdenCompraLinea.objects.create(
        orden=orden_compra, material=material, cantidad=cantidad, precio=precio,
    )