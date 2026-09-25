"""
Reglas del carrito y del pago.

Todo lo que toca dinero o stock ocurre ACÁ, en el servidor. El navegador nunca
manda precios ni totales: solo dice "producto X, cantidad N". Si el cálculo
estuviera en JavaScript (como en la plantilla original), cualquiera podría
modificar el precio desde las herramientas del navegador.
"""

from django.db import transaction

from catalogo.models import Producto
from core.errores import ErrorNegocio
from ventas.models import (
    Carrito, EstadoCarrito, EstadoPedido, ItemCarrito, ItemPedido, Pedido,
)


def carrito_abierto(perfil):
    """El carrito abierto del cliente EN SU TIENDA (se crea si no existe).
    Como se busca por (tienda, cliente), cada usuario tiene un carrito
    distinto en cada tienda."""
    carrito, _ = Carrito.objects.get_or_create(
        tienda=perfil.tienda, cliente=perfil, estado=EstadoCarrito.objects.get(codigo='ABIERTO'),
        habilitado=True,
    )
    return carrito


def _producto_vendible(perfil, producto_id):
    # .de_tienda(): un cliente jamás puede agregar un producto de otra tienda
    # aunque adivine su id.
    producto = (
        Producto.objects.de_tienda(perfil.tienda).activos().filter(pk=producto_id).first()
    )
    if producto is None:
        raise ErrorNegocio('El producto no está disponible.')
    return producto


def agregar_producto(perfil, producto_id, cantidad=1):
    producto = _producto_vendible(perfil, producto_id)
    carrito = carrito_abierto(perfil)
    item = ItemCarrito.objects.filter(carrito=carrito, producto=producto).first()

    # Si el ítem estaba dado de baja (lo había quitado), se reinicia en 0.
    actual = item.cantidad if item and item.habilitado else 0
    nueva = actual + cantidad
    if cantidad < 1:
        raise ErrorNegocio('La cantidad debe ser al menos 1.')
    if nueva > producto.stock:
        raise ErrorNegocio(f'Solo quedan {producto.stock} unidades de "{producto.nombre}".')

    if item is None:
        item = ItemCarrito.objects.create(carrito=carrito, producto=producto, cantidad=nueva)
    else:
        item.cantidad = nueva
        item.habilitado = True
        item.fecha_baja = None
        item.save()
    return item


def _item_del_cliente(perfil, item_id):
    item = (
        ItemCarrito.objects.select_related('producto')
        .filter(pk=item_id, carrito__cliente=perfil, carrito__estado__codigo='ABIERTO', habilitado=True)
        .first()
    )
    if item is None:
        raise ErrorNegocio('Ese producto no está en tu carrito.')
    return item


def cambiar_cantidad(perfil, item_id, cantidad):
    item = _item_del_cliente(perfil, item_id)
    if cantidad < 1:
        return quitar_item(perfil, item_id)
    if cantidad > item.producto.stock:
        raise ErrorNegocio(f'Solo quedan {item.producto.stock} unidades de "{item.producto.nombre}".')
    item.cantidad = cantidad
    item.save(update_fields=['cantidad'])
    return item


def quitar_item(perfil, item_id):
    """Quitar del carrito = baja lógica del ítem (no se borra la fila)."""
    item = _item_del_cliente(perfil, item_id)
    item.dar_de_baja()
    return item


@transaction.atomic
def pagar(perfil):
    """Convierte el carrito en un Pedido (pago simulado) y descuenta el stock.

    transaction.atomic + select_for_update: si dos clientes compran el último
    producto al mismo tiempo, el segundo espera y luego ve stock 0 (sin esto
    se podría vender dos veces lo mismo)."""
    carrito = carrito_abierto(perfil)
    items = list(carrito.items.filter(habilitado=True).select_related('producto'))
    if not items:
        raise ErrorNegocio('Tu carrito está vacío.')

    productos = {
        p.id: p for p in Producto.objects.select_for_update().filter(pk__in=[i.producto_id for i in items])
    }
    for item in items:
        producto = productos[item.producto_id]
        if not producto.habilitado:
            raise ErrorNegocio(f'"{producto.nombre}" ya no está disponible.')
        if item.cantidad > producto.stock:
            raise ErrorNegocio(f'Solo quedan {producto.stock} unidades de "{producto.nombre}".')

    pedido = Pedido.objects.create(
        tienda=perfil.tienda, cliente=perfil,
        estado=EstadoPedido.objects.get(codigo=EstadoPedido.PAGADO),
        total=sum(i.cantidad * productos[i.producto_id].precio for i in items),
    )
    for item in items:
        producto = productos[item.producto_id]
        # Se guarda el precio de HOY: si mañana sube, este pedido no cambia.
        ItemPedido.objects.create(
            pedido=pedido, producto=producto, cantidad=item.cantidad,
            precio_unitario=producto.precio,
        )
        producto.stock -= item.cantidad
        producto.save(update_fields=['stock'])

    carrito.estado = EstadoCarrito.objects.get(codigo=EstadoCarrito.CERRADO)
    carrito.save(update_fields=['estado'])
    return pedido


# Transiciones permitidas: un pedido solo avanza, o se cancela antes de entregarse.
TRANSICIONES = {
    'PAGADO': ['ENVIADO', 'CANCELADO'],
    'ENVIADO': ['ENTREGADO', 'CANCELADO'],
    'ENTREGADO': [],
    'CANCELADO': [],
}


@transaction.atomic
def cambiar_estado_pedido(pedido, codigo_nuevo):
    actual = pedido.estado.codigo
    if codigo_nuevo not in TRANSICIONES.get(actual, []):
        raise ErrorNegocio(f'No se puede pasar de {actual} a {codigo_nuevo}.')
    if codigo_nuevo == 'CANCELADO':
        # Cancelar devuelve el stock.
        items = list(pedido.items.all())
        productos = {
            p.id: p for p in Producto.objects.select_for_update().filter(pk__in=[i.producto_id for i in items])
        }
        for item in items:
            producto = productos[item.producto_id]
            producto.stock += item.cantidad
            producto.save(update_fields=['stock'])
    pedido.estado = EstadoPedido.objects.get(codigo=codigo_nuevo)
    pedido.save(update_fields=['estado'])
    return pedido
