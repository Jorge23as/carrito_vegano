"""Vistas web de carrito, pedidos y dashboard de la tienda."""

from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogo.models import UMBRAL_STOCK_BAJO, Producto
from core.errores import ErrorNegocio
from core.permisos import requiere_rol
from core.utils import destino_seguro
from tiendas.models import PerfilUsuario, Rol
from ventas import services
from ventas.models import EstadoPedido, ItemPedido, Pedido


def _volver(request, por_defecto='/carrito/'):
    """Vuelve a la página anterior solo si es de este mismo sitio."""
    return redirect(destino_seguro(request, request.POST.get('next'), por_defecto))


# --- Cliente: carrito -------------------------------------------------------------

@requiere_rol(Rol.CLIENTE)
def ver_carrito(request):
    carrito = services.carrito_abierto(request.perfil)
    return render(request, 'tienda/carrito.html', {
        'items': carrito.items_activos, 'total': carrito.total,
    })


@requiere_rol(Rol.CLIENTE)
@require_POST
def carrito_agregar(request, producto_id):
    try:
        cantidad = int(request.POST.get('cantidad', 1))
        item = services.agregar_producto(request.perfil, producto_id, cantidad)
        messages.success(request, f'"{item.producto.nombre}" agregado al carrito.')
    except (ErrorNegocio, ValueError) as error:
        messages.error(request, str(error) if isinstance(error, ErrorNegocio) else 'Cantidad inválida.')
    return _volver(request, '/')


@requiere_rol(Rol.CLIENTE)
@require_POST
def carrito_cantidad(request, item_id):
    try:
        services.cambiar_cantidad(request.perfil, item_id, int(request.POST.get('cantidad', 1)))
    except (ErrorNegocio, ValueError) as error:
        messages.error(request, str(error) if isinstance(error, ErrorNegocio) else 'Cantidad inválida.')
    return redirect('/carrito/')


@requiere_rol(Rol.CLIENTE)
@require_POST
def carrito_quitar(request, item_id):
    try:
        services.quitar_item(request.perfil, item_id)
    except ErrorNegocio as error:
        messages.error(request, str(error))
    return redirect('/carrito/')


@requiere_rol(Rol.CLIENTE)
@require_POST
def carrito_pagar(request):
    try:
        pedido = services.pagar(request.perfil)
    except ErrorNegocio as error:
        messages.error(request, str(error))
        return redirect('/carrito/')
    messages.success(request, f'¡Pago realizado! Tu pedido es el #{pedido.pk}.')
    return redirect(f'/pedidos/{pedido.pk}/')


# --- Cliente: sus pedidos -----------------------------------------------------------

@requiere_rol(Rol.CLIENTE)
def mis_pedidos(request):
    pedidos = Pedido.objects.de_tienda(request.tienda).activos().filter(cliente=request.perfil).select_related('estado')
    return render(request, 'tienda/pedidos.html', {'pedidos': pedidos})


@requiere_rol(Rol.CLIENTE)
def mi_pedido(request, pk):
    # Filtra por cliente: nadie ve los pedidos de otra persona.
    pedido = get_object_or_404(
        Pedido.objects.de_tienda(request.tienda).filter(cliente=request.perfil).select_related('estado'), pk=pk)
    return render(request, 'tienda/pedido_detalle.html', {
        'pedido': pedido, 'items': pedido.items.select_related('producto'),
    })


# --- Admin de tienda: dashboard y pedidos ---------------------------------------------

@requiere_rol(Rol.ADMIN_TIENDA)
def panel_dashboard(request):
    tienda = request.tienda
    pedidos = Pedido.objects.de_tienda(tienda).activos().exclude(estado__codigo='CANCELADO')
    vendidos = ItemPedido.objects.filter(pedido__in=pedidos)

    return render(request, 'panel/dashboard.html', {
        'seccion': 'dashboard',
        'ventas_total': pedidos.aggregate(s=Sum('total'))['s'] or 0,
        'n_pedidos': pedidos.count(),
        'n_por_enviar': Pedido.objects.de_tienda(tienda).filter(estado__codigo='PAGADO').count(),
        'n_clientes': PerfilUsuario.objects.de_tienda(tienda).filter(rol__codigo=Rol.CLIENTE, habilitado=True).count(),
        'top_producto': (vendidos.values('producto__nombre').annotate(u=Sum('cantidad')).order_by('-u').first()),
        'top_categoria': (vendidos.values('producto__categoria__nombre').annotate(u=Sum('cantidad')).order_by('-u').first()),
        'quiebre': Producto.objects.de_tienda(tienda).activos().filter(stock__lte=UMBRAL_STOCK_BAJO).order_by('stock'),
        'umbral': UMBRAL_STOCK_BAJO,
        'recientes': Pedido.objects.de_tienda(tienda).select_related('cliente', 'estado')[:5],
        'por_estado': (Pedido.objects.de_tienda(tienda).values('estado__nombre').annotate(n=Count('id'))),
    })


@requiere_rol(Rol.ADMIN_TIENDA)
def panel_pedidos(request):
    pedidos = Pedido.objects.de_tienda(request.tienda).select_related('cliente', 'estado')
    return render(request, 'panel/pedidos.html', {'pedidos': pedidos, 'seccion': 'pedidos'})


@requiere_rol(Rol.ADMIN_TIENDA)
def panel_pedido(request, pk):
    pedido = get_object_or_404(Pedido.objects.de_tienda(request.tienda).select_related('cliente', 'estado'), pk=pk)
    siguientes = EstadoPedido.objects.filter(codigo__in=services.TRANSICIONES[pedido.estado.codigo])
    return render(request, 'panel/pedido_detalle.html', {
        'pedido': pedido, 'items': pedido.items.select_related('producto'),
        'siguientes': siguientes, 'seccion': 'pedidos',
    })


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def panel_pedido_estado(request, pk):
    pedido = get_object_or_404(Pedido.objects.de_tienda(request.tienda).select_related('estado'), pk=pk)
    try:
        services.cambiar_estado_pedido(pedido, request.POST.get('estado', ''))
        messages.success(request, f'Pedido #{pedido.pk} actualizado.')
    except ErrorNegocio as error:
        messages.error(request, str(error))
    return redirect(f'/panel/pedidos/{pedido.pk}/')
