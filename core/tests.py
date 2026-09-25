"""
Tests del proyecto. Cada clase prueba una regla de la prueba 2.
Correr con:  python manage.py test

Sirven además como "documentación ejecutable": si una regla deja de cumplirse,
un test falla.
"""

import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from catalogo.models import Categoria, Producto
from core.models import Metrica
from tiendas import services
from tiendas.models import PerfilUsuario, Plan, Rol, Tienda
from ventas import services as ventas
from ventas.models import EstadoPedido, Pedido

CLAVE = 'Clave-Segura-2026'
HOST_A = 'tienda-a.localhost'
HOST_B = 'tienda-b.localhost'


def crear_tienda(slug, plan='Pro'):
    """Crea una tienda con su admin (email admin@<slug>.cl) y un producto."""
    tienda, admin = services.crear_tienda_con_admin(
        nombre=slug.title(), slug=slug, plan=Plan.objects.get(nombre=plan),
        admin={'nombres': 'Ana', 'apellido_paterno': 'Admin', 'email': f'admin@{slug}.cl', 'password': CLAVE},
    )
    categoria = Categoria.objects.create(tienda=tienda, nombre='General')
    producto = Producto.objects.create(tienda=tienda, categoria=categoria, nombre='Cosa', precio=1000, stock=10)
    return tienda, admin, categoria, producto


def crear_cliente(tienda, email='cli@correo.cl'):
    return services.registrar_cliente(
        tienda, nombres='Cami', apellido_paterno='Rojas', email=email, password=CLAVE)


def login_api(client, host, email, password=CLAVE):
    return client.post('/api/auth/login/', json.dumps({'email': email, 'password': password}),
                       content_type='application/json', HTTP_HOST=host)


class Base(TestCase):
    def setUp(self):
        cache.clear()  # el contador de intentos de login vive en caché
        self.a, self.admin_a, self.cat_a, self.prod_a = crear_tienda('tienda-a')
        self.b, self.admin_b, self.cat_b, self.prod_b = crear_tienda('tienda-b')
        self.cli_a = crear_cliente(self.a)
        self.client = Client()


class TenantTests(Base):
    def test_el_host_decide_la_tienda(self):
        r = self.client.get('/', HTTP_HOST=HOST_A)
        self.assertContains(r, 'Tienda-A')
        self.assertNotContains(r, 'Tienda-B')

    def test_tienda_inexistente_da_404_amable(self):
        r = self.client.get('/', HTTP_HOST='fantasma.localhost')
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, 'no existe', status_code=404)

    def test_tienda_suspendida_da_403(self):
        self.a.dar_de_baja()
        self.assertEqual(self.client.get('/', HTTP_HOST=HOST_A).status_code, 403)

    def test_dominio_propio(self):
        self.a.dominio_propio = 'zapatilleate.cl'
        self.a.save()
        with self.settings(ALLOWED_HOSTS=['zapatilleate.cl']):
            r = self.client.get('/', HTTP_HOST='zapatilleate.cl')
        self.assertContains(r, 'Tienda-A')

    def test_portada_de_plataforma_lista_tiendas(self):
        r = self.client.get('/')
        self.assertContains(r, 'Tienda-A')
        self.assertContains(r, 'Tienda-B')

    def test_cada_tienda_ve_solo_sus_productos(self):
        Producto.objects.create(tienda=self.b, categoria=self.cat_b, nombre='Exclusivo de B', precio=5, stock=1)
        r = self.client.get('/api/productos/', HTTP_HOST=HOST_A)
        nombres = [p['nombre'] for p in r.json()['results']]
        self.assertNotIn('Exclusivo de B', nombres)


class ErroresControladosTests(Base):
    def test_url_basura_en_tienda_y_plataforma(self):
        for host in ('localhost', HOST_A):
            r = self.client.get('/esto/no/existe/???', HTTP_HOST=host)
            self.assertEqual(r.status_code, 404)
            # Redirección automática al inicio + botón.
            self.assertContains(r, 'http-equiv="refresh"', status_code=404)
            self.assertContains(r, 'Volver al inicio', status_code=404)

    def test_url_basura_de_la_api_responde_json(self):
        r = self.client.get('/api/nada/', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 404)
        self.assertIn('error', r.json())

    def test_producto_inexistente_da_404(self):
        self.assertEqual(self.client.get('/producto/99999/', HTTP_HOST=HOST_A).status_code, 404)


