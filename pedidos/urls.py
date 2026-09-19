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
    path('<int:pk>/descargar/', views.descargar, name='descargar'),
    path('descargar/todas/', views.descargar_todas, name='descargar_todas'),

    path('obras/', views.obras, name='obras'),
    path('obras/<int:pk>/editar/', views.obra_editar, name='obra_editar'),
    path('obras/<int:pk>/borrar/', views.obra_borrar, name='obra_borrar'),

    path('proveedores/', views.proveedores, name='proveedores'),
    path('proveedores/<int:pk>/editar/', views.proveedor_editar, name='proveedor_editar'),
    path('proveedores/<int:pk>/borrar/', views.proveedor_borrar, name='proveedor_borrar'),
]