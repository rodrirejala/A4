from django.contrib import admin

from .models import ItemNotaPedido, NotaPedido, Obra, Proveedor


class ItemInline(admin.TabularInline):
    model = ItemNotaPedido
    extra = 1


@admin.register(NotaPedido)
class NotaPedidoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'fecha', 'obra', 'solicitante', 'proveedor', 'estado']
    list_filter = ['estado', 'prioridad', 'fecha']
    search_fields = ['numero', 'solicitante', 'obra__nombre', 'proveedor__nombre']
    inlines = [ItemInline]
    readonly_fields = ['creado_por']


admin.site.register([Obra, Proveedor])