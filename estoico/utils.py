from django.utils import timezone
from django.db.models import Avg, Count
from datetime import datetime, timedelta
import json

from .models import (
    ContenidoDiario, ReflexionDiaria, LogroEstoico, LogroUsuario,
    EstadisticaUsuario, PerfilEstoico
)

def obtener_contenido_dia(dia=None):
    """
    Obtiene el contenido estoico para un día específico
    """
    if dia is None:
        dia = timezone.now().timetuple().tm_yday
    
    try:
        return ContenidoDiario.objects.get(dia=dia)
    except ContenidoDiario.DoesNotExist:
        return None

def verificar_logros(usuario):
    """
    Verifica y otorga logros al usuario basado en su progreso
    """
    estadisticas, _ = EstadisticaUsuario.objects.get_or_create(usuario=usuario)
    logros_otorgados = []
    
    # Obtener logros que el usuario no tiene
    logros_usuario_ids = LogroUsuario.objects.filter(usuario=usuario).values_list('logro_id', flat=True)
    logros_disponibles = LogroEstoico.objects.filter(activo=True).exclude(id__in=logros_usuario_ids)
    
    for logro in logros_disponibles:
        otorgar_logro = False
        
        if logro.tipo == 'dias_consecutivos':
            if estadisticas.racha_actual >= logro.criterio_valor:
                otorgar_logro = True
        
        elif logro.tipo == 'total_reflexiones':
            total_reflexiones = ReflexionDiaria.objects.filter(usuario=usuario).count()
            if total_reflexiones >= logro.criterio_valor:
                otorgar_logro = True
        
        elif logro.tipo == 'tema_completado':
            # Verificar si completó un tema específico (todos los días de un mes)
            temas_completados = verificar_temas_completados(usuario)
            if len(temas_completados) >= logro.criterio_valor:
                otorgar_logro = True
        
        elif logro.tipo == 'filosofo_explorado':
            # Verificar si exploró reflexiones de diferentes filósofos
            filosofos_explorados = ReflexionDiaria.objects.filter(
                usuario=usuario
            ).values_list('contenido_dia__autor', flat=True).distinct().count()
            if filosofos_explorados >= logro.criterio_valor:
                otorgar_logro = True
        
        elif logro.tipo == 'calidad_reflexion':
            # Verificar promedio de calificaciones
            promedio = ReflexionDiaria.objects.filter(
                usuario=usuario,
                calificacion_dia__isnull=False
            ).aggregate(promedio=Avg('calificacion_dia'))['promedio']
            if promedio and promedio >= logro.criterio_valor:
                otorgar_logro = True
        
        if otorgar_logro:
            LogroUsuario.objects.create(usuario=usuario, logro=logro)
            logros_otorgados.append(logro)
    
    return logros_otorgados

def calcular_estadisticas(usuario):
    """
    Calcula y actualiza las estadísticas del usuario
    """
    estadisticas, _ = EstadisticaUsuario.objects.get_or_create(usuario=usuario)
    
    # Calcular días activos
    dias_activos = ReflexionDiaria.objects.filter(usuario=usuario).count()
    
    # Calcular promedio de calificaciones
    promedio_calificacion = ReflexionDiaria.objects.filter(
        usuario=usuario,
        calificacion_dia__isnull=False
    ).aggregate(promedio=Avg('calificacion_dia'))['promedio'] or 0
    
    # Calcular tiempo total de reflexión
    tiempo_total = ReflexionDiaria.objects.filter(
        usuario=usuario
    ).aggregate(total=Count('tiempo_reflexion'))['total'] or 0
    
    # Calcular temas completados
    temas_completados = verificar_temas_completados(usuario)
    
    # Calcular filósofos explorados
    filosofos_explorados = list(ReflexionDiaria.objects.filter(
        usuario=usuario
    ).values_list('contenido_dia__autor', flat=True).distinct())
    
    # Actualizar estadísticas
    estadisticas.dias_activos = dias_activos
    estadisticas.promedio_calificacion = promedio_calificacion
    estadisticas.tiempo_total_reflexion = tiempo_total
    estadisticas.temas_completados = temas_completados
    estadisticas.filosofos_explorados = filosofos_explorados
    estadisticas.save()
    
    return estadisticas

def verificar_temas_completados(usuario):
    """
    Verifica qué temas mensuales ha completado el usuario
    """
    temas_completados = []
    
    # Obtener todos los temas únicos
    temas = ContenidoDiario.objects.values_list('tema', flat=True).distinct()
    
    for tema in temas:
        # Contar días del tema
        dias_tema = ContenidoDiario.objects.filter(tema=tema).count()
        
        # Contar reflexiones del usuario para este tema
        reflexiones_tema = ReflexionDiaria.objects.filter(
            usuario=usuario,
            contenido_dia__tema=tema
        ).count()
        
        # Si completó al menos 80% del tema, considerarlo completado
        if reflexiones_tema >= (dias_tema * 0.8):
            temas_completados.append(tema)
    
    return temas_completados

