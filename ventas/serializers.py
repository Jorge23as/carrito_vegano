from rest_framework import serializers

from ventas.models import Carrito, ItemCarrito, ItemPedido, Pedido


class AgregarAlCarritoSerializer(serializers.Serializer):
    producto = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1, default=1)


class CantidadSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=0)


class ItemCarritoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    precio = serializers.IntegerField(source='producto.precio', read_only=True)
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemCarrito
        fields = ['id', 'producto', 'producto_nombre', 'precio', 'cantidad', 'subtotal']


class CarritoSerializer(serializers.ModelSerializer):
    items = ItemCarritoSerializer(source='items_activos', many=True, read_only=True)
    total = serializers.IntegerField(read_only=True)

    class Meta:
        model = Carrito
        fields = ['id', 'items', 'total']


class ItemPedidoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemPedido
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_unitario', 'subtotal']


class PedidoSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(source='estado.codigo', read_only=True)
    cliente = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    items = ItemPedidoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = ['id', 'cliente', 'estado', 'total', 'fecha', 'items']


class CambiarEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=['ENVIADO', 'ENTREGADO', 'CANCELADO'])
