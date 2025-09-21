# logros/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.core.paginator import Paginator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

from clientes.models import Cliente
from .models import (
    PerfilGamificacion, Arquetipo, PruebaLegendaria, PruebaUsuario,
    Quest, QuestUsuario, HistorialPuntos, Notificacion, Liga,
    Temporada,
    RankingEntry
)
from .services import CodiceService, AnalisisGamificacionService


@login_required
def perfil_gamificacion(request, cliente_id=None):
    """Vista principal del Códice de las Leyendas"""

    if cliente_id:
        cliente = get_object_or_404(Cliente, id=cliente_id)
    else:
        # Si no se especifica cliente, mostrar el primero disponible o redirigir
        cliente = Cliente.objects.first()
        if not cliente:
            messages.error(request, "No hay clientes registrados.")
            return redirect('clientes:lista_clientes')

    # Obtener o crear el perfil de gamificación
    perfil, created = PerfilGamificacion.objects.get_or_create(
        cliente=cliente,
        defaults={'nivel_actual': Arquetipo.objects.order_by('nivel').first()}
    )

    if created:
        messages.info(request, f"Se ha creado el perfil de gamificación para {cliente.nombre}.")

    # Obtener todos los arquetipos para mostrar la progresión
    todos_arquetipos = Arquetipo.objects.all().order_by('nivel')
    nivel_actual = perfil.nivel_actual.nivel if perfil.nivel_actual else 1

    # Preparar datos del códice
    codice = []
    for arquetipo in todos_arquetipos:
        # Determinar si este capítulo está desbloqueado
        desbloqueado = arquetipo.nivel <= nivel_actual

        if desbloqueado:
            # Obtener las pruebas de este arquetipo
            pruebas = PruebaLegendaria.objects.filter(arquetipo=arquetipo)
            pruebas_usuario = PruebaUsuario.objects.filter(
                perfil=perfil,
                prueba__in=pruebas
            ).select_related('prueba')

            # Crear diccionario de progreso por prueba
            progreso_pruebas = {pu.prueba.id: pu for pu in pruebas_usuario}

            pruebas_data = []
            for prueba in pruebas:
                if not prueba.es_secreta or prueba.id in progreso_pruebas:
                    pu = progreso_pruebas.get(prueba.id)
                    if pu:
                        progreso_actual = pu.progreso_actual
                        completada = pu.completada
                    else:
                        progreso_actual = 0
                        completada = False

                    porcentaje = min((progreso_actual / prueba.meta_valor) * 100, 100) if prueba.meta_valor > 0 else 0

                    pruebas_data.append({
                        'prueba': prueba,
                        'progreso_actual': progreso_actual,
                        'completada': completada,
                        'porcentaje': porcentaje,
                        'es_secreta': prueba.es_secreta and not completada
                    })

            # Calcular si el capítulo está dominado
            total_pruebas = len(pruebas_data)
            pruebas_completadas = sum(1 for p in pruebas_data if p['completada'])
            dominado = total_pruebas > 0 and pruebas_completadas == total_pruebas

            codice.append({
                'arquetipo': arquetipo,
                'desbloqueado': True,
                'dominado': dominado,
                'pruebas': pruebas_data,
                'progreso_capitulo': (pruebas_completadas / total_pruebas * 100) if total_pruebas > 0 else 0
            })
        else:
            # Capítulo bloqueado
            codice.append({
                'arquetipo': arquetipo,
                'desbloqueado': False,
                'dominado': False,
                'pruebas': [],
                'progreso_capitulo': 0
            })

    # Calcular progreso hacia el siguiente nivel
    siguiente_arquetipo = Arquetipo.objects.filter(nivel__gt=nivel_actual).order_by('nivel').first()
    progreso_siguiente_nivel = 0
    puntos_necesarios = 0

    if siguiente_arquetipo:
        puntos_actuales = perfil.puntos_totales
        puntos_nivel_actual = perfil.nivel_actual.puntos_requeridos if perfil.nivel_actual else 0
        puntos_siguiente_nivel = siguiente_arquetipo.puntos_requeridos

        if puntos_siguiente_nivel > puntos_nivel_actual:
            progreso_siguiente_nivel = ((puntos_actuales - puntos_nivel_actual) /
                                        (puntos_siguiente_nivel - puntos_nivel_actual)) * 100
            progreso_siguiente_nivel = min(max(progreso_siguiente_nivel, 0), 100)
            puntos_necesarios = max(puntos_siguiente_nivel - puntos_actuales, 0)

    # Obtener historial reciente de puntos
    historial_reciente = HistorialPuntos.objects.filter(
        perfil=perfil
    ).order_by('-fecha')[:10]

    # Obtener notificaciones no leídas
    notificaciones_no_leidas = Notificacion.objects.filter(
        perfil=perfil,
        leida=False
    ).order_by('-fecha_creacion')[:5]

    # Obtener quests activas (mantenemos la funcionalidad original)
    quests_activas = QuestUsuario.objects.filter(
        perfil=perfil,
        completada=False,
        quest__activa=True
    ).select_related('quest')[:5]

    context = {
        'cliente': cliente,
        'perfil': perfil,
        'codice': codice,
        'siguiente_arquetipo': siguiente_arquetipo,
        'progreso_siguiente_nivel': progreso_siguiente_nivel,
        'puntos_necesarios': puntos_necesarios,
        'historial_reciente': historial_reciente,
        'notificaciones_no_leidas': notificaciones_no_leidas,
        'quests_activas': quests_activas,
        'todos_los_clientes': Cliente.objects.all(),
    }

    return render(request, 'logros/perfil_gamificacion.html', context)


