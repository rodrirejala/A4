"""Permisos del rol Administrador."""

from django.test import TestCase
from django.urls import reverse

from pedidos.models import NotaPedido

from .base import BasePermisosTest, payload_nota


RUTAS_ADMIN = [
    ('pedidos:panel', {}),
    ('pedidos:nueva', {}),
    ('pedidos:editar', {'pk': 1}),
    ('pedidos:borrar', {'pk': 1}),
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

# Estas rutas exigen POST: un GET solo redirige.
RUTAS_ADMIN_REDIRIGEN = {
    'pedidos:obra_borrar',
    'pedidos:proveedor_borrar',
    'pedidos:usuario_borrar',
}


class AdminTest(BasePermisosTest):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_accede_a_todas_las_rutas(self):
        for nombre, kwargs in RUTAS_ADMIN:
            with self.subTest(ruta=nombre):
                response = self.client.get(reverse(nombre, kwargs=kwargs))
                esperado = 302 if nombre in RUTAS_ADMIN_REDIRIGEN else 200
                self.assertEqual(response.status_code, esperado, f'{nombre} falló')

    def test_ve_todas_las_notas(self):
        response = self.client.get(reverse('pedidos:panel'))
        notas = list(response.context['notas'])

        self.assertIn(self.nota_ana, notas)
        self.assertIn(self.nota_beto, notas)
        self.assertIn(self.nota_huerfana, notas)
        self.assertTrue(response.context['es_admin'])

    def test_ve_el_detalle_de_cualquiera(self):
        for nota in (self.nota_ana, self.nota_beto, self.nota_huerfana):
            with self.subTest(nota=nota.numero):
                response = self.client.get(reverse('pedidos:detalle', args=[nota.pk]))
                self.assertEqual(response.status_code, 200)

    def test_aprueba_una_nota_con_su_propio_nombre(self):
        response = self.client.post(reverse('pedidos:aprobar', args=[self.nota_ana.pk]))
        self.assertEqual(response.status_code, 302)

        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'aprobada')
        self.assertEqual(self.nota_ana.aprobado_por, 'Jefe Compras')

    def test_el_aprobador_no_depende_del_post(self):
        """El nombre del aprobador sale de la sesión, no del formulario."""
        self.client.post(
            reverse('pedidos:aprobar', args=[self.nota_ana.pk]),
            {'aprobado_por': 'Nombre Falso'},
        )
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.aprobado_por, 'Jefe Compras')

    def test_revierte_una_nota_aprobada(self):
        self.nota_ana.estado = 'aprobada'
        self.nota_ana.aprobado_por = 'Alguien'
        self.nota_ana.save()

        self.client.post(reverse('pedidos:aprobar', args=[self.nota_ana.pk]))
        self.nota_ana.refresh_from_db()

        self.assertEqual(self.nota_ana.estado, 'pendiente')
        self.assertEqual(self.nota_ana.aprobado_por, '')

    def test_aprobar_solo_responde_a_post(self):
        response = self.client.get(reverse('pedidos:aprobar', args=[self.nota_ana.pk]))
        self.assertEqual(response.status_code, 302)
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'pendiente')

    def test_edita_una_nota_ajena(self):
        response = self.client.post(
            reverse('pedidos:editar', args=[self.nota_beto.pk]),
            payload_nota(solicitante='Beto Editado'),
        )
        self.assertEqual(response.status_code, 302)

        self.nota_beto.refresh_from_db()
        self.assertEqual(self.nota_beto.solicitante, 'Beto Editado')

    def test_editar_no_cambia_el_numero_ni_el_autor(self):
        self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            payload_nota(),
        )
        self.nota_ana.refresh_from_db()

        self.assertEqual(self.nota_ana.numero, 1)
        self.assertEqual(self.nota_ana.usuario, self.ana)

    def test_el_admin_crea_notas_con_datos_de_administracion(self):
        self.client.post(reverse('pedidos:nueva'), payload_nota(
            proveedor_nombre='Proveedor Nuevo', creado_por='Jefe', para_envio='on', a_retirar='on',
        ))
        nota = NotaPedido.objects.order_by('-id').first()

        self.assertIsNotNone(nota.proveedor)
        self.assertEqual(nota.proveedor.nombre, 'Proveedor Nuevo')
        self.assertTrue(nota.para_envio)
        self.assertTrue(nota.a_retirar)

    def test_borra_una_nota(self):
        self.client.post(reverse('pedidos:borrar', args=[self.nota_beto.pk]))
        self.assertFalse(NotaPedido.objects.filter(pk=self.nota_beto.pk).exists())

    def test_borrar_es_idempotente_ante_get(self):
        """Un GET no borra: pide confirmación."""
        response = self.client.get(reverse('pedidos:borrar', args=[self.nota_beto.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(NotaPedido.objects.filter(pk=self.nota_beto.pk).exists())

    def test_descarga_todas_en_zip(self):
        response = self.client.get(reverse('pedidos:descargar_todas'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_descarga_todas_filtradas_por_estado(self):
        self.nota_ana.estado = 'aprobada'
        self.nota_ana.save()

        response = self.client.get(reverse('pedidos:descargar_todas'), {'estado': 'aprobada'})
        self.assertEqual(response.status_code, 200)

        import zipfile
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            self.assertEqual(len(zf.namelist()), 1)

    def test_zip_vacio_avisa_y_redirige(self):
        NotaPedido.objects.all().delete()
        response = self.client.get(reverse('pedidos:descargar_todas'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('pedidos:panel'))