class AutenticacionTests(Base):
    def test_catalogo_es_publico(self):
        self.assertEqual(self.client.get('/', HTTP_HOST=HOST_A).status_code, 200)
        self.assertEqual(self.client.get('/api/productos/', HTTP_HOST=HOST_A).status_code, 200)

    def test_endpoint_protegido_sin_login_da_401(self):
        self.assertEqual(self.client.get('/api/carrito/', HTTP_HOST=HOST_A).status_code, 401)
        self.assertEqual(self.client.get('/api/clientes/', HTTP_HOST=HOST_A).status_code, 401)

    def test_pagina_protegida_redirige_al_login(self):
        r = self.client.get('/panel/', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.url.startswith('/login/'))

    def test_login_deja_jwt_en_cookie_httponly(self):
        r = login_api(self.client, HOST_A, 'cli@correo.cl')
        self.assertEqual(r.status_code, 200)
        cookie = r.cookies['access_token']
        self.assertTrue(cookie['httponly'])
        self.assertNotIn('access', r.json())  # el token NO viaja en el cuerpo

    def test_login_web_y_acceso(self):
        r = self.client.post('/login/', {'email': 'cli@correo.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get('/carrito/', HTTP_HOST=HOST_A).status_code, 200)

    def test_credenciales_malas(self):
        r = login_api(self.client, HOST_A, 'cli@correo.cl', 'incorrecta')
        self.assertEqual(r.status_code, 401)

    def test_la_cookie_de_una_tienda_no_sirve_en_otra(self):
        """Un token válido NO basta: también debe pertenecer a la tienda del subdominio."""
        login_api(self.client, HOST_A, 'cli@correo.cl')
        self.assertEqual(self.client.get('/api/auth/yo/', HTTP_HOST=HOST_A).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/yo/', HTTP_HOST=HOST_B).status_code, 401)

    def test_cliente_de_una_tienda_no_entra_al_login_de_otra(self):
        r = login_api(self.client, HOST_B, 'cli@correo.cl')  # el cliente solo existe en A
        self.assertEqual(r.status_code, 401)

    def test_bloqueo_por_intentos_fallidos(self):
        for _ in range(5):
            login_api(self.client, HOST_A, 'cli@correo.cl', 'mala')
        r = login_api(self.client, HOST_A, 'cli@correo.cl', CLAVE)  # ni la correcta pasa
        self.assertEqual(r.status_code, 429)

    def test_logout_invalida_el_refresh(self):
        login_api(self.client, HOST_A, 'cli@correo.cl')
        refresh = self.client.cookies['refresh_token'].value
        self.client.post('/api/auth/logout/', HTTP_HOST=HOST_A)
        # Aunque alguien hubiera copiado el refresh, ya no sirve.
        otro = Client()
        otro.cookies['refresh_token'] = refresh
        self.assertEqual(otro.get('/api/auth/yo/', HTTP_HOST=HOST_A).status_code, 401)

    def test_open_redirect_bloqueado(self):
        r = self.client.post('/login/?next=https://sitio-malo.com/', {'email': 'cli@correo.cl', 'password': CLAVE},
                             HTTP_HOST=HOST_A)
        self.assertEqual(r.url, '/')

    def test_csrf_se_exige_en_la_api_con_cookie(self):
        cliente = Client(enforce_csrf_checks=True)
        login_api(cliente, HOST_A, 'admin@tienda-a.cl')
        datos = json.dumps({'nombre': 'Nueva'})
        sin_token = cliente.post('/api/categorias/', datos, content_type='application/json', HTTP_HOST=HOST_A)
        self.assertEqual(sin_token.status_code, 403)
        cliente.get('/', HTTP_HOST=HOST_A)  # esta página trae un formulario y entrega la cookie csrftoken
        token = cliente.cookies['csrftoken'].value
        con_token = cliente.post('/api/categorias/', datos, content_type='application/json',
                                 HTTP_HOST=HOST_A, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(con_token.status_code, 201)


class JerarquiaTests(Base):
    def test_al_crear_tienda_se_crea_su_admin(self):
        perfil = PerfilUsuario.objects.get(user__email='admin@tienda-a.cl')
        self.assertEqual(perfil.rol.codigo, Rol.ADMIN_TIENDA)
        self.assertEqual(perfil.tienda, self.a)

    def test_admin_general_crea_tienda_por_la_web(self):
        services.crear_admin_general(email='root@plataforma.cl', password=CLAVE, nombres='Root', apellido_paterno='X')
        self.client.post('/login/', {'email': 'root@plataforma.cl', 'password': CLAVE})
        r = self.client.post('/plataforma/tiendas/nueva/', {
            'nombre_tienda': 'Zapatos', 'slug': 'zapatos', 'plan': Plan.objects.get(nombre='Básico').pk,
            'color_primario': '#112233', 'dominio_propio': '', 'nombres': 'Luis', 'apellido_paterno': 'Perez',
            'apellido_materno': '', 'email': 'luis@zapatos.cl', 'password': CLAVE,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(PerfilUsuario.objects.filter(user__email='luis@zapatos.cl', rol__codigo=Rol.ADMIN_TIENDA).exists())

    def test_admin_de_tienda_no_puede_crear_tiendas(self):
        login_api(self.client, HOST_A, 'admin@tienda-a.cl')
        r = self.client.post('/api/tiendas/', json.dumps({}), content_type='application/json', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 403)

    def test_admin_de_tienda_no_entra_a_la_plataforma(self):
        self.client.post('/login/', {'email': 'admin@tienda-a.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        # su cookie no vale en el host de la plataforma
        self.assertEqual(self.client.get('/plataforma/').status_code, 302)

    def test_admin_de_tienda_no_puede_crear_otro_admin(self):
        """No existe ningún endpoint para que un admin cree admins: solo el general reasigna."""
        login_api(self.client, HOST_A, 'admin@tienda-a.cl')
        r = self.client.post('/api/tiendas/1/reasignar-admin/', json.dumps({}), content_type='application/json',
                             HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 403)

    def test_cliente_se_autoregistra_con_permisos_minimos(self):
        r = self.client.post('/api/auth/registro/', json.dumps({
            'nombres': 'Nuevo', 'apellido_paterno': 'Cliente', 'email': 'nuevo@correo.cl', 'password': CLAVE}),
            content_type='application/json', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['rol'], Rol.CLIENTE)
        r = self.client.post('/api/productos/', json.dumps({'nombre': 'x'}), content_type='application/json', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 403)  # un cliente no crea productos

    def test_reasignar_admin(self):
        services.crear_admin_general(email='root@plataforma.cl', password=CLAVE, nombres='Root', apellido_paterno='X')
        self.client.post('/login/', {'email': 'root@plataforma.cl', 'password': CLAVE})
        self.client.post(f'/plataforma/tiendas/{self.a.pk}/reasignar-admin/', {
            'nombres': 'Nuevo', 'apellido_paterno': 'Jefe', 'apellido_materno': '',
            'email': 'jefe@tienda-a.cl', 'password': CLAVE})
        self.admin_a.refresh_from_db()
        self.assertFalse(self.admin_a.habilitado)  # el anterior quedó de baja, no borrado
        self.assertTrue(PerfilUsuario.objects.filter(user__email='jefe@tienda-a.cl', habilitado=True).exists())

    def test_nombres_separados_en_perfil(self):
        campos = [f.name for f in PerfilUsuario._meta.get_fields()]
        for esperado in ('nombres', 'apellido_paterno', 'apellido_materno'):
            self.assertIn(esperado, campos)


class BajaLogicaTests(Base):
    def test_delete_de_un_objeto_es_baja(self):
        self.prod_a.delete()
        self.assertTrue(Producto.objects.filter(pk=self.prod_a.pk).exists())
        self.prod_a.refresh_from_db()
        self.assertFalse(self.prod_a.habilitado)
        self.assertIsNotNone(self.prod_a.fecha_baja)

    def test_delete_de_un_queryset_es_baja(self):
        Producto.objects.filter(tienda=self.a).delete()
        self.assertEqual(Producto.objects.filter(tienda=self.a, habilitado=True).count(), 0)
        self.assertEqual(Producto.objects.filter(tienda=self.a).count(), 1)

    def test_api_delete_no_ejecuta_sql_delete(self):
        login_api(self.client, HOST_A, 'admin@tienda-a.cl')
        with CaptureQueriesContext(connection) as consultas:
            r = self.client.delete(f'/api/productos/{self.prod_a.pk}/', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 204)
        self.assertFalse([q for q in consultas if q['sql'].lstrip().upper().startswith('DELETE')])
        # deja de verse en el catálogo público, pero la fila sigue
        publico = Client().get('/api/productos/', HTTP_HOST=HOST_A).json()['results']  # visitante anónimo
        self.assertEqual(publico, [])
        self.assertTrue(Producto.objects.filter(pk=self.prod_a.pk).exists())

    def test_baneo_corta_la_sesion_al_instante(self):
        login_api(self.client, HOST_A, 'cli@correo.cl')
        self.assertEqual(self.client.get('/api/carrito/', HTTP_HOST=HOST_A).status_code, 200)
        self.cli_a.dar_de_baja()
        self.assertEqual(self.client.get('/api/carrito/', HTTP_HOST=HOST_A).status_code, 401)
        self.assertEqual(login_api(Client(), HOST_A, 'cli@correo.cl').status_code, 401)
        self.assertTrue(User.objects.filter(pk=self.cli_a.user_id).exists())  # la cuenta sigue en la BD

    def test_admin_banea_cliente_por_la_web(self):
        self.client.post('/login/', {'email': 'admin@tienda-a.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        self.client.post(f'/panel/clientes/{self.cli_a.pk}/baja/', HTTP_HOST=HOST_A)
        self.cli_a.refresh_from_db()
        self.assertFalse(self.cli_a.habilitado)

    def test_admin_no_puede_tocar_clientes_de_otra_tienda(self):
        otro = crear_cliente(self.b, 'otro@correo.cl')
        self.client.post('/login/', {'email': 'admin@tienda-a.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        r = self.client.post(f'/panel/clientes/{otro.pk}/baja/', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 404)
        otro.refresh_from_db()
        self.assertTrue(otro.habilitado)

    def test_admin_no_edita_productos_de_otra_tienda(self):
        self.client.post('/login/', {'email': 'admin@tienda-a.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        self.assertEqual(self.client.get(f'/panel/productos/{self.prod_b.pk}/editar/', HTTP_HOST=HOST_A).status_code, 404)
        r = self.client.delete(f'/api/productos/{self.prod_b.pk}/', HTTP_HOST=HOST_A)
        self.assertIn(r.status_code, (403, 404))


class CarritoTests(Base):
    def test_carrito_distinto_por_usuario_y_por_tienda(self):
        cli2 = crear_cliente(self.a, 'otra@correo.cl')
        mismo_correo_en_b = crear_cliente(self.b, 'cli@correo.cl')  # mismo correo, otra tienda
        ventas.agregar_producto(self.cli_a, self.prod_a.pk, 2)
        self.assertEqual(ventas.carrito_abierto(self.cli_a).total, 2000)
        self.assertEqual(ventas.carrito_abierto(cli2).total, 0)
        self.assertEqual(ventas.carrito_abierto(mismo_correo_en_b).total, 0)
        self.assertNotEqual(ventas.carrito_abierto(self.cli_a).pk, ventas.carrito_abierto(cli2).pk)

    def test_no_se_agrega_producto_de_otra_tienda(self):
        from core.errores import ErrorNegocio
        with self.assertRaises(ErrorNegocio):
            ventas.agregar_producto(self.cli_a, self.prod_b.pk, 1)

    def test_quitar_item_es_baja_logica(self):
        item = ventas.agregar_producto(self.cli_a, self.prod_a.pk, 1)
        ventas.quitar_item(self.cli_a, item.pk)
        item.refresh_from_db()
        self.assertFalse(item.habilitado)
        self.assertEqual(ventas.carrito_abierto(self.cli_a).total, 0)

    def test_pagar_descuenta_stock_y_congela_precio(self):
        ventas.agregar_producto(self.cli_a, self.prod_a.pk, 3)
        pedido = ventas.pagar(self.cli_a)
        self.prod_a.refresh_from_db()
        self.assertEqual(self.prod_a.stock, 7)
        self.assertEqual(pedido.total, 3000)
        self.prod_a.precio = 9999
        self.prod_a.save()
        self.assertEqual(pedido.items.first().precio_unitario, 1000)  # el pedido no cambia

    def test_stock_insuficiente(self):
        from core.errores import ErrorNegocio
        with self.assertRaises(ErrorNegocio):
            ventas.agregar_producto(self.cli_a, self.prod_a.pk, 11)

    def test_carrito_vacio_no_se_paga(self):
        from core.errores import ErrorNegocio
        with self.assertRaises(ErrorNegocio):
            ventas.pagar(self.cli_a)

    def test_cancelar_pedido_devuelve_stock(self):
        ventas.agregar_producto(self.cli_a, self.prod_a.pk, 4)
        pedido = ventas.pagar(self.cli_a)
        ventas.cambiar_estado_pedido(pedido, 'CANCELADO')
        self.prod_a.refresh_from_db()
        self.assertEqual(self.prod_a.stock, 10)

    def test_no_se_puede_saltar_estados(self):
        from core.errores import ErrorNegocio
        ventas.agregar_producto(self.cli_a, self.prod_a.pk, 1)
        pedido = ventas.pagar(self.cli_a)
        with self.assertRaises(ErrorNegocio):
            ventas.cambiar_estado_pedido(pedido, 'ENTREGADO')  # falta pasar por ENVIADO

    def test_flujo_completo_por_la_api(self):
        login_api(self.client, HOST_A, 'cli@correo.cl')
        r = self.client.post('/api/carrito/items/', json.dumps({'producto': self.prod_a.pk, 'cantidad': 2}),
                             content_type='application/json', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get('/api/carrito/', HTTP_HOST=HOST_A).json()['total'], 2000)
        r = self.client.post('/api/carrito/pagar/', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.client.get('/api/pedidos/', HTTP_HOST=HOST_A).json()['results']), 1)

    def test_cliente_no_ve_pedidos_de_otro(self):
        cli2 = crear_cliente(self.a, 'otra@correo.cl')
        ventas.agregar_producto(cli2, self.prod_a.pk, 1)
        pedido_ajeno = ventas.pagar(cli2)
        login_api(self.client, HOST_A, 'cli@correo.cl')
        self.assertEqual(self.client.get(f'/api/pedidos/{pedido_ajeno.pk}/', HTTP_HOST=HOST_A).status_code, 404)
        self.assertEqual(self.client.get(f'/pedidos/{pedido_ajeno.pk}/', HTTP_HOST=HOST_A).status_code, 404)

    def test_cantidad_maliciosa_no_rompe(self):
        self.client.post('/login/', {'email': 'cli@correo.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        r = self.client.post(f'/carrito/agregar/{self.prod_a.pk}/', {'cantidad': 'abc'}, HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 302)  # mensaje de error, no un 500
        r = self.client.post(f'/carrito/agregar/{self.prod_a.pk}/', {'cantidad': '-5'}, HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 302)


class PlanYPersonalizacionTests(Base):
    def test_el_plan_limita_los_productos(self):
        Plan.objects.filter(nombre='Pro').update(max_productos=1)  # tienda-a ya tiene 1
        login_api(self.client, HOST_A, 'admin@tienda-a.cl')
        r = self.client.post('/api/productos/', json.dumps({'categoria': self.cat_a.pk, 'nombre': 'Otro', 'precio': 10, 'stock': 1}),
                             content_type='application/json', HTTP_HOST=HOST_A)
        self.assertEqual(r.status_code, 400)

    def test_admin_de_tienda_cambia_color(self):
        self.client.post('/login/', {'email': 'admin@tienda-a.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        self.client.post('/panel/configuracion/', {'nombre': 'Mi Tienda', 'color_primario': '#AA0000'}, HTTP_HOST=HOST_A)
        self.a.refresh_from_db()
        self.assertEqual(self.a.color_primario, '#AA0000')
        self.assertContains(self.client.get('/', HTTP_HOST=HOST_A), '--primario: #AA0000')

    def test_color_invalido_se_rechaza(self):
        """El color va dentro del CSS: aceptar cualquier texto permitiría inyectar código."""
        self.client.post('/login/', {'email': 'admin@tienda-a.cl', 'password': CLAVE}, HTTP_HOST=HOST_A)
        self.client.post('/panel/configuracion/', {'nombre': 'X', 'color_primario': 'red;}</style><script>alert(1)</script>'}, HTTP_HOST=HOST_A)
        self.a.refresh_from_db()
        self.assertEqual(self.a.color_primario, '#1B4332')

    def test_xss_en_nombre_de_producto_se_escapa(self):
        Producto.objects.create(tienda=self.a, categoria=self.cat_a, nombre='<script>alert(1)</script>', precio=1, stock=1)
        r = self.client.get('/', HTTP_HOST=HOST_A)
        self.assertNotContains(r, '<script>alert(1)</script>')
        self.assertContains(r, '&lt;script&gt;')


class MetricasTests(Base):
    def test_cada_request_de_tienda_deja_una_metrica(self):
        self.client.get('/', HTTP_HOST=HOST_A)
        m = Metrica.objects.filter(tienda=self.a).latest('id')
        self.assertEqual((m.metodo, m.ruta, m.status), ('GET', '/', 200))


class DemoTests(Base):
    def test_reiniciar_demo_deja_todo_como_al_inicio(self):
        from core.demo import reiniciar_demo
        tienda = reiniciar_demo()
        cliente = PerfilUsuario.objects.get(user__email='cliente@demo.cl', tienda=tienda)
        ventas.agregar_producto(cliente, Producto.objects.filter(tienda=tienda).first().pk, 1)
        ventas.pagar(cliente)
        antes = Pedido.objects.filter(tienda=tienda).count()
        reiniciar_demo()  # "Sandbox zero"
        tienda = Tienda.objects.get(slug='demo')
        self.assertEqual(Pedido.objects.filter(tienda=tienda).count(), 1)
        self.assertLess(Pedido.objects.filter(tienda=tienda).count(), antes)