def obtener_racha_actual(usuario):
    """
    Calcula la racha actual de días consecutivos del usuario
    """
    hoy = timezone.now().date()
    racha = 0
    fecha_actual = hoy
    
    while True:
        reflexion = ReflexionDiaria.objects.filter(
            usuario=usuario,
            fecha=fecha_actual
        ).first()
        
        if reflexion:
            racha += 1
            fecha_actual -= timedelta(days=1)
        else:
            break
    
    return racha

def generar_reporte_progreso(usuario, periodo_dias=30):
    """
    Genera un reporte de progreso del usuario
    """
    fecha_inicio = timezone.now().date() - timedelta(days=periodo_dias)
    
    reflexiones = ReflexionDiaria.objects.filter(
        usuario=usuario,
        fecha__gte=fecha_inicio
    ).select_related('contenido_dia')
    
    # Datos por día
    datos_diarios = []
    for i in range(periodo_dias):
        fecha = fecha_inicio + timedelta(days=i)
        reflexion = reflexiones.filter(fecha=fecha).first()
        
        datos_diarios.append({
            'fecha': fecha,
            'activo': reflexion is not None,
            'calificacion': reflexion.calificacion_dia if reflexion else None,
            'tema': reflexion.contenido_dia.tema if reflexion else None,
            'autor': reflexion.contenido_dia.autor if reflexion else None,
        })
    
    # Estadísticas del período
    dias_activos = len([d for d in datos_diarios if d['activo']])
    calificaciones = [d['calificacion'] for d in datos_diarios if d['calificacion']]
    promedio_calificacion = sum(calificaciones) / len(calificaciones) if calificaciones else 0
    
    # Temas más frecuentes
    temas = [d['tema'] for d in datos_diarios if d['tema']]
    temas_frecuencia = {}
    for tema in temas:
        temas_frecuencia[tema] = temas_frecuencia.get(tema, 0) + 1
    
    # Autores más frecuentes
    autores = [d['autor'] for d in datos_diarios if d['autor']]
    autores_frecuencia = {}
    for autor in autores:
        autores_frecuencia[autor] = autores_frecuencia.get(autor, 0) + 1
    
    return {
        'periodo_dias': periodo_dias,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': timezone.now().date(),
        'dias_activos': dias_activos,
        'porcentaje_actividad': (dias_activos / periodo_dias) * 100,
        'promedio_calificacion': promedio_calificacion,
        'temas_frecuencia': temas_frecuencia,
        'autores_frecuencia': autores_frecuencia,
        'datos_diarios': datos_diarios,
    }

def cargar_contenido_inicial():
    """
    Carga el contenido inicial de los 366 días desde el archivo JSON
    """
    # Esta función se usaría para cargar el contenido desde el archivo JSON
    # que creamos anteriormente
    pass

def crear_logros_iniciales():
    """
    Crea los logros iniciales del sistema
    """
    logros_iniciales = [
        {
            'nombre': 'Primer Paso',
            'descripcion': 'Completa tu primera reflexión estoica',
            'tipo': 'total_reflexiones',
            'criterio_valor': 1,
            'icono': '🌱'
        },
        {
            'nombre': 'Constancia',
            'descripcion': 'Reflexiona durante 7 días consecutivos',
            'tipo': 'dias_consecutivos',
            'criterio_valor': 7,
            'icono': '🔥'
        },
        {
            'nombre': 'Dedicación',
            'descripcion': 'Reflexiona durante 30 días consecutivos',
            'tipo': 'dias_consecutivos',
            'criterio_valor': 30,
            'icono': '💪'
        },
        {
            'nombre': 'Maestría',
            'descripcion': 'Reflexiona durante 100 días consecutivos',
            'tipo': 'dias_consecutivos',
            'criterio_valor': 100,
            'icono': '👑'
        },
        {
            'nombre': 'Explorador',
            'descripcion': 'Lee reflexiones de 3 filósofos diferentes',
            'tipo': 'filosofo_explorado',
            'criterio_valor': 3,
            'icono': '🧭'
        },
        {
            'nombre': 'Sabio',
            'descripcion': 'Mantén un promedio de 4+ estrellas en tus días',
            'tipo': 'calidad_reflexion',
            'criterio_valor': 4,
            'icono': '🦉'
        },
        {
            'nombre': 'Completista',
            'descripcion': 'Completa un tema mensual completo',
            'tipo': 'tema_completado',
            'criterio_valor': 1,
            'icono': '📚'
        },
        {
            'nombre': 'Centurión',
            'descripcion': 'Completa 100 reflexiones en total',
            'tipo': 'total_reflexiones',
            'criterio_valor': 100,
            'icono': '🏛️'
        },
    ]
    
    for logro_data in logros_iniciales:
        LogroEstoico.objects.get_or_create(
            nombre=logro_data['nombre'],
            defaults=logro_data
        )

