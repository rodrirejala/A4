"""Estados de la nota: pendientes, aprobada, cerrado y sus transiciones."""

from django.urls import reverse

from pedidos.models import ItemNotaPedido, NotaPedido
from pedidos.roles import GRUPO_SOLICITANTE

from .base import BasePermisosTest, crear_usuario


class EstadosNotaTest(BasePermisosTest):
    def setUp(self):
        self.client.force_login(self.admin)
        self.nota = self.nota_ana

    def _cerrar(self, nota=None):
        return self.client.post(reverse('pedidos:cerrar', args=[(nota or self.nota).pk]))

    def test_estado_inicial_es_pendiente(self):
        nota = NotaPedido.objects.create(
            numero=99, fecha='2026-3-15', solicitante='Nueva',
        )
        self.assertEqual(nota.estado, 'pendiente')

    def test_admin_aproba_y_vuelve_a_pendiente(self):
        self.client.post(reverse('pedidos:aprobar', args=[self.nota.pk]))
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'aprobada')
        self.assertEqual(self.nota.aprobado_por, 'Jefe Compras')

        self.client.post(reverse('pedidos:aprobar', args=[self.nota.pk]))
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'pendiente')
        self.assertEqual(self.nota.aprobado_por, '')

    def test_cerrar_y_reabrir(self):
        self._cerrar()
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'cerrado')
        self.assertEqual(self.nota.cerrado_por, 'Jefe Compras')
        self.assertTrue(self.nota.esta_cerrada)
        self.assertEqual(self.nota.clase_estado, 'secondary')

        self._cerrar()
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'pendiente')
        self.assertEqual(self.nota.cerrado_por, '')

    def test_una_nota_cerrada_no_se_puede_aprobar(self):
        """Cerrado es terminal: aprobar no la reabre por abajo."""
        self._cerrar()
        self.client.post(reverse('pedidos:aprobar', args=[self.nota.pk]))
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'cerrado')

    def test_cerrar_conserva_el_aprobador_para_la_firma_del_excel(self):
        self.client.post(reverse('pedidos:aprobar', args=[self.nota.pk]))
        self._cerrar()
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.aprobado_por, 'Jefe Compras')

    def test_cerrar_ignora_get(self):
        """Solo POST: un link malicioso no cierra notas."""
        self.client.get(reverse('pedidos:cerrar', args=[self.nota.pk]))
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'pendiente')

    def test_solicitante_no_puede_cerrar(self):
        self.client.force_login(self.ana)
        self.assertEqual(self._cerrar().status_code, 403)
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.estado, 'pendiente')

    def test_solicitante_no_puede_aprobar(self):
        self.client.force_login(self.ana)
        self.assertEqual(
            self.client.post(reverse('pedidos:aprobar', args=[self.nota.pk])).status_code, 403
        )

    def test_otros_no_pueden_cerrar_una_nota_ajena(self):
        """La nota de Beto es visible para Ana (admin-solo) pero no cerrable."""
        otro = crear_usuario('otro', GRUPO_SOLICITANTE)
        self.client.force_login(otro)
        self.assertEqual(
            self.client.post(reverse('pedidos:cerrar', args=[self.nota_beto.pk])).status_code, 403
        )

    def test_clase_estado_de_cada_valor(self):
        self.assertEqual(self.nota.clase_estado, 'warning')
        self.nota.estado = 'aprobada'
        self.assertEqual(self.nota.clase_estado, 'success')


