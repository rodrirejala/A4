"""Asignación del N.P. N° y autorización del autor."""

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from pedidos.models import NotaPedido

from .base import BasePermisosTest, payload_nota


class NumeracionTest(BasePermisosTest):
    def test_asigna_el_siguiente_numero(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('pedidos:nueva'), payload_nota())

        nota = NotaPedido.objects.order_by('-id').first()
        self.assertEqual(nota.numero, 4)

    def test_reintenta_ante_colision_de_numero(self):
        """Si el número ya fue tomado, el savepoint permite reintentar sin fallar."""
        import pedidos.views as views

        # El 1° intento devuelve un número YA usado (colisión garantizada),
        # el 2° devuelve el siguiente libre.
        intentos = [1, 4]
        original = views._siguiente_numero
        views._siguiente_numero = lambda: intentos.pop(0)
        try:
            self.client.force_login(self.admin)
            response = self.client.post(reverse('pedidos:nueva'), payload_nota())
        finally:
            views._siguiente_numero = original

        self.assertEqual(response.status_code, 302)
        self.assertEqual(intentos, [], 'no se agotaron los reintentos')

        nota = NotaPedido.objects.order_by('-id').first()
        self.assertEqual(nota.numero, 4)

    def test_no_deja_intentos_pendientes_si_falla_siempre(self):
        """Si la colisión persiste, el error sube (no se cuelga en loop)."""
        import pedidos.views as views

        original = views._siguiente_numero
        views._siguiente_numero = lambda: 1  # siempre colisiona
        try:
            self.client.force_login(self.admin)
            with self.assertRaises(IntegrityError):
                self.client.post(reverse('pedidos:nueva'), payload_nota())
        finally:
            views._siguiente_numero = original

    def test_registra_el_usuario_autenticado_como_autor(self):
        self.client.force_login(self.beto)
        self.client.post(reverse('pedidos:nueva'), payload_nota())

        nota = NotaPedido.objects.order_by('-id').first()
        self.assertEqual(nota.usuario, self.beto)
        self.assertEqual(nota.autor, 'beto')

    def test_autor_usa_el_nombre_completo_cuando_esta(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('pedidos:nueva'), payload_nota())

        nota = NotaPedido.objects.order_by('-id').first()
        self.assertEqual(nota.autor, 'Jefe Compras')

    def test_autor_fallback_al_texto_historico(self):
        self.assertEqual(self.nota_huerfana.autor, '')
        self.nota_huerfana.creado_por = 'Legacy'
        self.nota_huerfana.save()
        self.assertEqual(self.nota_huerfana.autor, 'Legacy')