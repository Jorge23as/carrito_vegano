"""
Vistas web (con templates) de tiendas y usuarios.

Convención: cada vista con permisos lleva @requiere_rol(...) arriba. Si el
rol no calza, el decorador responde 403; si no hay sesión, redirige al login.
"""

from django.conf import settings
from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.auth import (
    borrar_cookies, emitir_tokens, invalidar_refresh, limpiar_fallos,
    login_bloqueado, poner_cookies, registrar_fallo,
)
from core.demo import reiniciar_demo
from core.errores import ErrorNegocio
from core.models import Metrica
from core.permisos import requiere_rol
from core.utils import destino_seguro, url_tienda
from tiendas import services
from tiendas.forms import (
    ConfiguracionTiendaForm, DatosPersonalesForm, LoginForm, RegistroClienteForm,
    TiendaNuevaForm,
)
from tiendas.models import PerfilUsuario, Rol, Tienda


def _destino_por_rol(perfil):
    if perfil.rol.codigo == Rol.ADMIN_GENERAL:
        return '/plataforma/'
    if perfil.rol.codigo == Rol.ADMIN_TIENDA:
        return '/panel/'
    return '/'


def _iniciar_sesion(perfil, destino):
    """Responde con una redirección y deja los JWT en cookies HttpOnly."""
    respuesta = redirect(destino)
    access, refresh = emitir_tokens(perfil)
    poner_cookies(respuesta, access, refresh)
    return respuesta


# --- Sesión -------------------------------------------------------------------

def login_view(request):
    if request.perfil:
        return redirect(_destino_por_rol(request.perfil))

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        host, email = request.get_host(), form.cleaned_data['email']
        if login_bloqueado(host, email):
            # Defensa contra fuerza bruta: 5 fallos => 5 minutos de bloqueo.
            form.add_error(None, 'Demasiados intentos fallidos. Espera 5 minutos.')
        else:
            try:
                _, perfil = services.autenticar_credenciales(
                    request.tienda, email, form.cleaned_data['password'])
            except ErrorNegocio as error:
                registrar_fallo(host, email)
                form.add_error(None, str(error))
            else:
                limpiar_fallos(host, email)
                destino = destino_seguro(request, request.GET.get('next'), _destino_por_rol(perfil))
                return _iniciar_sesion(perfil, destino)
    return render(request, 'cuentas/login.html', {'form': form})


def registro_view(request):
    """Autoregistro de clientes (solo dentro de una tienda)."""
    if request.tienda is None:
        return render(request, 'errores/404.html', status=404)
    if request.perfil:
        return redirect('/')

    form = RegistroClienteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            perfil = services.registrar_cliente(request.tienda, **form.datos_cliente())
        except ErrorNegocio as error:
            form.add_error('email', str(error))
        else:
            messages.success(request, f'¡Bienvenido/a, {perfil.nombres}!')
            return _iniciar_sesion(perfil, '/')
    return render(request, 'cuentas/registro.html', {'form': form})


@require_POST
def logout_view(request):
    # POST y no GET: así un enlace o imagen ajena no puede cerrarte la sesión.
    invalidar_refresh(request)
    respuesta = redirect('/')
    borrar_cookies(respuesta)
    return respuesta


# --- Plataforma (admin general) ---------------------------------------------------

def home_plataforma(request):
    """Portada pública de la plataforma: lista las tiendas activas."""
    tiendas = list(Tienda.objects.activos().select_related('plan'))
    for t in tiendas:
        t.url = url_tienda(request, t)
    return render(request, 'plataforma/inicio.html', {'tiendas': tiendas})


@requiere_rol(Rol.ADMIN_GENERAL)
def plataforma_dashboard(request):
    """Dashboard general: tiendas, dinero/ventas por tienda y tiempos de respuesta."""
    no_cancelado = ~Q(pedidos__estado__codigo='CANCELADO') & Q(pedidos__habilitado=True)
    filas = list(
        Tienda.objects.select_related('plan').annotate(
            n_ventas=Count('pedidos', filter=no_cancelado),
            dinero=Sum('pedidos__total', filter=no_cancelado),
        )
    )
    tiempos = {
        f['tienda']: f for f in
        Metrica.objects.filter(tienda__isnull=False).values('tienda')
        .annotate(promedio=Avg('duracion_ms'), n=Count('id'))
    }
    for fila in filas:
        fila.dinero = fila.dinero or 0
        t = tiempos.get(fila.id)
        fila.tiempo_ms = round(t['promedio']) if t else None
        fila.n_requests = t['n'] if t else 0

    return render(request, 'plataforma/dashboard.html', {
        'filas': filas,
        'total_tiendas': len(filas),
        'tiendas_activas': sum(1 for f in filas if f.habilitado),
        'dinero_total': sum(f.dinero for f in filas),
        'ventas_total': sum(f.n_ventas for f in filas),
        'demo_slug': settings.TIENDA_DEMO_SLUG,
    })


