"""Catálogo maestro de materiales: normalización, resolver y unificar."""

from django.db import IntegrityError, transaction
from django.urls import reverse

from pedidos.models import Material
from pedidos.textos import normalizar

from .base import BasePermisosTest, item, linea, material, orden


class NormalizarTextoTest(BasePermisosTest):
    """``normalizar`` es lo que decide si dos textos son el mismo material."""

    def test_ignora_mayusculas_y_acentos(self):
        self.assertEqual(normalizar('CEMENTO'), normalizar('ceménto'))

    def test_colapsa_espacios(self):
        self.assertEqual(normalizar('  cemento   Portland  '), 'cemento portland')

    def test_unifica_tildes_y_comas(self):
        self.assertEqual(normalizar('CEMENTO, 50 kilogramos'), 'cemento 50 kilogramos')

    def test_no_puede_inventar_equivalencias(self):
        """La normalización es textual: '50kg' y '50 kilogramos' siguen distintas.

        Eso es a propósito: unir equivalencias semánticas es decisión del admin
        (vista de fusión), no del código.
        """
        self.assertNotEqual(normalizar('cemento 50kg'), normalizar('cemento 50 kilogramos'))


class MaterialCRUDTest(BasePermisosTest):
    def setUp(self):
        self.client.force_login(self.admin)

    def test_crear_material_calcula_la_clave(self):
        response = self.client.post(reverse('pedidos:materiales'), {
            'nombre': '  Bolsas de Cemento ',
            'unidad': 'bolsa', 'especificacion': '50 kg', 'notas': '', 'activo': 'on',
        })
        self.assertEqual(response.status_code, 302)
        nuevo = Material.objects.get(nombre='Bolsas de Cemento')
        self.assertEqual(nuevo.clave, 'bolsas de cemento')
        self.assertEqual(nuevo.unidad, 'bolsa')

    def test_rechaza_duplicado_por_normalizacion(self):
        material('Bolsas de Cemento')
        response = self.client.post(reverse('pedidos:materiales'), {
            'nombre': 'BOLSAS de CEMENTO', 'unidad': '', 'especificacion': '',
            'notas': '', 'activo': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('nombre', response.context['form'].errors)
        self.assertEqual(Material.objects.filter(clave='bolsas de cemento').count(), 1)

    def test_editar_no_choca_consigo_mismo(self):
        """Reenviar el mismo nombre no debe dar 'duplicado'."""
        cemento = material('Cemento', unidad='bolsa')
        response = self.client.post(
            reverse('pedidos:material_editar', args=[cemento.pk]),
            {'nombre': 'Cemento', 'unidad': 'saco', 'especificacion': '',
             'notas': '', 'activo': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        cemento.refresh_from_db()
        self.assertEqual(cemento.unidad, 'saco')

    def test_borrar_con_items_los_deja_sin_catalogar(self):
        cemento = material('Cemento')
        it = item(self.nota_ana, 'Cemento', 10)
        self.client.post(reverse('pedidos:material_borrar', args=[cemento.pk]))
        self.assertFalse(Material.objects.filter(pk=cemento.pk).exists())
        it.refresh_from_db()
        self.assertIsNone(it.material)
        self.assertEqual(it.detalle, 'Cemento')

    def test_borrar_con_ordenes_lo_desactiva_en_vez_de_borrarlo(self):
        cemento = material('Cemento')
        linea(orden(), cemento, 5)
        self.client.post(reverse('pedidos:material_borrar', args=[cemento.pk]))
        cemento.refresh_from_db()
        self.assertTrue(Material.objects.filter(pk=cemento.pk).exists())
        self.assertFalse(cemento.activo)

    def test_solicitante_no_administra_el_catalogo(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('pedidos:materiales')).status_code, 403)


class ResolucionDeMaterialTest(BasePermisosTest):
    """Al guardar una nota, el texto libre debe pegarse al catálogo."""

    def setUp(self):
        self.client.force_login(self.admin)
        self.cemento = material('Cemento', unidad='bolsa')

    def _payload(self, detalle):
        """Reemplaza todos los ítems de la nota por uno solo con ``detalle``."""
        existentes = list(self.nota_ana.items.all())
        data = {
            'obra_nombre': self.nota_ana.obra.nombre,
            'proveedor_nombre': '', 'encargado': '', 'etapa': '',
            'fecha': '2026-03-15', 'solicitante': 'Ana', 'prioridad': 'Media',
            'limite': '', 'vendedor': '', 'creado_por': '', 'para_envio': '',
            'a_retirar': '', 'retira': '', 'observaciones': '',
            'items-TOTAL_FORMS': str(len(existentes) + 1),
            'items-INITIAL_FORMS': str(len(existentes)),
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '11',
        }
        for indice, previo in enumerate(existentes):
            data[f'items-{indice}-id'] = str(previo.pk)
            data[f'items-{indice}-cantidad'] = str(previo.cantidad)
            data[f'items-{indice}-detalle'] = previo.detalle
            data[f'items-{indice}-especificaciones'] = previo.especificaciones
        nuevo = len(existentes)
        data[f'items-{nuevo}-cantidad'] = '7'
        data[f'items-{nuevo}-detalle'] = detalle
        data[f'items-{nuevo}-especificaciones'] = ''
        return data

    def test_resuelve_variantes_de_escritura(self):
        for detalle in ('cemento', 'CEMENTO', '  Cemento ', 'CeMeNtO'):
            with self.subTest(detalle=detalle):
                self.client.post(
                    reverse('pedidos:editar', args=[self.nota_ana.pk]),
                    self._payload(detalle),
                )
                self.nota_ana.refresh_from_db()
                nuevo = self.nota_ana.items.order_by('-id').first()
                self.assertEqual(nuevo.detalle, detalle.strip())
                self.assertEqual(nuevo.material, self.cemento)

    def test_no_resuelve_si_el_material_esta_inactivo(self):
        self.cemento.activo = False
        self.cemento.save(update_fields=['activo'])
        self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            self._payload('cemento'),
        )
        self.nota_ana.refresh_from_db()
        self.assertIsNone(self.nota_ana.items.order_by('-id').first().material)

    def test_deja_sin_catalogar_lo_que_no_existe(self):
        self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            self._payload('ladrillo hueco 12x18'),
        )
        self.nota_ana.refresh_from_db()
        nuevo = self.nota_ana.items.order_by('-id').first()
        self.assertIsNone(nuevo.material)
        self.assertEqual(nuevo.detalle, 'ladrillo hueco 12x18')

    def test_crear_material_reenlaza_lo_pendiente(self):
        """Si el admin cataloga después, el ítem orphan se engancha solo."""
        self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            self._payload('varillas de hierro 10mm'),
        )
        pendiente = self.nota_ana.items.order_by('-id').first()
        self.assertIsNone(pendiente.material)

        self.client.post(reverse('pedidos:materiales'), {
            'nombre': 'Varillas de Hierro 10mm', 'unidad': 'barra',
            'especificacion': '', 'notas': '', 'activo': 'on',
        })
        nuevo = Material.objects.get(clave='varillas de hierro 10mm')
        self.client.post(
            reverse('pedidos:editar', args=[self.nota_ana.pk]),
            self._payload('varillas de hierro 10mm'),
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.material, nuevo)


