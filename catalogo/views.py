"""Vistas web del catálogo: parte pública (sin login) y panel del admin de tienda."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogo.forms import CategoriaForm, ProductoForm
from catalogo.models import Categoria, Producto
from core.permisos import requiere_rol
from tiendas.models import Rol


# --- Público: cualquiera puede ver el catálogo, sin iniciar sesión --------------

def catalogo(request):
    """Portada de una tienda. Filtra por categoría (?categoria=) y busca (?q=)."""
    productos = Producto.objects.de_tienda(request.tienda).activos().select_related('categoria')
    categorias = Categoria.objects.de_tienda(request.tienda).activos()

    categoria_id = request.GET.get('categoria', '')
    if categoria_id.isdigit():
        productos = productos.filter(categoria_id=categoria_id)
    busqueda = request.GET.get('q', '').strip()
    if busqueda:
        productos = productos.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))

    return render(request, 'tienda/catalogo.html', {
        'productos': productos, 'categorias': categorias,
        'categoria_id': categoria_id, 'busqueda': busqueda,
    })


def producto_detalle(request, pk):
    if request.tienda is None:
        return render(request, 'errores/404.html', status=404)
    producto = get_object_or_404(
        Producto.objects.de_tienda(request.tienda).activos().select_related('categoria'), pk=pk)
    return render(request, 'tienda/producto_detalle.html', {'producto': producto})


# --- Panel: productos -----------------------------------------------------------

@requiere_rol(Rol.ADMIN_TIENDA)
def panel_productos(request):
    productos = Producto.objects.de_tienda(request.tienda).select_related('categoria').order_by('-habilitado', 'nombre')
    activos = productos.filter(habilitado=True).count()
    return render(request, 'panel/productos.html', {
        'productos': productos, 'seccion': 'productos',
        'activos': activos, 'limite': request.tienda.plan.max_productos,
    })


@requiere_rol(Rol.ADMIN_TIENDA)
def producto_nuevo(request):
    tienda = request.tienda
    # El plan de suscripción recorta funciones: acá, la cantidad de productos.
    if Producto.objects.de_tienda(tienda).activos().count() >= tienda.plan.max_productos:
        messages.error(request, f'Tu plan {tienda.plan.nombre} permite hasta '
                                f'{tienda.plan.max_productos} productos activos.')
        return redirect('/panel/productos/')
    if not Categoria.objects.de_tienda(tienda).activos().exists():
        messages.error(request, 'Primero crea al menos una categoría.')
        return redirect('/panel/categorias/')

    form = ProductoForm(request.POST or None, request.FILES or None, tienda=tienda)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto creado.')
        return redirect('/panel/productos/')
    return render(request, 'panel/form.html', {'form': form, 'titulo': 'Nuevo producto', 'seccion': 'productos'})


@requiere_rol(Rol.ADMIN_TIENDA)
def producto_editar(request, pk):
    # de_tienda(): editar un producto de otra tienda da 404, aunque se adivine el id.
    producto = get_object_or_404(Producto.objects.de_tienda(request.tienda), pk=pk)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto, tienda=request.tienda)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto actualizado.')
        return redirect('/panel/productos/')
    return render(request, 'panel/form.html', {'form': form, 'titulo': f'Editar {producto.nombre}', 'seccion': 'productos'})


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def producto_baja(request, pk):
    producto = get_object_or_404(Producto.objects.de_tienda(request.tienda), pk=pk)
    producto.dar_de_baja()
    messages.success(request, f'"{producto.nombre}" fue dado de baja.')
    return redirect('/panel/productos/')


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def producto_reactivar(request, pk):
    producto = get_object_or_404(Producto.objects.de_tienda(request.tienda), pk=pk)
    activos = Producto.objects.de_tienda(request.tienda).activos().count()
    if activos >= request.tienda.plan.max_productos:
        messages.error(request, 'Llegaste al límite de productos de tu plan.')
    else:
        producto.reactivar()
        messages.success(request, f'"{producto.nombre}" fue reactivado.')
    return redirect('/panel/productos/')


# --- Panel: categorías ----------------------------------------------------------

@requiere_rol(Rol.ADMIN_TIENDA)
def panel_categorias(request):
    categorias = Categoria.objects.de_tienda(request.tienda).order_by('-habilitado', 'nombre')
    return render(request, 'panel/categorias.html', {'categorias': categorias, 'seccion': 'categorias'})


@requiere_rol(Rol.ADMIN_TIENDA)
def categoria_nueva(request):
    form = CategoriaForm(request.POST or None, tienda=request.tienda)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Categoría creada.')
        return redirect('/panel/categorias/')
    return render(request, 'panel/form.html', {'form': form, 'titulo': 'Nueva categoría', 'seccion': 'categorias'})


@requiere_rol(Rol.ADMIN_TIENDA)
def categoria_editar(request, pk):
    categoria = get_object_or_404(Categoria.objects.de_tienda(request.tienda), pk=pk)
    form = CategoriaForm(request.POST or None, instance=categoria, tienda=request.tienda)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Categoría actualizada.')
        return redirect('/panel/categorias/')
    return render(request, 'panel/form.html', {'form': form, 'titulo': f'Editar {categoria.nombre}', 'seccion': 'categorias'})


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def categoria_baja(request, pk):
    categoria = get_object_or_404(Categoria.objects.de_tienda(request.tienda), pk=pk)
    categoria.dar_de_baja()
    messages.success(request, f'Categoría "{categoria.nombre}" dada de baja.')
    return redirect('/panel/categorias/')


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def categoria_reactivar(request, pk):
    categoria = get_object_or_404(Categoria.objects.de_tienda(request.tienda), pk=pk)
    categoria.reactivar()
    messages.success(request, f'Categoría "{categoria.nombre}" reactivada.')
    return redirect('/panel/categorias/')
