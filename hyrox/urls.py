from django.urls import path
from . import views

app_name = 'hyrox'

urlpatterns = [
    path('dashboard/', views.hyrox_dashboard, name='dashboard'),
    path('crear-objetivo/', views.crear_objetivo, name='crear_objetivo'),
    path('cancelar-objetivo/<int:objective_id>/', views.cancelar_objetivo, name='cancelar_objetivo'),
    path('registrar-entrenamiento/<int:objective_id>/', views.registrar_entrenamiento, name='registrar_entrenamiento'),
    path('registrar-entrenamiento/<int:objective_id>/<int:session_id>/', views.registrar_entrenamiento, name='registrar_entrenamiento_session'),
    path('regenerar-plan/<int:objective_id>/', views.regenerar_plan, name='regenerar_plan'),
    path('borrar-entrenamiento/<int:session_id>/', views.borrar_entrenamiento, name='borrar_entrenamiento'),
    path('editar-sesion/<int:session_id>/', views.editar_sesion_hyrox, name='editar_sesion'),
    path('procesar-con-ia/<int:session_id>/', views.procesar_con_ia, name='procesar_con_ia'),
    path('registrar-entrenamiento-ia/<int:session_id>/', views.registrar_entrenamiento_ia, name='registrar_entrenamiento_ia'),
    path('coach-chat/', views.CoachInteractionView.as_view(), name='coach_chat'),
    path('get-greeting/', views.GetGreetingView.as_view(), name='get_greeting'),
    path('reportar-lesion/', views.reportar_lesion, name='reportar_lesion'),
    path('reportar-recuperacion/<int:lesion_id>/', views.reportar_recuperacion, name='reportar_recuperacion'),
    path('marcar-lesion-recuperada/<int:lesion_id>/', views.marcar_lesion_recuperada, name='marcar_lesion_recuperada'),
    path('test-recuperacion/<int:lesion_id>/', views.test_recuperacion, name='test_recuperacion'),

    # Strava integration
    path('strava/connect/',                         views.strava_connect,         name='strava_connect'),
    path('strava/callback/',                        views.strava_callback,        name='strava_callback'),
    path('strava/webhook/',                         views.strava_webhook,         name='strava_webhook'),
    path('strava/reconciliacion/',                  views.strava_reconciliacion,  name='strava_reconciliacion'),
    path('strava/procesar/<int:actividad_id>/',     views.strava_procesar,        name='strava_procesar'),
    path('strava/importar-recientes/',              views.strava_importar_recientes, name='strava_importar_recientes'),
]
