"""API del catálogo: lectura PÚBLICA, escritura solo del admin de la tienda."""

from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from catalogo.models import Categoria, Producto
from catalogo.serializers import CategoriaSerializer, ProductoSerializer
from core.api import TenantMixin, es_admin_tienda, tienda_actual
from core.permisos import LecturaPublicaEscrituraAdminTienda


class _CatalogoViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [LecturaPublicaEscrituraAdminTienda]
    modelo = None

    def get_queryset(self):
        consulta = self.modelo.objects.de_tienda(tienda_actual(self.request))
        # El público y los clientes solo ven lo activo; el admin ve todo.
        return consulta if es_admin_tienda(self.request) else consulta.activos()

    def perform_destroy(self, instance):
        instance.dar_de_baja()  # DELETE = baja lógica, nunca borrado real

    @action(detail=True, methods=['post'])
    def reactivar(self, request, pk=None):
        objeto = self.get_object()
        objeto.reactivar()
        return Response(self.get_serializer(objeto).data)


class CategoriaViewSet(_CatalogoViewSet):
    modelo = Categoria
    queryset = Categoria.objects.none()  # solo para Swagger; el real está en get_queryset
    serializer_class = CategoriaSerializer

    def perform_create(self, serializer):
        serializer.save(tienda=tienda_actual(self.request))


class ProductoViewSet(_CatalogoViewSet):
    modelo = Producto
    queryset = Producto.objects.none()  # solo para Swagger; el real está en get_queryset
    serializer_class = ProductoSerializer
    filterset_fields = ['categoria', 'habilitado']
    filter_backends = _CatalogoViewSet.filter_backends + [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre', 'precio', 'stock']

    def get_queryset(self):
        return super().get_queryset().select_related('categoria')

    def perform_create(self, serializer):
        tienda = tienda_actual(self.request)
        if Producto.objects.de_tienda(tienda).activos().count() >= tienda.plan.max_productos:
            raise ValidationError(f'Tu plan {tienda.plan.nombre} permite hasta {tienda.plan.max_productos} productos activos.')
        serializer.save(tienda=tienda)
