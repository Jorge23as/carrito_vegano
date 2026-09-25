"""Todas las rutas de la API REST, bajo /api/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalogo.api import CategoriaViewSet, ProductoViewSet
from tiendas.api import (
    ClienteViewSet, LoginAPIView, LogoutAPIView, RegistroAPIView, TiendaViewSet, YoAPIView,
)
from ventas.api import (
    CarritoAPIView, CarritoItemDetalleAPIView, CarritoItemsAPIView, PagarAPIView, PedidoViewSet,
)

# El router genera solo las rutas de lista/detalle de cada ViewSet.
router = DefaultRouter()
router.register('productos', ProductoViewSet, basename='producto')
router.register('categorias', CategoriaViewSet, basename='categoria')
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('tiendas', TiendaViewSet, basename='tienda')
router.register('pedidos', PedidoViewSet, basename='pedido')

urlpatterns = [
    path('auth/login/', LoginAPIView.as_view()),
    path('auth/logout/', LogoutAPIView.as_view()),
    path('auth/registro/', RegistroAPIView.as_view()),
    path('auth/yo/', YoAPIView.as_view()),
    path('carrito/', CarritoAPIView.as_view()),
    path('carrito/items/', CarritoItemsAPIView.as_view()),
    path('carrito/items/<int:item_id>/', CarritoItemDetalleAPIView.as_view()),
    path('carrito/pagar/', PagarAPIView.as_view()),
    path('', include(router.urls)),
]