# logros/views.py

# logros/views.py

@login_required
def detalle_arquetipo(request, cliente_id, arquetipo_nivel):
    """Vista detallada y robusta de un arquetipo específico."""

    # SIN try...except para poder ver los errores reales

    cliente = get_object_or_404(Cliente, id=cliente_id)
    arquetipo = get_object_or_404(Arquetipo, nivel=arquetipo_nivel)
    perfil = PerfilGamificacion.objects.filter(cliente=cliente).first()

    arquetipo_anterior = Arquetipo.objects.filter(nivel=arquetipo.nivel - 1).first()
    arquetipo_siguiente = Arquetipo.objects.filter(nivel=arquetipo.nivel + 1).first()

    pruebas_arquetipo = list(PruebaLegendaria.objects.filter(arquetipo=arquetipo))

    context = {
        'cliente': cliente,
        'perfil': perfil,
        'arquetipo': arquetipo,
        'pruebas_arquetipo': pruebas_arquetipo,
        'arquetipo_anterior': arquetipo_anterior,
        'arquetipo_siguiente': arquetipo_siguiente,
        'es_desbloqueado': False,
        'fecha_desbloqueo': None,
        'tiempo_en_nivel': "Bloqueado",
        'pruebas_completadas_nivel': 0,
        'records_en_nivel': 0,
    }

    if perfil and perfil.nivel_actual and arquetipo.nivel <= perfil.nivel_actual.nivel:
        context['es_desbloqueado'] = True

        pruebas_completadas_ids = set(PruebaUsuario.objects.filter(
            perfil=perfil,
            prueba__in=pruebas_arquetipo,
            completada=True
        ).values_list('prueba_id', flat=True))

        for prueba in context['pruebas_arquetipo']:
            prueba.completada = prueba.id in pruebas_completadas_ids

        context['pruebas_completadas_nivel'] = len(pruebas_completadas_ids)
        context['fecha_desbloqueo'] = perfil.fecha_actualizacion
        dias_en_nivel = (timezone.now() - perfil.fecha_actualizacion).days
        context['tiempo_en_nivel'] = f"{dias_en_nivel} día{'s' if dias_en_nivel != 1 else ''}"

    # MUY IMPORTANTE: Asegúrate de que el nombre del template sea el correcto.
    return render(request, 'logros/arquetipo_detalle.html', context)


@login_required
def lista_arquetipos(request):
    """Lista todos los arquetipos disponibles"""
    arquetipos = Arquetipo.objects.all().order_by('nivel')

    context = {
        'arquetipos': arquetipos,
    }

    return render(request, 'logros/lista_arquetipos.html', context)


@login_required
def lista_pruebas_legendarias(request):
    """Lista todas las pruebas legendarias disponibles"""
    pruebas = PruebaLegendaria.objects.all().select_related('arquetipo').order_by('arquetipo__nivel', 'nombre')

    # Filtros
    arquetipo_id = request.GET.get('arquetipo')
    if arquetipo_id:
        pruebas = pruebas.filter(arquetipo__nivel=arquetipo_id)

    mostrar_secretas = request.GET.get('secretas') == 'true'
    if not mostrar_secretas:
        pruebas = pruebas.filter(es_secreta=False)

    # Paginación
    paginator = Paginator(pruebas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'arquetipos': Arquetipo.objects.all().order_by('nivel'),
        'arquetipo_seleccionado': arquetipo_id,
        'mostrar_secretas': mostrar_secretas,
    }

    return render(request, 'logros/lista_pruebas_legendarias.html', context)


@login_required
def ranking_clientes(request):
    """Ranking de clientes por puntos totales"""
    perfiles = PerfilGamificacion.objects.select_related(
        'cliente', 'nivel_actual'
    ).order_by('-puntos_totales')

    # Añadir posición en el ranking
    for i, perfil in enumerate(perfiles, 1):
        perfil.posicion = i

    context = {
        'perfiles': perfiles,
    }

    return render(request, 'logros/ranking_clientes.html', context)


@login_required
def procesar_entreno(request, entreno_id):
    """Procesa manualmente la gamificación de un entrenamiento"""
    from entrenos.models import EntrenoRealizado

    entreno = get_object_or_404(EntrenoRealizado, id=entreno_id)

    try:
        resultado = CodiceService.procesar_entreno_completo(entreno)

        mensaje = f"Entrenamiento procesado exitosamente. "
        if resultado['pruebas_completadas']:
            mensaje += f"Pruebas completadas: {len(resultado['pruebas_completadas'])}. "
        if resultado['nivel_subido']:
            mensaje += "¡Nivel subido! "
        mensaje += f"Puntos totales: {resultado['puntos_totales']}"

        messages.success(request, mensaje)

    except Exception as e:
        messages.error(request, f"Error al procesar el entrenamiento: {str(e)}")

    return redirect('logros:perfil_gamificacion', cliente_id=entreno.cliente.id)


# --------------------------------------------------------------------------
# VISTAS DE ANÁLISIS (MANTIENEN LA FUNCIONALIDAD ORIGINAL)
# --------------------------------------------------------------------------

@login_required
def analisis_cliente(request, cliente_id):
    """Análisis de gamificación para un cliente específico"""
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Obtener período de análisis
    dias = int(request.GET.get('dias', 30))

    # Generar análisis
    analisis = AnalisisGamificacionService.analizar_cliente(cliente, dias)

    context = {
        'cliente': cliente,
        'analisis': analisis,
        'dias': dias,
    }

    return render(request, 'logros/analisis_cliente.html', context)


