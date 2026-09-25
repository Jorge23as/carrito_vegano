from django.contrib import admin

from ventas.models import Carrito, EstadoCarrito, EstadoPedido, ItemCarrito, ItemPedido, Pedido

admin.site.register([EstadoCarrito, EstadoPedido, Carrito, ItemCarrito, Pedido, ItemPedido])
