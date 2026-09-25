from django import forms
from django.contrib.auth.password_validation import validate_password

from core.forms import Formulario, FormularioModelo
from core.imagenes import optimizar
from tiendas.models import Plan, Tienda, validar_color_hex


class LoginForm(Formulario):
    email = forms.EmailField(label='Correo electrónico', widget=forms.EmailInput(attrs={'placeholder': 'tu@correo.com'}))
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput)


class DatosPersonalesForm(Formulario):
    """Campos de una persona, con nombres separados (3FN)."""

    nombres = forms.CharField(max_length=100)
    apellido_paterno = forms.CharField(max_length=60)
    apellido_materno = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(label='Correo electrónico')
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput)

    def clean_password(self):
        # Aplica los validadores de AUTH_PASSWORD_VALIDATORS (largo, común, numérica...).
        clave = self.cleaned_data['password']
        validate_password(clave)
        return clave

    def datos_admin(self):
        """Los datos como los espera services.crear_usuario_perfil."""
        d = self.cleaned_data
        return {
            'nombres': d['nombres'], 'apellido_paterno': d['apellido_paterno'],
            'apellido_materno': d.get('apellido_materno', ''), 'email': d['email'],
            'password': d['password'],
        }


class RegistroClienteForm(DatosPersonalesForm):
    fecha_nacimiento = forms.DateField(
        required=False, widget=forms.DateInput(attrs={'type': 'date'}),
    )
    telefono = forms.CharField(max_length=20, required=False)
    password2 = forms.CharField(label='Repite la contraseña', widget=forms.PasswordInput)

    def clean(self):
        datos = super().clean()
        if datos.get('password') and datos.get('password') != datos.get('password2'):
            self.add_error('password2', 'Las contraseñas no coinciden.')
        return datos

    def datos_cliente(self):
        d = self.cleaned_data
        return {**self.datos_admin(), 'fecha_nacimiento': d.get('fecha_nacimiento'),
                'telefono': d.get('telefono', '')}


class TiendaNuevaForm(DatosPersonalesForm):
    """El admin general crea la tienda Y su admin en un solo formulario."""

    nombre_tienda = forms.CharField(label='Nombre de la tienda', max_length=100)
    slug = forms.CharField(label='Subdominio', max_length=30,
                           help_text='La tienda quedará en <subdominio>.localhost')
    plan = forms.ModelChoiceField(queryset=Plan.objects.all())
    dominio_propio = forms.CharField(label='Dominio propio (opcional)', max_length=253, required=False)
    color_primario = forms.CharField(max_length=7, initial='#1B4332', validators=[validar_color_hex],
                                     widget=forms.TextInput(attrs={'type': 'color'}))

    def clean_slug(self):
        slug = self.cleaned_data['slug'].strip().lower()
        # Reutiliza las validaciones del modelo (formato y subdominios reservados).
        for validador in Tienda._meta.get_field('slug').validators:
            validador(slug)
        if Tienda.objects.filter(slug=slug).exists():
            raise forms.ValidationError('Ese subdominio ya está en uso.')
        return slug

    def clean_dominio_propio(self):
        dominio = self.cleaned_data['dominio_propio'].strip().lower()
        if dominio and Tienda.objects.filter(dominio_propio=dominio).exists():
            raise forms.ValidationError('Ese dominio ya está en uso.')
        return dominio


class ConfiguracionTiendaForm(FormularioModelo):
    """Lo que el admin de tienda puede personalizar: nombre, color y logo."""

    class Meta:
        model = Tienda
        fields = ['nombre', 'color_primario', 'logo']
        widgets = {'color_primario': forms.TextInput(attrs={'type': 'color'})}

    def save(self, commit=True):
        tienda = super().save(commit=False)
        if 'logo' in self.changed_data and self.cleaned_data.get('logo'):
            tienda.logo = optimizar(self.cleaned_data['logo'], max_px=400)
        if commit:
            tienda.save()
        return tienda