@login_required
def analisis_global(request):
    """Análisis global de gamificación"""
    dias = int(request.GET.get('dias', 30))
    fecha_inicio = timezone.now() - timedelta(days=dias)

    # Estadísticas generales
    total_perfiles = PerfilGamificacion.objects.count()
    total_puntos = PerfilGamificacion.objects.aggregate(
        total=Sum('puntos_totales')
    )['total'] or 0

    # Pruebas completadas en el período
    pruebas_completadas = PruebaUsuario.objects.filter(
        completada=True,
        fecha_completada__gte=fecha_inicio
    ).count()

    # Top 10 clientes
    top_clientes = PerfilGamificacion.objects.select_related(
        'cliente', 'nivel_actual'
    ).order_by('-puntos_totales')[:10]

    context = {
        'dias': dias,
        'total_perfiles': total_perfiles,
        'total_puntos': total_puntos,
        'pruebas_completadas': pruebas_completadas,
        'top_clientes': top_clientes,
    }

    return render(request, 'logros/analisis_global.html', context)


# --------------------------------------------------------------------------
# VISTAS DE NOTIFICACIONES
# --------------------------------------------------------------------------

@login_required
def listar_notificaciones(request, cliente_id):
    """Lista las notificaciones de un cliente"""
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        perfil = PerfilGamificacion.objects.get(cliente=cliente)
    except PerfilGamificacion.DoesNotExist:
        messages.error(request, "El cliente no tiene un perfil de gamificación.")
        return redirect('logros:perfil_gamificacion', cliente_id=cliente_id)

    notificaciones = Notificacion.objects.filter(
        perfil=perfil
    ).order_by('-fecha_creacion')

    # Paginación
    paginator = Paginator(notificaciones, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'cliente': cliente,
        'perfil': perfil,
        'page_obj': page_obj,
    }

    return render(request, 'logros/notificaciones.html', context)


@login_required
def marcar_notificacion_leida(request, notificacion_id):
    """Marca una notificación como leída"""
    if request.method == 'POST':
        notificacion = get_object_or_404(Notificacion, id=notificacion_id)
        notificacion.leida = True
        notificacion.save()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False})


@login_required
def obtener_notificaciones_ajax(request, cliente_id):
    """Obtiene las notificaciones no leídas de un cliente vía AJAX"""
    cliente = get_object_or_404(Cliente, id=cliente_id)

    try:
        perfil = PerfilGamificacion.objects.get(cliente=cliente)
    except PerfilGamificacion.DoesNotExist:
        return JsonResponse({'notificaciones': []})

    notificaciones = Notificacion.objects.filter(
        perfil=perfil,
        leida=False
    ).order_by('-fecha_creacion')[:10]

    data = []
    for notif in notificaciones:
        data.append({
            'id': notif.id,
            'tipo': notif.tipo,
            'titulo': notif.titulo,
            'mensaje': notif.mensaje,
            'fecha': notif.fecha_creacion.strftime('%d/%m/%Y %H:%M')
        })

    return JsonResponse({'notificaciones': data})


# --------------------------------------------------------------------------
# VISTAS DE QUESTS (MANTIENEN LA FUNCIONALIDAD ORIGINAL)
# --------------------------------------------------------------------------

@login_required
def lista_misiones(request):
    """Lista todas las misiones disponibles"""
    misiones = Quest.objects.filter(activa=True).order_by('periodo', 'nombre')

    context = {
        'misiones': misiones,
    }

    return render(request, 'logros/lista_misiones.html', context)


@login_required
def detalle_mision(request, mision_id):
    """Detalle de una misión específica"""
    mision = get_object_or_404(Quest, id=mision_id)

    context = {
        'mision': mision,
    }

    return render(request, 'logros/detalle_mision.html', context)


# --------------------------------------------------------------------------
# EXPORTACIÓN A PDF
# --------------------------------------------------------------------------

@login_required
def exportar_analisis_cliente_pdf(request, cliente_id):
    """Exporta el análisis de un cliente a PDF"""
    cliente = get_object_or_404(Cliente, id=cliente_id)
    dias = int(request.GET.get('dias', 30))

    # Generar análisis
    analisis = AnalisisGamificacionService.analizar_cliente(cliente, dias)

    # Crear PDF
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    # Título
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"Análisis de Gamificación - {cliente.nombre}")

    # Contenido básico
    p.setFont("Helvetica", 12)
    y = 700

    if analisis['perfil']:
        p.drawString(100, y, f"Puntos totales: {analisis['perfil'].puntos_totales}")
        y -= 20
        p.drawString(100, y, f"Nivel actual: {analisis['nivel_actual']}")
        y -= 20
        p.drawString(100, y, f"Racha actual: {analisis['racha_actual']} días")
        y -= 20
        p.drawString(100, y, f"Puntos en los últimos {dias} días: {analisis['puntos_periodo']}")
    else:
        p.drawString(100, y, "El cliente no tiene datos de gamificación.")

    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="analisis_{cliente.nombre}_{dias}dias.pdf"'

    return response


from django.db.models import Sum, Count, F
from datetime import datetime, timedelta


