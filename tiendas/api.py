"""Endpoints de la API para autenticación, clientes y tiendas."""

from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.api import TenantMixin, tienda_actual
from core.auth import (
    borrar_cookies, emitir_tokens, invalidar_refresh, limpiar_fallos,
    login_bloqueado, poner_cookies, registrar_fallo,
)
from core.errores import ErrorNegocio
from core.permisos import rol_api
from tiendas import services
from tiendas.models import PerfilUsuario, Rol, Tienda
from tiendas.serializers import (
    AdminSerializer, LoginSerializer, PerfilSerializer, RegistroSerializer,
    TiendaSerializer,
)


class LoginAPIView(GenericAPIView):
    """Inicia sesión: guarda los JWT en cookies HttpOnly (no en el cuerpo)."""
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # al loguearse aún no hay sesión que validar

    def post(self, request):
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        host, email = request.get_host(), datos.validated_data['email']
        if login_bloqueado(host, email):
            return Response({'error': 'Demasiados intentos fallidos. Espera 5 minutos.'}, status=429)
        try:
            _, perfil = services.autenticar_credenciales(
                request._request.tienda, email, datos.validated_data['password'])
        except ErrorNegocio as error:
            registrar_fallo(host, email)
            return Response({'error': str(error)}, status=401)
        limpiar_fallos(host, email)
        respuesta = Response(PerfilSerializer(perfil).data)
        access, refresh = emitir_tokens(perfil)
        poner_cookies(respuesta, access, refresh)
        return respuesta


class LogoutAPIView(GenericAPIView):
    serializer_class = serializers.Serializer  # no recibe datos
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        invalidar_refresh(request)
        respuesta = Response({'detalle': 'Sesión cerrada.'})
        borrar_cookies(respuesta)
        return respuesta


class RegistroAPIView(GenericAPIView):
    """Autoregistro de cliente con permisos mínimos."""
    serializer_class = RegistroSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        tienda = tienda_actual(request)
        datos = self.get_serializer(data=request.data)
        datos.is_valid(raise_exception=True)
        perfil = services.registrar_cliente(tienda, **datos.validated_data)
        respuesta = Response(PerfilSerializer(perfil).data, status=201)
        access, refresh = emitir_tokens(perfil)
        poner_cookies(respuesta, access, refresh)
        return respuesta


class YoAPIView(GenericAPIView):
    serializer_class = PerfilSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PerfilSerializer(request._request.perfil).data)


class ClienteViewSet(TenantMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Clientes de la tienda. PROTEGIDO: solo el admin de esa tienda (datos personales)."""
    serializer_class = PerfilSerializer
    queryset = PerfilUsuario.objects.none()  # solo para Swagger; el real está en get_queryset
    permission_classes = [rol_api(Rol.ADMIN_TIENDA)]
    filterset_fields = ['habilitado']

    def get_queryset(self):
        return (PerfilUsuario.objects.de_tienda(tienda_actual(self.request))
                .filter(rol__codigo=Rol.CLIENTE).select_related('user', 'rol', 'tienda').order_by('id'))

    @action(detail=True, methods=['post'])
    def baja(self, request, pk=None):
        cliente = self.get_object()
        cliente.dar_de_baja()
        return Response(PerfilSerializer(cliente).data)

    @action(detail=True, methods=['post'])
    def reactivar(self, request, pk=None):
        cliente = self.get_object()
        cliente.reactivar()
        return Response(PerfilSerializer(cliente).data)


class TiendaViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Gestión de tiendas: SOLO el admin general (y solo desde la plataforma)."""
    queryset = Tienda.objects.select_related('plan').order_by('id')
    serializer_class = TiendaSerializer
    permission_classes = [rol_api(Rol.ADMIN_GENERAL)]

    def perform_destroy(self, instance):
        instance.dar_de_baja()  # DELETE = baja lógica, nunca borrado real

    @action(detail=True, methods=['post'])
    def reactivar(self, request, pk=None):
        tienda = self.get_object()
        tienda.reactivar()
        return Response(TiendaSerializer(tienda).data)

    @action(detail=True, methods=['post'], url_path='reasignar-admin', serializer_class=AdminSerializer)
    def reasignar_admin(self, request, pk=None):
        datos = AdminSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        perfil = services.reasignar_admin_tienda(self.get_object(), **datos.validated_data)
        return Response(PerfilSerializer(perfil).data, status=201)