class FusionDeMaterialesTest(BasePermisosTest):
    """Unificar duplicados es la única forma de juntar 'cemento' y 'cemento 50kg'."""

    def setUp(self):
        self.client.force_login(self.admin)
        self.oficial = material('Cemento 50kg', unidad='bolsa')
        self.duplicado = material('Cemento', unidad='bolsa')

    def test_reasigna_items_y_borra_el_duplicado(self):
        it1 = item(self.nota_ana, 'Cemento', 10)
        it2 = item(self.nota_beto, 'Cemento', 5)

        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': self.oficial.pk,
            'origenes': [str(self.duplicado.pk)],
        })

        self.assertFalse(Material.objects.filter(pk=self.duplicado.pk).exists())
        self.assertTrue(Material.objects.filter(pk=self.oficial.pk).exists())
        for it in (it1, it2):
            it.refresh_from_db()
            self.assertEqual(it.material, self.oficial)

    def test_reasigna_lineas_de_orden(self):
        # Sin esto, borrar el duplicado dejaría la línea huérfana (PROTECT).
        de_orden = linea(orden(), self.duplicado, 8)
        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': self.oficial.pk,
            'origenes': [str(self.duplicado.pk)],
        })
        de_orden.refresh_from_db()
        self.assertEqual(de_orden.material, self.oficial)

    def test_consolida_varias_fuentes_una_sola_vez(self):
        tercero = material('Cemento Portland')
        item(self.nota_ana, 'Cemento', 10)
        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': self.oficial.pk,
            'origenes': [str(self.duplicado.pk), str(tercero.pk)],
        })
        self.assertEqual(Material.objects.count(), 1)
        self.assertEqual(self.nota_ana.items.get().material, self.oficial)

    def test_no_se_fusiona_consigo_mismo(self):
        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': self.oficial.pk,
            'origenes': [str(self.oficial.pk)],
        })
        self.assertEqual(Material.objects.count(), 2)

    def test_exige_destino_y_origenes(self):
        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': '', 'origenes': [str(self.duplicado.pk)],
        })
        self.assertEqual(Material.objects.count(), 2)
        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': str(self.oficial.pk), 'origenes': [],
        })
        self.assertEqual(Material.objects.count(), 2)

    def test_ignora_destino_inexistente(self):
        self.client.post(reverse('pedidos:material_fusionar'), {
            'destino': '999999', 'origenes': [str(self.duplicado.pk)],
        })
        self.assertEqual(Material.objects.count(), 2)

    def test_solicitante_no_fusiona(self):
        self.client.force_login(self.ana)
        self.assertEqual(
            self.client.post(reverse('pedidos:material_fusionar'), {
                'destino': self.oficial.pk, 'origenes': [str(self.duplicado.pk)],
            }).status_code,
            403,
        )
        self.assertEqual(Material.objects.count(), 2)