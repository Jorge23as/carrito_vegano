from django import template

register = template.Library()


@register.filter
def clp(valor):
    """1234567 -> $1.234.567 (formato de peso chileno)."""
    try:
        return '$' + f'{int(valor):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return '$0'
