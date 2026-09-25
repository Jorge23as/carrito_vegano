from django import forms


class EstiloMixin:
    """Le pone la clase CSS 'input' a todos los campos, para no repetirla
    en cada formulario (los estilos están en static/css/app.css)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if not isinstance(campo.widget, (forms.CheckboxInput, forms.FileInput)):
                campo.widget.attrs.setdefault('class', 'input')


class Formulario(EstiloMixin, forms.Form):
    pass


class FormularioModelo(EstiloMixin, forms.ModelForm):
    pass
