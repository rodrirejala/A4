from django.urls import path

from . import views

app_name = 'pedidos'

urlpatterns = [
    path('', views.panel, name='panel'),
    path('nueva/', views.nueva, name='nueva'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/borrar/', views.borrar, name='borrar'),
    path('<int:pk>/aprobar/', views.aprobar, name='aprobar'),
    path('<int:pk>/cerrar/', views.cerrar, name='cerrar'),
    path('<int:pk>/descargar/', views.descargar, name='descargar'),
    path('descargar/todas/', views.descargar_todas, name='descargar_todas'),

    path('materiales/', views.materiales, name='materiales'),
    path('materiales/fusionar/', views.material_fusionar, name='material_fusionar'),
    path('materiales/<int:pk>/editar/', views.material_editar, name='material_editar'),
    path('materiales/<int:pk>/borrar/', views.material_borrar, name='material_borrar'),

    path('compras/', views.compras, name='compras'),
    path('compras/crear/', views.compras_crear_orden, name='compras_crear_orden'),
    path('compras/<int:pk>/', views.orden_detalle, name='orden_detalle'),
    path('compras/<int:pk>/anular/', views.orden_anular, name='orden_anular'),
    path('compras/<int:pk>/descargar/', views.orden_descargar, name='orden_descargar'),

    path('obras/', views.obras, name='obras'),
    path('obras/<int:pk>/editar/', views.obra_editar, name='obra_editar'),
    path('obras/<int:pk>/borrar/', views.obra_borrar, name='obra_borrar'),

    path('proveedores/', views.proveedores, name='proveedores'),
    path('proveedores/<int:pk>/editar/', views.proveedor_editar, name='proveedor_editar'),
    path('proveedores/<int:pk>/borrar/', views.proveedor_borrar, name='proveedor_borrar'),

    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/nuevo/', views.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views.usuario_editar, name='usuario_editar'),
    path('usuarios/<int:pk>/borrar/', views.usuario_borrar, name='usuario_borrar'),
]