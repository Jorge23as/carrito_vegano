from django import forms

from catalogo.models import Categoria, Producto
from core.forms import FormularioModelo
from core.imagenes import optimizar


class CategoriaForm(FormularioModelo):
    class Meta:
        model = Categoria
        fields = ['nombre']

    def __init__(self, *args, tienda, **kwargs):
        super().__init__(*args, **kwargs)
        self.tienda = tienda

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        repetida = Categoria.objects.de_tienda(self.tienda).filter(nombre__iexact=nombre)
        if self.instance.pk:
            repetida = repetida.exclude(pk=self.instance.pk)
        if repetida.exists():
            raise forms.ValidationError('Ya existe una categoría con ese nombre.')
        return nombre

    def save(self, commit=True):
        categoria = super().save(commit=False)
        categoria.tienda = self.tienda
        if commit:
            categoria.save()
        return categoria


class ProductoForm(FormularioModelo):
    class Meta:
        model = Producto
        fields = ['categoria', 'nombre', 'descripcion', 'precio', 'stock', 'imagen']
        widgets = {'descripcion': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, tienda, **kwargs):
        super().__init__(*args, **kwargs)
        self.tienda = tienda
        # Solo se puede elegir una categoría ACTIVA de ESTA tienda.
        self.fields['categoria'].queryset = Categoria.objects.de_tienda(tienda).activos()

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio < 1:
            raise forms.ValidationError('El precio debe ser mayor a 0.')
        return precio

    def save(self, commit=True):
        producto = super().save(commit=False)
        producto.tienda = self.tienda
        if 'imagen' in self.changed_data and self.cleaned_data.get('imagen'):
            producto.imagen = optimizar(self.cleaned_data['imagen'])
        if commit:
            producto.save()
        return producto