def leaderboard_view(request):
    """
    Vista principal del leaderboard épico
    """
    # Obtener tipo de ranking solicitado
    tipo_ranking = request.GET.get('tipo', 'puntos_totales')

    # Obtener temporada actual
    temporada_actual = Temporada.objects.filter(activa=True).first()
    if not temporada_actual:
        # Crear temporada si no existe
        temporada_actual = RankingService.crear_temporada_actual()

    # Actualizar rankings
    RankingService.actualizar_rankings()

    # Obtener rankings para el tipo seleccionado
    rankings = RankingEntry.objects.filter(
        temporada=temporada_actual,
        tipo_ranking=tipo_ranking
    ).select_related('perfil__cliente').order_by('posicion')[:50]

    # Obtener top 3 para el podio
    top_3 = rankings[:3]

    # Obtener todas las ligas
    ligas = Liga.objects.all().order_by('puntos_minimos')

    # Obtener posición del usuario actual (si está logueado)
    posicion_usuario = None
    liga_usuario = None
    if request.user.is_authenticated and hasattr(request.user, 'cliente'):
        try:
            perfil = PerfilGamificacion.objects.get(cliente=request.user.cliente)
            posicion_usuario = RankingEntry.objects.filter(
                perfil=perfil,
                temporada=temporada_actual,
                tipo_ranking=tipo_ranking
            ).first()
            liga_usuario = RankingService.obtener_liga_usuario(perfil)
        except PerfilGamificacion.DoesNotExist:
            pass

    # Calcular estadísticas generales
    total_participantes = PerfilGamificacion.objects.count()

    # Contar entrenamientos totales
    from entrenos.models import EntrenoRealizado
    total_entrenamientos = EntrenoRealizado.objects.count()

    # Calcular volumen total
    from entrenos.models import EjercicioRealizado
    volumen_total = EjercicioRealizado.objects.filter(
        completado=True
    ).aggregate(
        total=Sum(F('peso_kg') * F('series') * F('repeticiones'))
    )['total'] or 0

    context = {
        'rankings': rankings,
        'top_3': top_3,
        'tipo_actual': tipo_ranking,
        'temporada': temporada_actual,
        'ligas': ligas,
        'posicion_usuario': posicion_usuario,
        'liga_usuario': liga_usuario,
        'total_participantes': total_participantes,
        'total_entrenamientos': total_entrenamientos,
        'volumen_total': volumen_total,
    }

    return render(request, 'logros/leaderboard.html', context)


# CLASE DE SERVICIO PARA RANKINGS
class RankingService:
    """
    Servicio principal para manejar rankings y leaderboards
    """

    @staticmethod
    def crear_temporada_actual():
        """
        Crea la temporada mensual actual si no existe
        """
        from django.utils import timezone
        from datetime import timedelta

        ahora = timezone.now()
        inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Calcular fin de mes
        if inicio_mes.month == 12:
            fin_mes = inicio_mes.replace(year=inicio_mes.year + 1, month=1) - timedelta(seconds=1)
        else:
            fin_mes = inicio_mes.replace(month=inicio_mes.month + 1) - timedelta(seconds=1)

        temporada, created = Temporada.objects.get_or_create(
            tipo='mensual',
            fecha_inicio__year=inicio_mes.year,
            fecha_inicio__month=inicio_mes.month,
            defaults={
                'nombre': f'Temporada {inicio_mes.strftime("%B %Y")}',
                'fecha_inicio': inicio_mes,
                'fecha_fin': fin_mes,
                'activa': True,
                'descripcion': f'Competencia mensual de {inicio_mes.strftime("%B %Y")}',
                'premio_descripcion': 'Reconocimiento especial y puntos bonus'
            }
        )

        return temporada

    @staticmethod
    def actualizar_rankings():
        """
        Actualiza todos los rankings para la temporada actual
        """
        temporada = RankingService.crear_temporada_actual()

        # Obtener todos los perfiles activos
        perfiles = PerfilGamificacion.objects.select_related('cliente').all()

        # Actualizar cada tipo de ranking
        tipos_ranking = [
            'puntos_totales',
            'entrenamientos_mes',
            'racha_actual',
            'volumen_total',
            'pruebas_completadas',
            'nivel_arquetipo'
        ]

        for tipo in tipos_ranking:
            RankingService._actualizar_ranking_especifico(temporada, tipo, perfiles)

    @staticmethod
    def _actualizar_ranking_especifico(temporada, tipo_ranking, perfiles):
        """
        Actualiza un tipo específico de ranking
        """
        # Calcular valores para cada perfil
        datos_ranking = []

        for perfil in perfiles:
            valor = RankingService._calcular_valor_ranking(perfil, tipo_ranking, temporada)
            if valor is not None:
                datos_ranking.append({
                    'perfil': perfil,
                    'valor': valor
                })

        # Ordenar por valor (descendente)
        datos_ranking.sort(key=lambda x: x['valor'], reverse=True)

        # Actualizar posiciones
        for posicion, datos in enumerate(datos_ranking, 1):
            RankingEntry.objects.update_or_create(
                perfil=datos['perfil'],
                temporada=temporada,
                tipo_ranking=tipo_ranking,
                defaults={
                    'valor': datos['valor'],
                    'posicion': posicion
                }
            )

    @staticmethod
    def _calcular_valor_ranking(perfil, tipo_ranking, temporada):
        """
        Calcula el valor específico para un tipo de ranking
        """
        try:
            if tipo_ranking == 'puntos_totales':
                return perfil.puntos_totales or 0

            # --- CORRECCIÓN 1 ---
            # El campo se llama 'racha_actual', no 'racha_dias_consecutivos'.
            elif tipo_ranking == 'racha_actual':
                return perfil.racha_actual or 0

            # --- CORRECCIÓN 2 ---
            # 'perfil.nivel_actual' ya es el objeto Arquetipo. No necesitamos buscarlo de nuevo.
            # Y el campo se llama 'titulo_arquetipo', no 'titulo'.
            elif tipo_ranking == 'nivel_arquetipo':
                if perfil.nivel_actual:
                    # Simplemente accedemos a los puntos del arquetipo que ya tenemos.
                    return perfil.nivel_actual.puntos_requeridos or 0
                return 0

            elif tipo_ranking == 'entrenamientos_mes':
                # Contar entrenamientos en el mes actual
                inicio_mes = temporada.fecha_inicio
                fin_mes = temporada.fecha_fin

                # La importación ya debería estar al principio del archivo, pero la dejamos por seguridad.
                from entrenos.models import EntrenoRealizado
                count = EntrenoRealizado.objects.filter(
                    cliente=perfil.cliente,
                    fecha__range=[inicio_mes.date(), fin_mes.date()]
                ).count()
                return count

            elif tipo_ranking == 'volumen_total':
                # Calcular volumen total levantado
                # La importación ya debería estar al principio del archivo.
                from entrenos.models import EjercicioRealizado
                total = EjercicioRealizado.objects.filter(
                    entreno__cliente=perfil.cliente,
                    completado=True
                ).aggregate(
                    # Importante: F y Sum deben venir de django.db.models
                    total=Sum(F('peso_kg') * F('series') * F('repeticiones'))
                )['total'] or 0
                return total

            elif tipo_ranking == 'pruebas_completadas':
                # La importación ya debería estar al principio del archivo.
                from .models import PruebaUsuario
                count = PruebaUsuario.objects.filter(
                    perfil=perfil,
                    completada=True
                ).count()
                return count

            else:
                return 0

        except Exception as e:
            # Este print es muy útil para depurar, como acabamos de ver.
            print(f"Error calculando {tipo_ranking} para {perfil.cliente.nombre}: {e}")
            return 0

    @staticmethod
    def obtener_liga_usuario(perfil):
        """
        Determina la liga del usuario basada en sus puntos
        """
        puntos = perfil.puntos_totales or 0

        liga = Liga.objects.filter(
            puntos_minimos__lte=puntos,
            puntos_maximos__gte=puntos
        ).first()

        return liga or Liga.objects.filter(nombre='bronce').first()


