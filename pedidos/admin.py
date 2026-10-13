from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from .models import (
    ItemNotaPedido, Material, NotaPedido, Obra, OrdenCompra, OrdenCompraLinea, Proveedor,
)
from .roles import GRUPO_ADMINISTRADOR


class ItemInline(admin.TabularInline):
    model = ItemNotaPedido
    extra = 1
    autocomplete_fields = ['material']


@admin.register(NotaPedido)
class NotaPedidoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'fecha', 'obra', 'solicitante', 'proveedor', 'estado', 'autor']
    list_filter = ['estado', 'prioridad', 'fecha']
    search_fields = ['numero', 'solicitante', 'creado_por', 'obra__nombre', 'proveedor__nombre', 'usuario__username']
    inlines = [ItemInline]
    readonly_fields = ['creado_por', 'usuario', 'created_at', 'updated_at']
    autocomplete_fields = ['obra', 'proveedor']

    @admin.display(description='Usuario', ordering='usuario__username')
    def autor(self, obj):
        return obj.autor


@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'direccion', 'activa']
    list_filter = ['activa']
    search_fields = ['nombre', 'direccion']


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'ruc', 'telefono']
    search_fields = ['nombre', 'ruc']


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'clave', 'unidad', 'activo', 'usos']
    list_filter = ['activo']
    search_fields = ['nombre', 'clave', 'especificacion']
    readonly_fields = ['clave']

    @admin.display(description='Ítems enlazados')
    def usos(self, obj):
        return obj.items.count()


class LineaOrdenInline(admin.TabularInline):
    model = OrdenCompraLinea
    extra = 0
    autocomplete_fields = ['material']


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = [
        'numero', 'proveedor', 'fecha', 'total', 'lineas', 'notas',
        'anulada', 'creado_por',
    ]
    list_filter = ['anulada', 'fecha']
    search_fields = ['numero', 'proveedor__nombre', 'observaciones']
    autocomplete_fields = ['proveedor']
    inlines = [LineaOrdenInline]
    readonly_fields = ['numero', 'creado_por', 'created_at']
    filter_horizontal = ['notas']

    @admin.display(description='Líneas')
    def lineas(self, obj):
        return obj.lineas.count()

    @admin.display(description='Notas')
    def notas(self, obj):
        return obj.notas.count()

    @admin.display(description='Total')
    def total(self, obj):
        return f'{obj.total:,.2f}'


class UserAdminConRoles(UserAdmin):
    """Suma los roles de la app al panel de usuarios de Django."""

    list_display = ['username', 'first_name', 'last_name', 'email', 'es_admin', 'is_active']

    @admin.display(boolean=True, description='Administrador')
    def es_admin(self, obj):
        return obj.is_superuser or obj.groups.filter(name=GRUPO_ADMINISTRADOR).exists()

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('groups')


admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)
admin.site.unregister(User)
admin.site.register(User, UserAdminConRoles)