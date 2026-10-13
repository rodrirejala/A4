"""Gestión de usuarios: roles, escalada de privilegios y anti-lockout."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pedidos.roles import GRUPO_ADMINISTRADOR, GRUPO_SOLICITANTE, roles_de

from .base import BasePermisosTest


def payload_usuario(username='nuevo', **overrides):
    data = {
        'username': username,
        'first_name': '',
        'last_name': '',
        'email': '',
        'password1': 'ClaveSegura123',
        'password2': 'ClaveSegura123',
        'es_admin': '',
        'es_solicitante': 'on',
    }
    data.update(overrides)
    return data


class GestionUsuariosTest(BasePermisosTest):
    def setUp(self):
        self.client.force_login(self.admin)

    # -- Creación ----------------------------------------------------------

    def test_crea_un_solicitante(self):
        response = self.client.post(reverse('pedidos:usuario_crear'), payload_usuario('carlos'))
        self.assertEqual(response.status_code, 302)

        nuevo = User.objects.get(username='carlos')
        self.assertEqual(roles_de(nuevo), [GRUPO_SOLICITANTE])
        self.assertTrue(nuevo.check_password('ClaveSegura123'))
        self.assertFalse(nuevo.is_superuser)
        self.assertFalse(nuevo.is_staff)

    def test_crea_un_administrador(self):
        self.client.post(
            reverse('pedidos:usuario_crear'),
            payload_usuario('jefa', es_admin='on', es_solicitante=''),
        )
        nuevo = User.objects.get(username='jefa')
        self.assertEqual(roles_de(nuevo), [GRUPO_ADMINISTRADOR])

    def test_crea_un_usuario_con_ambos_roles(self):
        self.client.post(
            reverse('pedidos:usuario_crear'),
            payload_usuario('mixto', es_admin='on', es_solicitante='on'),
        )
        nuevo = User.objects.get(username='mixto')
        self.assertEqual(roles_de(nuevo), [GRUPO_SOLICITANTE, GRUPO_ADMINISTRADOR])

    def test_exige_al_menos_un_rol(self):
        response = self.client.post(
            reverse('pedidos:usuario_crear'),
            payload_usuario('sinrol', es_admin='', es_solicitante=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tenés que asignar al menos un rol')
        self.assertFalse(User.objects.filter(username='sinrol').exists())

    def test_rechaza_escalada_de_privilegios(self):
        """La pantalla nunca concede is_superuser / is_staff."""
        response = self.client.post(reverse('pedidos:usuario_crear'), payload_usuario(
            'tramposo', is_superuser='on', is_staff='on',
        ))
        self.assertEqual(response.status_code, 302)

        nuevo = User.objects.get(username='tramposo')
        self.assertFalse(nuevo.is_superuser)
        self.assertFalse(nuevo.is_staff)

    # -- Edición -----------------------------------------------------------

    def test_promueve_un_solicitante_a_administrador(self):
        response = self.client.post(
            reverse('pedidos:usuario_editar', args=[self.ana.pk]),
            {'username': 'ana', 'first_name': '', 'last_name': '', 'email': '',
             'es_admin': 'on', 'es_solicitante': 'on'},
        )
        self.assertEqual(response.status_code, 302)

        self.ana.refresh_from_db()
        self.assertIn(GRUPO_ADMINISTRADOR, roles_de(self.ana))

    def test_editar_sin_password_conserva_la_contrasena(self):
        anterior = self.ana.password
        self.client.post(
            reverse('pedidos:usuario_editar', args=[self.ana.pk]),
            {'username': 'ana', 'first_name': '', 'last_name': '', 'email': '',
             'es_admin': '', 'es_solicitante': 'on'},
        )
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.password, anterior)

    def test_editar_con_password_la_cambia(self):
        self.client.post(
            reverse('pedidos:usuario_editar', args=[self.ana.pk]),
            {'username': 'ana', 'first_name': '', 'last_name': '', 'email': '',
             'password1': 'NuevaClave999', 'password2': 'NuevaClave999',
             'es_admin': '', 'es_solicitante': 'on'},
        )
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password('NuevaClave999'))

    def test_no_se_puede_quitar_el_rol_a_si_mismo(self):
        response = self.client.post(
            reverse('pedidos:usuario_editar', args=[self.admin.pk]),
            {'username': self.admin.username, 'first_name': 'Jefe', 'last_name': 'Compras',
             'email': '', 'es_admin': '', 'es_solicitante': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No podés quitarte a vos mismo')

        self.admin.refresh_from_db()
        self.assertIn(GRUPO_ADMINISTRADOR, roles_de(self.admin))

    # -- Desactivación -----------------------------------------------------

    def test_desactiva_un_solicitante_conservando_sus_notas(self):
        response = self.client.post(reverse('pedidos:usuario_borrar', args=[self.ana.pk]))
        self.assertEqual(response.status_code, 302)

        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_active)
        self.assertTrue(User.objects.filter(pk=self.ana.pk).exists())
        self.assertEqual(self.ana.notas_creadas.count(), 1)

    def test_no_puede_desactivarse_a_si_mismo(self):
        self.client.post(reverse('pedidos:usuario_borrar', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_no_puede_desactivar_al_ultimo_administrador(self):
        otro = User.objects.create_user('otro_admin', password='ClaveSegura123')
        otro.groups.add(self.admin.groups.get(name=GRUPO_ADMINISTRADOR))
        # Deja al admin principal como único administrador.
        otro.is_active = False
        otro.save()

        self.client.post(reverse('pedidos:usuario_borrar', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_desactivar_es_idempotente_ante_get(self):
        response = self.client.get(reverse('pedidos:usuario_borrar', args=[self.ana.pk]))
        self.assertEqual(response.status_code, 302)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)

    def test_usuario_desactivado_no_puede_entrar(self):
        self.ana.is_active = False
        self.ana.save()

        self.client.logout()
        response = self.client.post(
            reverse('login'),
            {'username': 'ana', 'password': 'clave12345'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    # -- Listado -----------------------------------------------------------

    def test_listado_muestra_los_tres_grupos(self):
        User.objects.create_user('sin_rol', password='ClaveSegura123')

        response = self.client.get(reverse('pedidos:usuarios'))
        self.assertEqual(response.status_code, 200)

        admins = list(response.context['administradores'])
        solicitantes = list(response.context['solicitantes'])
        sin_rol = list(response.context['sin_rol'])

        self.assertIn(self.admin, admins)
        self.assertIn(self.ana, solicitantes)
        self.assertIn(self.beto, solicitantes)
        self.assertNotIn(self.ana, admins)
        self.assertEqual([u.username for u in sin_rol], ['sin_rol'])

    def test_listado_no_muestra_usuarios_inactivos(self):
        self.ana.is_active = False
        self.ana.save()

        response = self.client.get(reverse('pedidos:usuarios'))
        self.assertNotIn(self.ana, list(response.context['solicitantes']))