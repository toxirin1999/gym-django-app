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
    path('procesar-con-ia/<int:session_id>/', views.procesar_con_ia, name='procesar_con_ia'),
    path('registrar-entrenamiento-ia/<int:session_id>/', views.registrar_entrenamiento_ia, name='registrar_entrenamiento_ia'),
    path('coach-chat/', views.CoachInteractionView.as_view(), name='coach_chat'),
    path('get-greeting/', views.GetGreetingView.as_view(), name='get_greeting'),
    path('reportar-lesion/', views.reportar_lesion, name='reportar_lesion'),
    path('reportar-recuperacion/<int:lesion_id>/', views.reportar_recuperacion, name='reportar_recuperacion'),
    path('marcar-lesion-recuperada/<int:lesion_id>/', views.marcar_lesion_recuperada, name='marcar_lesion_recuperada'),
    path('test-recuperacion/<int:lesion_id>/', views.test_recuperacion, name='test_recuperacion'),
]
