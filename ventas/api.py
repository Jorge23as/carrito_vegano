"""API del carrito y de los pedidos."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from core.api import tienda_actual
from core.permisos import rol_api
from tiendas.models import Rol
from ventas import services
from ventas.models import Pedido
from ventas.serializers import (
    AgregarAlCarritoSerializer, CambiarEstadoSerializer, CantidadSerializer,
    CarritoSerializer, ItemCarritoSerializer, PedidoSerializer,
)


def _perfil(request):
    return request._request.perfil


class CarritoAPIView(GenericAPIView):
    """Mi carrito en esta tienda."""
    serializer_class = CarritoSerializer
    permission_classes = [rol_api(Rol.CLIENTE)]

    def get(self, request):
        return Response(CarritoSerializer(services.carrito_abierto(_perfil(request))).data)


class CarritoItemsAPIView(GenericAPIView):
    serializer_class = AgregarAlCarritoSerializer
    permission_classes = [rol_api(Rol.CLIENTE)]

    def post(self, request):
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        item = services.agregar_producto(_perfil(request), datos.validated_data['producto'],
                                         datos.validated_data['cantidad'])
        return Response(ItemCarritoSerializer(item).data, status=201)


class CarritoItemDetalleAPIView(GenericAPIView):
    serializer_class = CantidadSerializer
    permission_classes = [rol_api(Rol.CLIENTE)]

    def patch(self, request, item_id):
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        item = services.cambiar_cantidad(_perfil(request), item_id, datos.validated_data['cantidad'])
        return Response(ItemCarritoSerializer(item).data)

    def delete(self, request, item_id):
        services.quitar_item(_perfil(request), item_id)  # baja lógica del ítem
        return Response(status=204)


class PagarAPIView(GenericAPIView):
    serializer_class = PedidoSerializer
    permission_classes = [rol_api(Rol.CLIENTE)]

    def post(self, request):
        pedido = services.pagar(_perfil(request))
        return Response(PedidoSerializer(pedido).data, status=201)


class PedidoViewSet(viewsets.ReadOnlyModelViewSet):
    """El cliente ve SOLO sus pedidos; el admin de tienda ve todos los de su tienda."""
    serializer_class = PedidoSerializer
    queryset = Pedido.objects.none()  # solo para Swagger; el real está en get_queryset
    permission_classes = [rol_api(Rol.CLIENTE, Rol.ADMIN_TIENDA)]
    filterset_fields = ['estado__codigo']

    def get_queryset(self):
        perfil = _perfil(self.request)
        consulta = Pedido.objects.de_tienda(tienda_actual(self.request)).select_related('estado', 'cliente')
        if perfil.rol.codigo == Rol.CLIENTE:
            consulta = consulta.filter(cliente=perfil)
        return consulta.prefetch_related('items__producto')

    @action(detail=True, methods=['post'], permission_classes=[rol_api(Rol.ADMIN_TIENDA)],
            serializer_class=CambiarEstadoSerializer)
    def estado(self, request, pk=None):
        datos = CambiarEstadoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        pedido = services.cambiar_estado_pedido(self.get_object(), datos.validated_data['estado'])
        return Response(PedidoSerializer(pedido).data)
