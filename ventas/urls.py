from django.urls import path

from ventas import views

urlpatterns = [
    path('carrito/', views.ver_carrito),
    path('carrito/agregar/<int:producto_id>/', views.carrito_agregar),
    path('carrito/item/<int:item_id>/cantidad/', views.carrito_cantidad),
    path('carrito/item/<int:item_id>/quitar/', views.carrito_quitar),
    path('carrito/pagar/', views.carrito_pagar),
    path('pedidos/', views.mis_pedidos),
    path('pedidos/<int:pk>/', views.mi_pedido),
    path('panel/', views.panel_dashboard),
    path('panel/pedidos/', views.panel_pedidos),
    path('panel/pedidos/<int:pk>/', views.panel_pedido),
    path('panel/pedidos/<int:pk>/estado/', views.panel_pedido_estado),
]
