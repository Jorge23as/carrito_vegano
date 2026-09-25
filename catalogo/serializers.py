from rest_framework import serializers

from catalogo.models import Categoria, Producto
from core.imagenes import optimizar


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'habilitado']
        read_only_fields = ['id', 'habilitado']

    def validate_nombre(self, nombre):
        nombre = nombre.strip()
        repetida = Categoria.objects.de_tienda(self.context['tienda']).filter(nombre__iexact=nombre)
        if self.instance:
            repetida = repetida.exclude(pk=self.instance.pk)
        if repetida.exists():
            raise serializers.ValidationError('Ya existe una categoría con ese nombre.')
        return nombre


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = Producto
        fields = ['id', 'categoria', 'categoria_nombre', 'nombre', 'descripcion',
                  'precio', 'stock', 'imagen', 'habilitado']
        read_only_fields = ['id', 'habilitado']

    def validate_categoria(self, categoria):
        # Una categoría de otra tienda (o dada de baja) no es válida.
        if categoria.tienda_id != self.context['tienda'].id or not categoria.habilitado:
            raise serializers.ValidationError('Categoría inválida.')
        return categoria

    def validate_precio(self, precio):
        if precio < 1:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return precio

    def validate_imagen(self, imagen):
        return optimizar(imagen) if imagen else imagen