# Vista para el template "Ver Códice" completo
# Añadir esta función a logros/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from clientes.models import Cliente
from .models import PerfilGamificacion, Arquetipo, PruebaLegendaria, PruebaUsuario
from .services import CodiceService
import logging

logger = logging.getLogger(__name__)


# logros/views.py

# ... (tus otras importaciones y vistas) ...

@login_required
def ver_codice_completo(request, cliente_id):
    """
    Vista principal para mostrar el Códice de las Leyendas completo
    """
    # try:  # <--- LÍNEA COMENTADA
    # Obtener cliente
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Obtener o crear perfil de gamificación
    perfil, created = PerfilGamificacion.objects.get_or_create(
        cliente=cliente,
        defaults={
            'puntos_totales': 0,
            'racha_actual': 0,
            'entrenamientos_totales': 0,
            'records_totales': 0
        }
    )

    # Si es un perfil nuevo, asignar el primer arquetipo
    if created or not hasattr(perfil, 'nivel_actual') or not perfil.nivel_actual:
        primer_arquetipo = Arquetipo.objects.filter(nivel=1).first()
        if primer_arquetipo:
            perfil.nivel_actual = primer_arquetipo
            perfil.save()

    # Obtener datos del perfil
    nivel_actual = perfil.nivel_actual
    siguiente_nivel = Arquetipo.objects.filter(nivel=nivel_actual.nivel + 1).first() if nivel_actual else None
    puntos_ganados_en_nivel = 0
    puntos_totales_del_nivel = 0
    puntos_faltantes = 0
    porcentaje_progreso = 100
    # Calcular progreso hacia siguiente nivel
    if siguiente_nivel and nivel_actual:
        # Definimos las variables ANTES de usarlas
        puntos_base_nivel_actual = nivel_actual.puntos_requeridos
        puntos_meta_siguiente_nivel = siguiente_nivel.puntos_requeridos

        # Puntos que el usuario ha conseguido desde que empezó este nivel
        puntos_ganados_en_nivel = perfil.puntos_totales - puntos_base_nivel_actual

        # Total de puntos necesarios para pasar de este nivel al siguiente
        puntos_totales_del_nivel = puntos_meta_siguiente_nivel - puntos_base_nivel_actual

        # Puntos que le faltan para subir
        puntos_faltantes = max(0, puntos_meta_siguiente_nivel - perfil.puntos_totales)

        # Cálculo del porcentaje (opcional, pero útil tenerlo aquí)
        if puntos_totales_del_nivel > 0:
            porcentaje_progreso = min(100, (puntos_ganados_en_nivel / puntos_totales_del_nivel) * 100)
        else:
            porcentaje_progreso = 100 if puntos_ganados_en_nivel >= 0 else 0

        # Asegurarnos de que los valores no sean negativos
    puntos_ganados_en_nivel = max(0, puntos_ganados_en_nivel)
    puntos_totales_del_nivel = max(0, puntos_totales_del_nivel)
    # Obtener todos los arquetipos
    arquetipos = Arquetipo.objects.all().order_by('nivel')
    pruebas_activas = []
    if nivel_actual:
        pruebas_nivel_actual = PruebaLegendaria.objects.filter(arquetipo=nivel_actual)
        for prueba in pruebas_nivel_actual:
            if not PruebaUsuario.objects.filter(perfil=perfil, prueba=prueba, completada=True).exists():
                prueba.progreso_actual = calcular_progreso_prueba(perfil, prueba)
                pruebas_activas.append(prueba)

    todas_las_pruebas = []
    for arquetipo_loop in arquetipos:
        pruebas_arquetipo = PruebaLegendaria.objects.filter(arquetipo=arquetipo_loop)
        for prueba in pruebas_arquetipo:
            prueba.completada = PruebaUsuario.objects.filter(perfil=perfil, prueba=prueba, completada=True).exists()
            prueba.disponible = arquetipo_loop.nivel <= (nivel_actual.nivel if nivel_actual else 0)
            if prueba.disponible and not prueba.completada:
                prueba.progreso_actual = calcular_progreso_prueba(perfil, prueba)
            else:
                prueba.progreso_actual = prueba.meta_valor if prueba.completada else 0
            todas_las_pruebas.append(prueba)

    entrenamientos_totales = perfil.entrenos_totales
    pruebas_completadas = PruebaUsuario.objects.filter(perfil=perfil, completada=True).count()

    # Obtener todas las pruebas para la sección de pruebas
    todas_las_pruebas = []
    for arquetipo in arquetipos:
        pruebas_arquetipo = PruebaLegendaria.objects.filter(arquetipo=arquetipo)

        for prueba in pruebas_arquetipo:
            # Verificar si está completada
            prueba_usuario = PruebaUsuario.objects.filter(
                perfil=perfil,
                prueba=prueba,
                completada=True
            ).first()

            prueba.completada = bool(prueba_usuario)
            # --- POSIBLE PUNTO DE ERROR ---
            # Si nivel_actual es None, esto dará un AttributeError
            prueba.disponible = arquetipo.nivel <= nivel_actual.nivel if nivel_actual else False

            # Calcular progreso si está disponible y no completada
            if prueba.disponible and not prueba.completada:
                progreso_actual = calcular_progreso_prueba(perfil, prueba)
                prueba.progreso_actual = progreso_actual
                prueba.progreso_porcentaje = min(100, (
                        progreso_actual / prueba.meta_valor) * 100) if prueba.meta_valor > 0 else 0
            else:
                prueba.progreso_actual = prueba.meta_valor if prueba.completada else 0
                prueba.progreso_porcentaje = 100 if prueba.completada else 0

            todas_las_pruebas.append(prueba)

    # Estadísticas adicionales
    entrenamientos_totales = perfil.entrenos_totales
    pruebas_completadas = PruebaUsuario.objects.filter(perfil=perfil, completada=True).count()

    context = {
        'cliente': cliente,
        'perfil': perfil,
        'nivel_actual': nivel_actual,
        'siguiente_nivel': siguiente_nivel,
        'puntos_faltantes': puntos_faltantes,
        'porcentaje_progreso': round(porcentaje_progreso, 1),
        'arquetipos': arquetipos,
        'pruebas_activas': pruebas_activas,
        'todas_las_pruebas': todas_las_pruebas,
        'entrenamientos_totales': entrenamientos_totales,
        'pruebas_completadas': pruebas_completadas,
        'puntos_ganados_en_nivel': puntos_ganados_en_nivel,
        'puntos_totales_del_nivel': puntos_totales_del_nivel,
        'porcentaje_progreso': round(porcentaje_progreso, 1),

    }

    return render(request, 'logros/ver_codice_completo.html', context)

    # except Exception as e: # <--- LÍNEA COMENTADA
    #     logger.error(f"Error en ver_codice_completo para cliente {cliente_id}: {e}") # <--- LÍNEA COMENTADA
    #     return render(request, 'logros/error.html', { # <--- LÍNEA COMENTADA
    #         'error_message': 'Error al cargar el Códice de las Leyendas' # <--- LÍNEA COMENTADA
    #     }) # <--- LÍNEA COMENTADA


