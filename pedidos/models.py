from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from .roles import es_admin
from .textos import normalizar

# Clase de Bootstrap para la insignia del estado, usada en el panel y el detalle.
CLASES_ESTADO = {
    'pendiente': 'warning',
    'aprobada': 'success',
    'cerrado': 'secondary',
}


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


class Material(models.Model):
    """Catálogo maestro de materiales.

    El consolidado de compras agrupa por este modelo y no por el texto libre
    del ítem: es la única forma de que "CEMENTO", "  cemento " y "Cemento"
    cuenten como un mismo material. ``clave`` es la forma normalizada de
    ``nombre`` y es única, por lo que al guardar se recalcula en ``save()``.
    """

    nombre = models.CharField('Material', max_length=200)
    clave = models.CharField('Clave', max_length=200, unique=True, editable=False)
    unidad = models.CharField('Unidad', max_length=20, blank=True)
    especificacion = models.CharField('Especificación', max_length=300, blank=True)
    activo = models.BooleanField('Activo', default=True)
    notas = models.CharField('Notas', max_length=300, blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Material'
        verbose_name_plural = 'Materiales'

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.clave = normalizar(self.nombre)
        # La clave es única y se deriva del nombre; conviene avisar con un error
        # claro en vez de dejar que reviente el UNIQUE de la base.
        choque = Material.objects.filter(clave=self.clave)
        if self.pk:
            choque = choque.exclude(pk=self.pk)
        if choque.exists():
            raise ValidationError({
                'nombre': f'Ya existe el material "{choque.first().nombre}" con el mismo '
                          f'nombre (sin tildes ni mayúsculas). Editá ese en lugar de crear otro.',
            })
        super().save(*args, **kwargs)


class NotaPedidoQuerySet(models.QuerySet):
    def con_relaciones(self):
        return self.select_related('obra', 'proveedor', 'usuario')

    def visibles_para(self, user):
        """Notas que el usuario puede ver: todas si es admin, solo las suyas si no."""
        return self.con_relaciones() if es_admin(user) else self.con_relaciones().filter(usuario=user)

    def para_exportar(self):
        """Evita N+1 al generar el Excel/ZIP (items y relaciones)."""
        return self.con_relaciones().prefetch_related('items')


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
    cerrado_por = models.CharField('Cerrado por', max_length=200, blank=True)

    creado_por = models.CharField('Creado por', max_length=200, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notas_creadas', verbose_name='Usuario',
    )
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)

    objects = NotaPedidoQuerySet.as_manager()

    class Meta:
        ordering = ['-numero']
        verbose_name = 'Nota de Pedido'
        verbose_name_plural = 'Notas de Pedido'

    def __str__(self):
        return f'NP N° {self.numero}'

    def get_absolute_url(self):
        return reverse('pedidos:detalle', args=[self.pk])

    def registrar_autor(self, user):
        """Asigna el usuario autenticado y su nombre legible a ``creado_por``."""
        self.usuario = user
        if user is not None and getattr(user, 'is_authenticated', False):
            self.creado_por = user.get_full_name() or user.get_username()
        return self

    @property
    def autor(self):
        """Nombre del usuario que creó la nota, con fallback al texto histórico."""
        if self.usuario_id:
            return self.usuario.get_full_name() or self.usuario.get_username()
        return self.creado_por

    @property
    def clase_estado(self):
        """Sufijo de Bootstrap para la insignia del estado."""
        return CLASES_ESTADO.get(self.estado, 'secondary')

    @property
    def esta_cerrada(self):
        return self.estado == 'cerrado'


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
    material = models.ForeignKey(
        Material, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items', verbose_name='Material del catálogo',
        help_text='Se resuelve automáticamente al guardar según el detalle.',
    )

    class Meta:
        ordering = ['id']
        verbose_name = 'Ítem'
        verbose_name_plural = 'Ítems'

    def __str__(self):
        return self.detalle

    @property
    def nombre_material(self):
        """Nombre del material catalogado, con fallback al texto libre."""
        return self.material.nombre if self.material_id else self.detalle


class OrdenCompraQuerySet(models.QuerySet):
    def vigentes(self):
        """Órdenes no anuladas (las anuladas se consideran deshechas)."""
        return self.filter(anulada=False)


class OrdenCompra(models.Model):
    """Pedido que se le manda a un proveedor, armado desde el consolidado.

    Nace de la necesidad de comprar: el administrador tilda los materiales del
    consolidado que quiere pedirle a un mismo proveedor y el sistema agrupa las
    notas de origen en esta orden. ``notas`` es M2M (y no OneToOne) porque una
    nota puede tener materiales para dos proveedores distintos.
    """

    numero = models.PositiveIntegerField('O.C. N°', unique=True, editable=False)
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT, related_name='ordenes_compra',
        verbose_name='Proveedor',
    )
    fecha = models.DateField('Fecha')
    observaciones = models.TextField('Observaciones', blank=True)
    anulada = models.BooleanField('Anulada', default=False)

    notas = models.ManyToManyField(
        NotaPedido, related_name='ordenes_compra', blank=True,
        verbose_name='Notas de origen',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordenes_compra_creadas', verbose_name='Creado por',
    )
    created_at = models.DateTimeField('Creado', auto_now_add=True)

    objects = OrdenCompraQuerySet.as_manager()

    class Meta:
        ordering = ['-numero']
        verbose_name = 'Orden de Compra'
        verbose_name_plural = 'Órdenes de Compra'

    def __str__(self):
        return f'OC N° {self.numero:04d} - {self.proveedor}'

    def get_absolute_url(self):
        return reverse('pedidos:orden_detalle', args=[self.pk])

    @property
    def estado(self):
        return 'Anulada' if self.anulada else 'Vigente'

    @property
    def total(self):
        """Suma de los subtotales de las líneas."""
        return sum((linea.total for linea in self.lineas.all()), Decimal('0'))


class OrdenCompraLinea(models.Model):
    orden = models.ForeignKey(
        OrdenCompra, on_delete=models.CASCADE, related_name='lineas',
        verbose_name='Orden de compra',
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name='lineas_orden',
        verbose_name='Material',
    )
    cantidad = models.DecimalField('Cantidad', max_digits=12, decimal_places=2)
    especificacion = models.CharField('Especificación', max_length=300, blank=True)
    precio = models.DecimalField(
        'Precio unitario', max_digits=15, decimal_places=2, blank=True, null=True,
    )

    class Meta:
        ordering = ['id']
        verbose_name = 'Línea de orden de compra'
        verbose_name_plural = 'Líneas de orden de compra'

    def __str__(self):
        return f'{self.material} x {self.cantidad}'

    @property
    def total(self):
        if self.precio is None:
            return None
        return self.cantidad * self.precio