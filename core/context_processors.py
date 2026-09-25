"""Variables disponibles en TODOS los templates (sin pasarlas en cada vista)."""

from django.conf import settings
from django.db.models import Sum

from tiendas.models import Rol

COLOR_POR_DEFECTO = '#1B4332'


def global_ctx(request):
    tienda = getattr(request, 'tienda', None)
    perfil = getattr(request, 'perfil', None)

    cantidad_carrito = 0
    if perfil and perfil.rol.codigo == Rol.CLIENTE:
        from ventas.models import ItemCarrito
        cantidad_carrito = ItemCarrito.objects.filter(
            carrito__cliente=perfil, carrito__estado__codigo='ABIERTO', habilitado=True,
        ).aggregate(n=Sum('cantidad'))['n'] or 0

    return {
        'tienda': tienda,
        'perfil': perfil,
        'color_primario': tienda.color_primario if tienda else COLOR_POR_DEFECTO,
        'nombre_sitio': tienda.nombre if tienda else settings.PLATAFORMA_NOMBRE,
        'cantidad_carrito': cantidad_carrito,
        'ROL_ADMIN_GENERAL': Rol.ADMIN_GENERAL,
        'ROL_ADMIN_TIENDA': Rol.ADMIN_TIENDA,
        'ROL_CLIENTE': Rol.CLIENTE,
    }