# ... (el resto de tus vistas) ...


def calcular_progreso_prueba(perfil, prueba):
    """
    Calcula el progreso actual de una prueba específica
    """
    try:
        clave = prueba.clave_calculo

        # Mapeo de claves de cálculo a valores del perfil
        if 'primer_entrenamiento' in clave:
            return 1 if perfil.entrenamientos_totales > 0 else 0

        elif 'entrenos_completados' in clave:
            return perfil.entrenamientos_totales

        elif 'racha_dias' in clave:
            return perfil.racha_actual

        elif 'records_totales' in clave:
            return perfil.records_totales

        elif 'volumen_total' in clave:
            # Esto requeriría acceso a los datos de entrenamientos
            # Por ahora retornamos un valor estimado
            return perfil.entrenamientos_totales * 1000  # Estimación básica

        elif 'rm_banca' in clave or 'rm_sentadilla' in clave or 'rm_pesomuerto' in clave:
            # Esto requeriría acceso a los récords específicos del cliente
            # Por ahora retornamos 0
            return 0

        elif 'ejercicios_dominados' in clave:
            # Esto requeriría análisis de los ejercicios realizados
            # Por ahora retornamos una estimación
            return min(perfil.entrenamientos_totales // 10, prueba.meta_valor)

        elif 'ranking_top' in clave:
            # Esto requeriría acceso al sistema de rankings
            return 0

        else:
            # Para claves no reconocidas, retornar 0
            return 0

    except Exception as e:
        logger.error(f"Error calculando progreso para prueba {prueba.nombre}: {e}")
        return 0


@login_required
def gamificacion_resumen_json(request, cliente_id):
    """
    Endpoint JSON para actualizar datos del Códice en tiempo real
    """
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        perfil = PerfilGamificacion.objects.filter(cliente=cliente).first()

        if not perfil:
            return JsonResponse({
                'tiene_perfil': False,
                'error': 'Perfil de gamificación no encontrado'
            })

        nivel_actual = perfil.nivel_actual
        siguiente_nivel = Arquetipo.objects.filter(nivel=nivel_actual.nivel + 1).first() if nivel_actual else None

        if siguiente_nivel:
            porcentaje_progreso = min(100, (perfil.puntos_totales / siguiente_nivel.puntos_requeridos) * 100)
        else:
            porcentaje_progreso = 100

        data = {
            'tiene_perfil': True,
            'nivel_actual': nivel_actual.titulo_arquetipo if nivel_actual else 'Sin nivel',
            'puntos_actuales': perfil.puntos_totales,
            'puntos_siguiente': siguiente_nivel.puntos_requeridos if siguiente_nivel else perfil.puntos_totales,
            'porcentaje_progreso': round(porcentaje_progreso, 1),
            'racha_actual': perfil.racha_actual,
            'entrenamientos_totales': perfil.entrenamientos_totales,
            'records_totales': perfil.records_totales,
        }

        return JsonResponse(data)

    except Exception as e:
        logger.error(f"Error en gamificacion_resumen_json para cliente {cliente_id}: {e}")
        return JsonResponse({
            'tiene_perfil': False,
            'error': str(e)
        })


# Vista para mostrar detalles de arquetipos individuales
# Añadir esta función a logros/views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from clientes.models import Cliente
from .models import PerfilGamificacion, Arquetipo, PruebaLegendaria, PruebaUsuario
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@login_required
def arquetipo_detalle(request, cliente_id, arquetipo_id):
    """
    Vista para mostrar los detalles completos de un arquetipo específico
    """
    try:
        # Obtener cliente y arquetipo
        cliente = get_object_or_404(Cliente, id=cliente_id)
        arquetipo = get_object_or_404(Arquetipo, id=arquetipo_id)

        # Obtener perfil de gamificación
        perfil = PerfilGamificacion.objects.filter(cliente=cliente).first()

        if not perfil:
            # Si no tiene perfil, solo puede ver el primer arquetipo
            if arquetipo.nivel != 1:
                raise Http404("Arquetipo no disponible")

            # Crear contexto básico para arquetipo no desbloqueado
            context = crear_contexto_basico(cliente, arquetipo)
            return render(request, 'logros/arquetipo_detalle.html', context)

        # Verificar si el arquetipo está desbloqueado
        nivel_actual = perfil.nivel_actual.nivel if perfil.nivel_actual else 0
        es_desbloqueado = arquetipo.nivel <= nivel_actual

        # Si el arquetipo no está desbloqueado, mostrar información limitada
        if not es_desbloqueado:
            context = crear_contexto_basico(cliente, arquetipo)
            context.update({
                'perfil': perfil,
                'es_desbloqueado': False,
                'mensaje_bloqueado': f"Necesitas alcanzar el nivel {arquetipo.nivel} para desbloquear este arquetipo."
            })
            return render(request, 'logros/arquetipo_detalle.html', context)

        # Arquetipo desbloqueado - mostrar información completa
        context = crear_contexto_completo(cliente, arquetipo, perfil)

        return render(request, 'logros/arquetipo_detalle.html', context)

    except Exception as e:
        logger.error(f"Error en arquetipo_detalle para cliente {cliente_id}, arquetipo {arquetipo_id}: {e}")
        return render(request, 'logros/error.html', {
            'error_message': 'Error al cargar los detalles del arquetipo'
        })


def crear_contexto_basico(cliente, arquetipo):
    """
    Crea el contexto básico para arquetipos (desbloqueados o no)
    """
    # Obtener arquetipo anterior y siguiente
    arquetipo_anterior = Arquetipo.objects.filter(nivel=arquetipo.nivel - 1).first()
    arquetipo_siguiente = Arquetipo.objects.filter(nivel=arquetipo.nivel + 1).first()

    # Obtener pruebas del arquetipo
    pruebas_arquetipo = PruebaLegendaria.objects.filter(arquetipo=arquetipo)

    context = {
        'cliente': cliente,
        'arquetipo': arquetipo,
        'arquetipo_anterior': arquetipo_anterior,
        'arquetipo_siguiente': arquetipo_siguiente,
        'pruebas_arquetipo': pruebas_arquetipo,
        'es_desbloqueado': False,
        'fecha_desbloqueo': None,
        'tiempo_en_nivel': None,
        'pruebas_completadas_nivel': 0,
        'records_en_nivel': 0,
    }

    return context


def crear_contexto_completo(cliente, arquetipo, perfil):
    """
    Crea el contexto completo para arquetipos desbloqueados
    """
    # Contexto básico
    context = crear_contexto_basico(cliente, arquetipo)

    # Información específica del progreso del usuario
    context.update({
        'perfil': perfil,
        'es_desbloqueado': True,
    })

    # Calcular fecha de desbloqueo
    fecha_desbloqueo = calcular_fecha_desbloqueo(perfil, arquetipo)
    context['fecha_desbloqueo'] = fecha_desbloqueo

    # Calcular tiempo en nivel
    tiempo_en_nivel = calcular_tiempo_en_nivel(perfil, arquetipo)
    context['tiempo_en_nivel'] = tiempo_en_nivel

    # Obtener pruebas completadas en este nivel
    pruebas_completadas = obtener_pruebas_completadas_nivel(perfil, arquetipo)
    context['pruebas_completadas_nivel'] = pruebas_completadas

    # Marcar pruebas como completadas en el contexto
    for prueba in context['pruebas_arquetipo']:
        prueba_usuario = PruebaUsuario.objects.filter(
            perfil=perfil,
            prueba=prueba,
            completada=True
        ).first()
        prueba.completada = bool(prueba_usuario)

    # Calcular récords establecidos en este nivel (estimación)
    records_en_nivel = calcular_records_en_nivel(perfil, arquetipo)
    context['records_en_nivel'] = records_en_nivel

    return context


def calcular_fecha_desbloqueo(perfil, arquetipo):
    """
    Calcula cuándo se desbloqueó este arquetipo
    """
    try:
        # Si es el arquetipo actual, usar la fecha de última actualización del perfil
        if perfil.nivel_actual and perfil.nivel_actual.id == arquetipo.id:
            return perfil.fecha_ultima_actualizacion if hasattr(perfil, 'fecha_ultima_actualizacion') else None

        # Para arquetipos anteriores, estimar basándose en el progreso
        # Esto es una estimación - en una implementación real, guardarías estas fechas
        if arquetipo.nivel < perfil.nivel_actual.nivel:
            # Estimar que cada nivel tomó aproximadamente 1-2 semanas
            dias_estimados = (perfil.nivel_actual.nivel - arquetipo.nivel) * 10
            fecha_estimada = datetime.now() - timedelta(days=dias_estimados)
            return fecha_estimada.date()

        return None

    except Exception as e:
        logger.error(f"Error calculando fecha de desbloqueo: {e}")
        return None


def calcular_tiempo_en_nivel(perfil, arquetipo):
    """
    Calcula cuánto tiempo estuvo el usuario en este nivel
    """
    try:
        # Si es el arquetipo actual
        if perfil.nivel_actual and perfil.nivel_actual.id == arquetipo.id:
            fecha_desbloqueo = calcular_fecha_desbloqueo(perfil, arquetipo)
            if fecha_desbloqueo:
                dias = (datetime.now().date() - fecha_desbloqueo).days
                if dias < 7:
                    return f"{dias} días"
                elif dias < 30:
                    semanas = dias // 7
                    return f"{semanas} semana{'s' if semanas != 1 else ''}"
                else:
                    meses = dias // 30
                    return f"{meses} mes{'es' if meses != 1 else ''}"
            return "Tiempo actual"

        # Para arquetipos anteriores, estimar duración
        if arquetipo.nivel < perfil.nivel_actual.nivel:
            # Estimación basada en la dificultad del nivel
            if arquetipo.nivel <= 10:
                return "1-2 semanas"
            elif arquetipo.nivel <= 30:
                return "2-3 semanas"
            elif arquetipo.nivel <= 50:
                return "3-4 semanas"
            else:
                return "1-2 meses"

        return None

    except Exception as e:
        logger.error(f"Error calculando tiempo en nivel: {e}")
        return None


def obtener_pruebas_completadas_nivel(perfil, arquetipo):
    """
    Obtiene el número de pruebas completadas en este nivel específico
    """
    try:
        pruebas_nivel = PruebaLegendaria.objects.filter(arquetipo=arquetipo)
        pruebas_completadas = PruebaUsuario.objects.filter(
            perfil=perfil,
            prueba__in=pruebas_nivel,
            completada=True
        ).count()

        return pruebas_completadas

    except Exception as e:
        logger.error(f"Error obteniendo pruebas completadas: {e}")
        return 0


def calcular_records_en_nivel(perfil, arquetipo):
    """
    Calcula los récords establecidos durante este nivel (estimación)
    """
    try:
        # Esta es una estimación - en una implementación real,
        # guardarías un historial de récords con fechas

        # Estimar basándose en el nivel y los récords totales
        if arquetipo.nivel <= 10:
            return min(perfil.records_totales // 4, 3)
        elif arquetipo.nivel <= 30:
            return min(perfil.records_totales // 3, 5)
        elif arquetipo.nivel <= 50:
            return min(perfil.records_totales // 2, 8)
        else:
            return min(perfil.records_totales, 10)

    except Exception as e:
        logger.error(f"Error calculando récords en nivel: {e}")
        return 0


# Función auxiliar para obtener estadísticas específicas del arquetipo
def obtener_estadisticas_arquetipo(arquetipo):
    """
    Obtiene las estadísticas de poder específicas del arquetipo
    """
    # Mapeo de arquetipos a estadísticas específicas
    stats_especificos = {
        1: {'fuerza': 60, 'velocidad': 70, 'tecnica': 50, 'resistencia': 80, 'determinacion': 100, 'poder_epico': 75},
        # Saitama
        2: {'fuerza': 75, 'velocidad': 95, 'tecnica': 85, 'resistencia': 90, 'determinacion': 100, 'poder_epico': 80},
        # Rock Lee
        3: {'fuerza': 70, 'velocidad': 80, 'tecnica': 60, 'resistencia': 75, 'determinacion': 85, 'poder_epico': 70},
        # Krillin
        21: {'fuerza': 95, 'velocidad': 90, 'tecnica': 85, 'resistencia': 88, 'determinacion': 95, 'poder_epico': 92},
        # Goku SSJ
        # Añadir más según necesites
    }

    # Estadísticas por defecto basadas en el nivel
    stats_default = {
        'fuerza': min(100, 50 + arquetipo.nivel),
        'velocidad': min(100, 45 + arquetipo.nivel),
        'tecnica': min(100, 40 + arquetipo.nivel),
        'resistencia': min(100, 55 + arquetipo.nivel),
        'determinacion': min(100, 60 + arquetipo.nivel),
        'poder_epico': min(100, 35 + arquetipo.nivel * 0.8)
    }

    return stats_especificos.get(arquetipo.nivel, stats_default)
