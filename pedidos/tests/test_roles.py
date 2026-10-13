"""Helpers de roles y permisos de los grupos."""

from django.test import TestCase

from pedidos import roles

from .base import BasePermisosTest


class HelpersTest(BasePermisosTest):
    def test_es_admin(self):
        self.assertTrue(roles.es_admin(self.admin))
        self.assertFalse(roles.es_admin(self.ana))
        self.assertFalse(roles.es_admin(None))

    def test_superuser_es_admin_aunque_no_tenga_grupo(self):
        from django.contrib.auth.models import User

        superuser = User.objects.create_superuser('root', 'root@x.com', 'ClaveSegura123')
        self.assertTrue(roles.es_admin(superuser))
        self.assertFalse(roles.es_solicitante(superuser))

    def test_es_solicitante_excluye_al_admin(self):
        self.assertTrue(roles.es_solicitante(self.ana))
        self.assertFalse(roles.es_solicitante(self.admin))

    def test_es_solicitante_false_para_anonimo(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(roles.es_solicitante(AnonymousUser()))
        self.assertFalse(roles.es_admin(AnonymousUser()))

    def test_usuario_sin_grupo_no_es_nada(self):
        from django.contrib.auth.models import User

        huerfano = User.objects.create_user('huerfano', password='ClaveSegura123')
        self.assertFalse(roles.es_admin(huerfano))
        self.assertFalse(roles.es_solicitante(huerfano))
        self.assertEqual(roles.roles_de(huerfano), [])

    def test_roles_de_conserva_orden_declarado(self):
        self.ana.groups.add(self.admin.groups.get(name=roles.GRUPO_ADMINISTRADOR))
        self.assertEqual(
            roles.roles_de(self.ana),
            [roles.GRUPO_SOLICITANTE, roles.GRUPO_ADMINISTRADOR],
        )

    def test_asegurar_grupos_es_idempotente(self):
        roles.asegurar_grupos()
        primero = roles.asegurar_grupos()
        segundo = roles.asegurar_grupos()

        for nombre in roles.ROLES:
            self.assertEqual(primero[nombre].pk, segundo[nombre].pk)
            self.assertEqual(primero[nombre].permissions.count(), segundo[nombre].permissions.count())

    def test_solicitante_no_tiene_permisos_de_escritura(self):
        self.assertFalse(self.ana.has_perm('pedidos.change_notapedido'))
        self.assertFalse(self.ana.has_perm('pedidos.delete_notapedido'))
        self.assertFalse(self.ana.has_perm('auth.add_user'))
        self.assertTrue(self.ana.has_perm('pedidos.add_notapedido'))
        self.assertTrue(self.ana.has_perm('pedidos.view_notapedido'))

    def test_admin_tiene_todos_los_permisos_de_la_app(self):
        for codigo in roles.PERMISOS_ADMINISTRADOR:
            with self.subTest(permiso=codigo):
                self.assertTrue(self.admin.has_perm(codigo))