@requiere_rol(Rol.ADMIN_GENERAL)
def plataforma_tiendas(request):
    tiendas = list(Tienda.objects.select_related('plan').order_by('-habilitado', 'nombre'))
    for t in tiendas:
        t.url = url_tienda(request, t)
        t.admin = t.perfiles.filter(rol__codigo=Rol.ADMIN_TIENDA, habilitado=True).select_related('user').first()
    return render(request, 'plataforma/tiendas.html', {'tiendas': tiendas})


@requiere_rol(Rol.ADMIN_GENERAL)
def tienda_nueva(request):
    form = TiendaNuevaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            tienda, _ = services.crear_tienda_con_admin(
                nombre=d['nombre_tienda'], slug=d['slug'], plan=d['plan'],
                color_primario=d['color_primario'], dominio_propio=d['dominio_propio'],
                admin=form.datos_admin(),
            )
        except ErrorNegocio as error:
            form.add_error('email', str(error))
        else:
            messages.success(request, f'Tienda "{tienda.nombre}" creada junto a su administrador.')
            return redirect('/plataforma/tiendas/')
    return render(request, 'plataforma/tienda_form.html', {'form': form})


@requiere_rol(Rol.ADMIN_GENERAL)
@require_POST
def tienda_baja(request, pk):
    tienda = get_object_or_404(Tienda, pk=pk)
    tienda.dar_de_baja()
    messages.success(request, f'"{tienda.nombre}" fue suspendida (baja lógica).')
    return redirect('/plataforma/tiendas/')


@requiere_rol(Rol.ADMIN_GENERAL)
@require_POST
def tienda_reactivar(request, pk):
    tienda = get_object_or_404(Tienda, pk=pk)
    tienda.reactivar()
    messages.success(request, f'"{tienda.nombre}" fue reactivada.')
    return redirect('/plataforma/tiendas/')


@requiere_rol(Rol.ADMIN_GENERAL)
def tienda_reasignar_admin(request, pk):
    """El admin de una tienda desapareció: el admin general designa uno nuevo."""
    tienda = get_object_or_404(Tienda, pk=pk)
    form = DatosPersonalesForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.reasignar_admin_tienda(tienda, **form.datos_admin())
        except ErrorNegocio as error:
            form.add_error('email', str(error))
        else:
            messages.success(request, f'Nuevo administrador asignado a "{tienda.nombre}".')
            return redirect('/plataforma/tiendas/')
    return render(request, 'plataforma/reasignar.html', {'form': form, 'tienda_obj': tienda})


@requiere_rol(Rol.ADMIN_GENERAL)
@require_POST
def demo_reiniciar(request):
    reiniciar_demo()
    messages.success(request, 'La tienda demo volvió a su estado original.')
    return redirect('/plataforma/')


# --- Panel de la tienda (admin de tienda) -----------------------------------------

@requiere_rol(Rol.ADMIN_TIENDA)
def panel_configuracion(request):
    form = ConfiguracionTiendaForm(request.POST or None, request.FILES or None, instance=request.tienda)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Configuración guardada.')
        return redirect('/panel/configuracion/')
    return render(request, 'panel/form.html', {
        'form': form, 'titulo': 'Configuración de la tienda', 'seccion': 'configuracion',
        'ayuda': 'Personaliza el nombre, el color y el logo de tu tienda.',
    })


@requiere_rol(Rol.ADMIN_TIENDA)
def panel_clientes(request):
    clientes = (
        PerfilUsuario.objects.de_tienda(request.tienda)
        .filter(rol__codigo=Rol.CLIENTE).select_related('user').order_by('-habilitado', 'apellido_paterno')
    )
    return render(request, 'panel/clientes.html', {'clientes': clientes, 'seccion': 'clientes'})


def _cliente_de_la_tienda(request, pk):
    # Solo clientes de ESTA tienda: si el id es de otra, responde 404.
    return get_object_or_404(
        PerfilUsuario.objects.de_tienda(request.tienda).filter(rol__codigo=Rol.CLIENTE), pk=pk)


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def cliente_baja(request, pk):
    cliente = _cliente_de_la_tienda(request, pk)
    cliente.dar_de_baja()  # banea la cuenta: su sesión deja de funcionar al instante
    messages.success(request, f'{cliente.nombre_completo} fue baneado/a.')
    return redirect('/panel/clientes/')


@requiere_rol(Rol.ADMIN_TIENDA)
@require_POST
def cliente_reactivar(request, pk):
    cliente = _cliente_de_la_tienda(request, pk)
    cliente.reactivar()
    messages.success(request, f'{cliente.nombre_completo} fue reactivado/a.')
    return redirect('/panel/clientes/')