class FiltroEstadoTest(BasePermisosTest):
    """El filtro del panel tiene que conocer los tres estados."""

    def setUp(self):
        self.client.force_login(self.admin)
        self.nota_huerfana.estado = 'cerrado'
        self.nota_huerfana.save(update_fields=['estado'])

    def test_filtro_acepta_cerrado(self):
        """Regresión: la lista fija ('pendiente','aprobada') descartaba 'cerrado'."""
        response = self.client.get(reverse('pedidos:panel'), {'estado': 'cerrado'})
        self.assertEqual(response.status_code, 200)
        notas = list(response.context['notas'])
        self.assertEqual([n.pk for n in notas], [self.nota_huerfana.pk])

    def test_filtro_por_cada_estado(self):
        for estado, esperadas in (
            ('pendiente', [self.nota_ana, self.nota_beto]),
            ('aprobada', []),
            ('cerrado', [self.nota_huerfana]),
        ):
            with self.subTest(estado=estado):
                response = self.client.get(reverse('pedidos:panel'), {'estado': estado})
                self.assertEqual(
                    sorted(n.pk for n in response.context['notas']),
                    sorted(n.pk for n in esperadas),
                )

    def test_filtro_desconocido_no_falla(self):
        response = self.client.get(reverse('pedidos:panel'), {'estado': 'inventado'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notas']), 3)

    def test_contadores_incluyen_cerradas(self):
        response = self.client.get(reverse('pedidos:panel'))
        self.assertEqual(response.context['cant_cerradas'], 1)
        self.assertEqual(response.context['contadores']['cerrado'], 1)

    def test_descargar_todas_filtra_por_cerrado(self):
        """El .zip debe traer solo la cerrada (no devuelve una plantilla)."""
        import io
        import zipfile

        response = self.client.get(reverse('pedidos:descargar_todas'), {'estado': 'cerrado'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            nombres = zf.namelist()
        self.assertEqual(nombres, [f'NP_{self.nota_huerfana.numero:03d}_Obra Test.xlsx'])

    def test_select_de_estados_se_genera_desde_settings(self):
        """Las opciones del <select> no están escritas a mano."""
        from django.conf import settings

        response = self.client.get(reverse('pedidos:panel'))
        html = response.content.decode()
        for codigo, etiqueta in settings.ESTADOS_NOTA:
            self.assertIn(f'value="{codigo}"', html)
            self.assertIn(etiqueta, html)


class EstadoDesdeFormularioTest(BasePermisosTest):
    """El admin puede llevar la nota a 'cerrado' editándola."""

    def setUp(self):
        self.client.force_login(self.admin)

    def _payload(self, **extra):
        data = {
            'obra_nombre': self.nota_ana.obra.nombre,
            'proveedor_nombre': '',
            'encargado': '', 'etapa': '', 'fecha': '2026-03-15',
            'solicitante': 'Ana', 'prioridad': 'Media', 'limite': '',
            'vendedor': '', 'creado_por': '', 'para_envio': '', 'a_retirar': '',
            'retira': '', 'observaciones': '',
            'estado': 'cerrado',
            'items-TOTAL_FORMS': '0', 'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '11',
        }
        data.update(extra)
        return data

    def test_admin_cierra_desde_el_formulario(self):
        self.client.post(reverse('pedidos:editar', args=[self.nota_ana.pk]), self._payload())
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'cerrado')
        self.assertEqual(self.nota_ana.cerrado_por, 'Jefe Compras')

    def test_reabrir_una_cerrada_desde_el_formulario(self):
        """Reabrir y editar en un solo POST: el guard solo bloquea si sigue cerrada."""
        self.client.post(reverse('pedidos:editar', args=[self.nota_ana.pk]), self._payload())
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'cerrado')

        self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            self._payload(estado='pendiente', **{
                'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '0',
                'items-0-cantidad': '3', 'items-0-detalle': 'Cemento',
                'items-0-especificaciones': '',
            }),
        )
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'pendiente')

    def test_no_se_puede_editar_una_cerrada_sin_reabrirla(self):
        """Cerrado es un sello: editar el contenido exigiría dejarla cerrada."""
        self.client.post(reverse('pedidos:editar', args=[self.nota_ana.pk]), self._payload())
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'cerrado')

        respuesta = self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            self._payload(**{
                'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '0',
                'items-0-cantidad': '999', 'items-0-detalle': 'Cambiado',
                'items-0-especificaciones': '',
            }),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.nota_ana.refresh_from_db()
        self.assertEqual(self.nota_ana.estado, 'cerrado')
        self.assertEqual(
            ItemNotaPedido.objects.filter(nota=self.nota_ana, detalle='Cambiado').count(), 0
        )

    def test_solicitante_no_puede_inyectar_el_estado(self):
        """``estado`` es un campo admin: no se acepta por POST."""
        self.client.force_login(self.ana)
        self.assertEqual(
            self.client.post(
                reverse('pedidos:editar', args=[self.nota_ana.pk]), self._payload()
            ).status_code,
            403,
        )