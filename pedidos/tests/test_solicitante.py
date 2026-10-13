"""Matriz de permisos del rol Solicitante."""

from django.test import TestCase
from django.urls import reverse

from pedidos.models import NotaPedido

from .base import BasePermisosTest, payload_nota


RUTAS_SOLO_ADMIN = [
    ('pedidos:editar', {'pk': 1}),
    ('pedidos:borrar', {'pk': 1}),
    ('pedidos:aprobar', {'pk': 1}),
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


class SolicitanteTest(BasePermisosTest):
    def setUp(self):
        self.client.force_login(self.ana)

    # -- Lo que sí puede hacer ---------------------------------------------

    def test_accede_al_panel(self):
        self.assertEqual(self.client.get(reverse('pedidos:panel')).status_code, 200)

    def test_accede_al_formulario_de_nueva_nota(self):
        self.assertEqual(self.client.get(reverse('pedidos:nueva')).status_code, 200)

    def test_crea_una_nota_y_queda_a_su_nombre(self):
        antes = NotaPedido.objects.count()
        response = self.client.post(reverse('pedidos:nueva'), payload_nota())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(NotaPedido.objects.count(), antes + 1)

        nota = NotaPedido.objects.order_by('-id').first()
        self.assertEqual(nota.usuario, self.ana)
        self.assertEqual(nota.creado_por, 'ana')
        self.assertEqual(nota.numero, 4)

    def test_descarga_su_propia_nota_en_excel(self):
        url = reverse('pedidos:descargar', args=[self.nota_ana.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            response['Content-Type'],
        )

    def test_ve_su_propia_nota_en_el_detalle(self):
        response = self.client.get(reverse('pedidos:detalle', args=[self.nota_ana.pk]))
        self.assertEqual(response.status_code, 200)

    # -- Aislamiento entre solicitantes ------------------------------------

    def test_el_panel_solo_muestra_sus_notas(self):
        response = self.client.get(reverse('pedidos:panel'))
        notas = list(response.context['notas'])

        self.assertIn(self.nota_ana, notas)
        self.assertNotIn(self.nota_beto, notas)
        self.assertNotIn(self.nota_huerfana, notas)

    def test_no_ve_el_detalle_de_otro_solicitante(self):
        response = self.client.get(reverse('pedidos:detalle', args=[self.nota_beto.pk]))
        self.assertEqual(response.status_code, 404)

    def test_no_descarga_la_nota_de_otro_solicitante(self):
        response = self.client.get(reverse('pedidos:descargar', args=[self.nota_beto.pk]))
        self.assertEqual(response.status_code, 404)

    def test_no_ve_notas_huerfanas(self):
        """Notas sin usuario solo son visibles para administradores."""
        response = self.client.get(reverse('pedidos:detalle', args=[self.nota_huerfana.pk]))
        self.assertEqual(response.status_code, 404)

    def test_el_contador_refleja_solo_sus_notas(self):
        response = self.client.get(reverse('pedidos:panel'))
        self.assertEqual(response.context['cant_pendientes'], 1)
        self.assertEqual(response.context['cant_aprobadas'], 0)

    def test_es_admin_es_falso_en_el_contexto(self):
        response = self.client.get(reverse('pedidos:panel'))
        self.assertFalse(response.context['es_admin'])

    # -- Lo que no puede hacer --------------------------------------------

    def test_todas_las_rutas_de_admin_dan_403(self):
        for nombre, kwargs in RUTAS_SOLO_ADMIN:
            with self.subTest(ruta=nombre):
                response = self.client.get(reverse(nombre, kwargs=kwargs))
                self.assertEqual(response.status_code, 403, f'{nombre} no dio 403')

    def test_no_puede_aprobar_una_nota_por_post(self):
        response = self.client.post(reverse('pedidos:aprobar', args=[self.nota_beto.pk]))
        self.assertEqual(response.status_code, 403)
        self.nota_beto.refresh_from_db()
        self.assertEqual(self.nota_beto.estado, 'pendiente')

    def test_no_puede_borrar_una_nota(self):
        response = self.client.post(reverse('pedidos:borrar', args=[self.nota_beto.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(NotaPedido.objects.filter(pk=self.nota_beto.pk).exists())

    def test_no_puede_crear_una_nota_con_datos_de_administracion(self):
        """La sección Para Administración no se envía ni se guarda."""
        self.client.post(reverse('pedidos:nueva'), payload_nota(
            proveedor_nombre='Proveedor Oculto', creado_por='Mentira', para_envio='on',
        ))
        nota = NotaPedido.objects.order_by('-id').first()

        self.assertIsNone(nota.proveedor)
        self.assertEqual(nota.creado_por, 'ana')
        self.assertFalse(nota.para_envio)

    def test_no_ve_la_seccion_para_administracion_en_el_form(self):
        response = self.client.get(reverse('pedidos:nueva'))
        self.assertNotContains(response, 'Para Administración')