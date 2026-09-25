from django.urls import path

from catalogo import views

urlpatterns = [
    path('producto/<int:pk>/', views.producto_detalle),
    path('panel/productos/', views.panel_productos),
    path('panel/productos/nuevo/', views.producto_nuevo),
    path('panel/productos/<int:pk>/editar/', views.producto_editar),
    path('panel/productos/<int:pk>/baja/', views.producto_baja),
    path('panel/productos/<int:pk>/reactivar/', views.producto_reactivar),
    path('panel/categorias/', views.panel_categorias),
    path('panel/categorias/nueva/', views.categoria_nueva),
    path('panel/categorias/<int:pk>/editar/', views.categoria_editar),
    path('panel/categorias/<int:pk>/baja/', views.categoria_baja),
    path('panel/categorias/<int:pk>/reactivar/', views.categoria_reactivar),
]
