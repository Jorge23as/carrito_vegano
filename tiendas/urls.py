from django.urls import path

from tiendas import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
    # Plataforma (solo admin general, solo en el host sin tienda)
    path('plataforma/', views.plataforma_dashboard),
    path('plataforma/tiendas/', views.plataforma_tiendas),
    path('plataforma/tiendas/nueva/', views.tienda_nueva),
    path('plataforma/tiendas/<int:pk>/baja/', views.tienda_baja),
    path('plataforma/tiendas/<int:pk>/reactivar/', views.tienda_reactivar),
    path('plataforma/tiendas/<int:pk>/reasignar-admin/', views.tienda_reasignar_admin),
    path('plataforma/demo/reiniciar/', views.demo_reiniciar),
    # Panel de la tienda (solo admin de tienda)
    path('panel/configuracion/', views.panel_configuracion),
    path('panel/clientes/', views.panel_clientes),
    path('panel/clientes/<int:pk>/baja/', views.cliente_baja),
    path('panel/clientes/<int:pk>/reactivar/', views.cliente_reactivar),
]
