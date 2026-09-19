from django.conf import settings
from django.db import models
from django.urls import reverse


class Obra(models.Model):
    nombre = models.CharField('Obra', max_length=200)
    direccion = models.CharField('Dirección', max_length=200, blank=True)
    activa = models.BooleanField('Activa', default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Obra'
        verbose_name_plural = 'Obras'

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField('Nombre', max_length=200)
    ruc = models.CharField('RUC', max_length=40, blank=True)
    direccion = models.CharField('Dirección', max_length=200, blank=True)
    telefono = models.CharField('Teléfono', max_length=60, blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        return self.nombre


class NotaPedido(models.Model):
    numero = models.PositiveIntegerField('N.P. N°', unique=True, editable=False)
    obra = models.ForeignKey(
        Obra, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notas', verbose_name='Obra',
    )
    encargado = models.CharField('Encargado', max_length=200, blank=True)
    etapa = models.CharField('Etapa', max_length=200, blank=True)
    fecha = models.DateField('Fecha')
    solicitante = models.CharField('Solicitante', max_length=200)
    prioridad = models.CharField('Prioridad', max_length=50, blank=True, default='Media')
    limite = models.DateField('Límite', null=True, blank=True)

    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notas', verbose_name='Proveedor',
    )
    vendedor = models.CharField('Vendedor/a', max_length=200, blank=True)

    observaciones = models.TextField('Observaciones', blank=True)
    para_envio = models.BooleanField('Para Envío', default=False)
    a_retirar = models.BooleanField('A retirar', default=False)
    retira = models.CharField('Retira', max_length=200, blank=True)

    estado = models.CharField(
        'Estado', max_length=20, choices=settings.ESTADOS_NOTA, default='pendiente',
    )
    aprobado_por = models.CharField('Aprobado por', max_length=200, blank=True)

    creado_por = models.CharField('Creado por', max_length=200, blank=True)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)

    class Meta:
        ordering = ['-numero']
        verbose_name = 'Nota de Pedido'
        verbose_name_plural = 'Notas de Pedido'

    def __str__(self):
        return f'NP N° {self.numero}'

    def get_absolute_url(self):
        return reverse('pedidos:detalle', args=[self.pk])

    def __getitem__(self, key):
        if key == 'numero':
            return self.numero
        raise KeyError(key)


class ItemNotaPedido(models.Model):
    nota = models.ForeignKey(
        NotaPedido, on_delete=models.CASCADE, related_name='items',
        verbose_name='Nota de pedido',
    )
    stock = models.PositiveIntegerField('Stock', blank=True, null=True, default=0)
    cantidad = models.DecimalField('Cant.', max_digits=12, decimal_places=2, blank=True, null=True)
    detalle = models.CharField('Detalle de las mercaderías', max_length=300)
    especificaciones = models.CharField('Especificaciones/Medidas', max_length=300, blank=True)
    estado = models.CharField('Estado', max_length=100, blank=True)
    precio = models.DecimalField('Precios', max_digits=15, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Ítem'
        verbose_name_plural = 'Ítems'

    def __str__(self):
        return self.detalle