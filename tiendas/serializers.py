from rest_framework import serializers

from tiendas import services
from tiendas.models import PerfilUsuario, Plan, Tienda, validar_color_hex


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PerfilSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    rol = serializers.CharField(source='rol.codigo', read_only=True)
    tienda = serializers.CharField(source='tienda.slug', read_only=True, default=None)

    class Meta:
        model = PerfilUsuario
        fields = ['id', 'email', 'rol', 'tienda', 'nombres', 'apellido_paterno',
                  'apellido_materno', 'fecha_nacimiento', 'telefono', 'habilitado']
        read_only_fields = fields


class RegistroSerializer(serializers.Serializer):
    """Autoregistro de un cliente (la tienda sale del subdominio)."""
    nombres = serializers.CharField(max_length=100)
    apellido_paterno = serializers.CharField(max_length=60)
    apellido_materno = serializers.CharField(max_length=60, required=False, allow_blank=True, default='')
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    fecha_nacimiento = serializers.DateField(required=False, allow_null=True, default=None)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')


class AdminSerializer(serializers.Serializer):
    """Datos del admin de tienda que se crea junto con la tienda."""
    nombres = serializers.CharField(max_length=100)
    apellido_paterno = serializers.CharField(max_length=60)
    apellido_materno = serializers.CharField(max_length=60, required=False, allow_blank=True, default='')
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TiendaSerializer(serializers.ModelSerializer):
    plan = serializers.SlugRelatedField(slug_field='nombre', queryset=Plan.objects.all())
    # Solo al crear: datos del admin (write_only, no se devuelven).
    admin = AdminSerializer(write_only=True, required=False)

    class Meta:
        model = Tienda
        fields = ['id', 'nombre', 'slug', 'dominio_propio', 'color_primario', 'plan',
                  'habilitado', 'fecha_creacion', 'admin']
        read_only_fields = ['id', 'habilitado', 'fecha_creacion']

    def validate_slug(self, valor):
        for validador in Tienda._meta.get_field('slug').validators:
            validador(valor)
        return valor

    def create(self, datos):
        admin = datos.pop('admin', None)
        if admin is None:
            raise serializers.ValidationError({'admin': 'Al crear una tienda debes indicar su administrador.'})
        tienda, _ = services.crear_tienda_con_admin(admin=admin, **datos)
        return tienda
