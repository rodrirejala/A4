"""Acceso de usuarios anónimos: todo debe redirigir al login."""

from django.test import TestCase
from django.urls import reverse

from .base import BasePermisosTest


RUTAS_PROTEGIDAS = [
    ('pedidos:panel', {}),
    ('pedidos:nueva', {}),
    ('pedidos:detalle', {'pk': 1}),
    ('pedidos:editar', {'pk': 1}),
    ('pedidos:borrar', {'pk': 1}),
    ('pedidos:aprobar', {'pk': 1}),
    ('pedidos:descargar', {'pk': 1}),
    ('pedidos:descargar_todas', {}),
    ('pedidos:obras', {}),
    ('pedidos:obra_editar', {'pk': 1}),
    ('pedidos:obra_borrar', {'pk': 1}),
    ('pedidos:proveedores', {}),
    ('pedidos:proveedor_editar', {'pk': 1}),
    ('pedidos:proveedor_borrar', {'pk': 1}),
    ('pedidos:usuarios', {}),
    ('pedidos:usuario_crear', {}),
    ('pedidos:usuario_editar', {'pk': 1}),
    ('pedidos:usuario_borrar', {'pk': 1}),
]


class AnonimoTest(BasePermisosTest):
    def test_login_es_accesible(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_todas_las_rutas_redirigen_al_login(self):
        for nombre, kwargs in RUTAS_PROTEGIDAS:
            with self.subTest(ruta=nombre):
                url = reverse(nombre, kwargs=kwargs)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302, f'{nombre} no redirigió')
                self.assertIn(reverse('login'), response.url)

    def test_post_de_aprobacion_anonimo_no_aproba(self):
        nota = self.nota_ana
        response = self.client.post(reverse('pedidos:aprobar', args=[nota.pk]))
        self.assertEqual(response.status_code, 302)
        nota.refresh_from_db()
        self.assertEqual(nota.estado, 'pendiente')

    def test_logout_solo_acepta_post(self):
        self.client.force_login(self.ana)
        url = reverse('logout')

        self.assertEqual(self.client.get(url).status_code, 405)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)