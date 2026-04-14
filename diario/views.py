from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import random
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta, date
import json
from .insights_engine import generar_insights_semanales
import calendar  # <-- ¡AÑADE ESTA LÍNEA!
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from .forms import PersonaImportanteForm, InteraccionForm, ProsocheHabitoForm
from .services import HabitosService

from .models import (
    ProsocheMes, ProsocheSemana, ProsocheDiario, ProsocheHabito, ProsocheHabitoDia,
    AreaVida, Eudaimonia, TrimestreEudaimonia,
    EjercicioArete, Gnosis, EntrenamientoSemanal,
    SeguimientoVires, EventoKairos, PlanificacionDiaria, PersonaImportante, Interaccion, RevisionSemanal,
    ReflexionLibre, ReflexionGuiadaTema, Virtud, Insignia,
    InsigniaUsuario, RachaEscritura
)

from .insights_engine import generar_insights_semanales

# ========================================
# VISTA PRINCIPAL DEL DIARIO (VERSIÓN FINAL Y COMPLETA)
# ========================================
# ========================================
# VISTA PRINCIPAL DEL DIARIO (VERSIÓN FREUD v2)
# ========================================
# Añade este código a tu views.py existente o reemplaza la función dashboard_diario

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta, date
from django.urls import reverse

from .models import (
    ProsocheMes, ProsocheSemana, ProsocheDiario, ProsocheHabito, ProsocheHabitoDia,
    AreaVida, Eudaimonia, TrimestreEudaimonia,
    EjercicioArete, Gnosis, EntrenamientoSemanal,
    SeguimientoVires, EventoKairos, PlanificacionDiaria, PersonaImportante, Interaccion, RevisionSemanal,
    ReflexionLibre, ReflexionGuiadaTema, Virtud, Insignia,
    InsigniaUsuario, RachaEscritura
)

from .insights_engine import generar_insights_semanales


@login_required
def dashboard_diario(request):
    """
    Dashboard principal del diario con diseño inspirado en freud v2.
    Versión simplificada y guiada para uso diario.
    """
    hoy = timezone.now().date()
    hora_actual = timezone.now().hour
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    # --- 1. LÓGICA DE LOS 6 PILARES ---
    mentalidad_activa = EjercicioArete.objects.filter(
        usuario=request.user,
        estado='completado',
        fecha_completado__range=[inicio_semana, fin_semana]
    ).exists()

    dominio_fisico_activo = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha__range=[inicio_semana, fin_semana],
        entrenamiento_realizado=True
    ).exists()

    brujula_activa = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha__range=[inicio_semana, fin_semana]
    ).exists()

    lazos_activos = Interaccion.objects.filter(
        usuario=request.user,
        fecha__range=[inicio_semana, fin_semana]
    ).exists()

    maestria_activa = brujula_activa  # Simplificación

    relatos_activos = Gnosis.objects.filter(
        usuario=request.user,
        estado='finalizado',
        fecha_fin__range=[inicio_semana, fin_semana]
    ).exists()

    pilares_status = [
        {'nombre': 'Mentalidad', 'icono': 'fas fa-shield-alt', 'activo': mentalidad_activa},
        {'nombre': 'Dominio Físico', 'icono': 'fas fa-dumbbell', 'activo': dominio_fisico_activo},
        {'nombre': 'Brújula Vital', 'icono': 'fas fa-compass', 'activo': brujula_activa},
        {'nombre': 'Lazos de Hierro', 'icono': 'fas fa-users', 'activo': lazos_activos},
        {'nombre': 'Maestría Personal', 'icono': 'fas fa-tasks', 'activo': maestria_activa},
        {'nombre': 'Relatos de Poder', 'icono': 'fas fa-book-open', 'activo': relatos_activos},
    ]

    # Contar pilares activos
    pilares_activos = sum(1 for p in pilares_status if p['activo'])

    # --- 2. DATOS PARA LOS WIDGETS ---
    entrada_hoy = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha=hoy
    ).select_related('prosoche_mes').first()

    seguimiento_vires_hoy = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha=hoy
    ).first()

    # --- 3. LÓGICA DEL "PRÓXIMO PASO" ---
    proximo_paso = None
    if not entrada_hoy:
        proximo_paso = {
            'titulo': '¿Cuál es tu propósito para hoy?',
            'descripcion': '"Una vida sin examen no merece ser vivida." Dedica un momento a la reflexión matutina.',
            'texto_boton': 'Crear Entrada',
            'url_boton': reverse('diario:prosoche_nueva_entrada'),
            'icono': 'fa-pen-nib'
        }
    elif hoy.weekday() in [0, 6]:  # Lunes o Domingo
        proximo_paso = {
            'titulo': 'Es hora de reflexionar',
            'descripcion': 'Revisa tus avances de la semana y establece nuevos objetivos.',
            'texto_boton': 'Revisión Semanal',
            'url_boton': reverse('diario:prosoche_revision_semanal'),
            'icono': 'fa-calendar-check'
        }
    elif not seguimiento_vires_hoy:
        proximo_paso = {
            'titulo': '¿Cómo te encuentras hoy?',
            'descripcion': 'Registra tus métricas de salud y bienestar.',
            'texto_boton': 'Registrar Vires',
            'url_boton': reverse('diario:vires_seguimiento_crear'),
            'icono': 'fa-heartbeat'
        }
    elif entrada_hoy and not entrada_hoy.felicidad:
        proximo_paso = {
            'titulo': 'Termina tu día con gratitud',
            'descripcion': 'Reflexiona sobre lo que ha ido bien y lo que has aprendido.',
            'texto_boton': 'Reflexión Nocturna',
            'url_boton': reverse('diario:prosoche_editar_entrada', args=[entrada_hoy.id]),
            'icono': 'fa-moon'
        }
    elif entrada_hoy:
        proximo_paso = {
            'titulo': 'Día en marcha',
            'descripcion': 'Recuerda tu foco principal para hoy:',
            'foco_del_dia': f'"{entrada_hoy.persona_quiero_ser}"' if entrada_hoy.persona_quiero_ser else '"Mantener el rumbo."',
            'texto_boton': 'Ver Entrada',
            'url_boton': reverse('diario:prosoche_editar_entrada', args=[entrada_hoy.id]),
            'icono': 'fa-bullseye'
        }
    else:
        proximo_paso = {
            'titulo': '¡Todo en orden!',
            'descripcion': 'Has completado tus tareas clave. Disfruta de tu tiempo.',
            'texto_boton': 'Explorar',
            'url_boton': reverse('diario:dashboard_diario'),
            'icono': 'fa-check-circle'
        }

    # --- 4. DATOS DE LA SEMANA ---
    dias_semana = []
    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    # Obtener entradas de la semana
    entradas_semana = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha__range=[inicio_semana, fin_semana]
    ).values_list('fecha', flat=True)
    entradas_set = set(entradas_semana)

    dias_completados_semana = 0

    for i in range(7):
        dia_fecha = inicio_semana + timedelta(days=i)
        completado = dia_fecha in entradas_set
        if completado:
            dias_completados_semana += 1

        dias_semana.append({
            'nombre_corto': nombres_dias[i],
            'numero': dia_fecha.day,
            'fecha': dia_fecha,
            'es_hoy': dia_fecha == hoy,
            'completado': completado,
        })

    # --- 5. RACHA Y ESTADÍSTICAS ---
    racha, _ = RachaEscritura.objects.get_or_create(usuario=request.user)

    # --- 6. VIRTUDES ---
    virtudes = Virtud.objects.filter(usuario=request.user).order_by('tipo')

    # --- 7. REFLEXIÓN DEL DÍA ---
    reflexion_del_dia = ReflexionGuiadaTema.objects.filter(
        activa=True,
        fecha_activacion=hoy
    ).first()

    if not reflexion_del_dia:
        reflexion_del_dia = ReflexionGuiadaTema.objects.filter(
            activa=True,
            fecha_activacion__month=hoy.month,
            fecha_activacion__day__lte=hoy.day
        ).order_by('-fecha_activacion').first()

    # --- 8. INSIGNIAS NUEVAS ---
    insignias_nuevas = InsigniaUsuario.objects.filter(
        usuario=request.user,
        vista=False
    ).select_related('insignia')

    # --- 9. CONTEXTO FINAL ---
    context = {
        'hoy': hoy,
        'pilares_status': pilares_status,
        'pilares_activos': pilares_activos,
        'proximo_paso': proximo_paso,
        'entrada_hoy': entrada_hoy,
        'seguimiento_vires_hoy': seguimiento_vires_hoy,
        'dias_semana': dias_semana,
        'dias_completados_semana': dias_completados_semana,
        'racha': racha,
        'virtudes': virtudes,
        'reflexion_del_dia': reflexion_del_dia,
        'insignias_nuevas': insignias_nuevas,
    }

    return render(request, 'diario/dashboard.html', context)


# --- NUEVA VISTA PARA GUARDAR ESTADO DE ÁNIMO RÁPIDO ---
@login_required
def guardar_estado_animo(request):
    """
    Guarda el estado de ánimo desde el selector rápido del dashboard.
    """
    if request.method == 'POST':
        estado_animo = request.POST.get('estado_animo')

        if estado_animo:
            hoy = timezone.now().date()
            mes_nombre = hoy.strftime('%B')
            año = hoy.year

            # Obtener o crear el mes
            prosoche_mes, _ = ProsocheMes.objects.get_or_create(
                usuario=request.user,
                mes=mes_nombre,
                año=año
            )

            # Obtener o crear la entrada del día
            entrada, created = ProsocheDiario.objects.get_or_create(
                prosoche_mes=prosoche_mes,
                fecha=hoy,
                defaults={'estado_animo': int(estado_animo)}
            )

            if not created:
                entrada.estado_animo = int(estado_animo)
                entrada.save()

            messages.success(request, '¡Estado de ánimo registrado!')

    return redirect('diario:dashboard_diario')


@login_required
def prosoche_entrada_form(request, entrada_id=None):
    entrada_existente = None
    if entrada_id:
        entrada_existente = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)
        prosoche_mes = entrada_existente.prosoche_mes
        fecha = entrada_existente.fecha
    else:
        fecha = timezone.now().date()
        mes_nombre = fecha.strftime('%B')
        año = fecha.year
        prosoche_mes, _ = ProsocheMes.objects.get_or_create(
            usuario=request.user, mes=mes_nombre, año=año
        )
        # Si ya hay entrada para hoy, editarla en vez de crear una nueva vacía
        entrada_existente = ProsocheDiario.objects.filter(
            prosoche_mes=prosoche_mes, fecha=fecha
        ).first()

    if request.method == 'POST':
        try:
            # La lógica POST es solo para guardar datos, no necesita la sugerencia.
            data = {
                'etiquetas': request.POST.get('etiquetas', ''),
                'estado_animo': int(request.POST.get('estado_animo', 3)),
                'persona_quiero_ser': request.POST.get('persona_quiero_ser', ''),
                'gratitud_1': request.POST.get('gratitud_1', ''),
                'gratitud_2': request.POST.get('gratitud_2', ''),
                'gratitud_3': request.POST.get('gratitud_3', ''),
                'gratitud_4': request.POST.get('gratitud_4', ''),
                'gratitud_5': request.POST.get('gratitud_5', ''),
                'podcast_libro_dia': request.POST.get('podcast_libro_dia', ''),
                'felicidad': request.POST.get('felicidad', ''),
                'que_ha_ido_bien': request.POST.get('que_ha_ido_bien', ''),
                'que_puedo_mejorar': request.POST.get('que_puedo_mejorar', ''),
                'reflexiones_dia': request.POST.get('reflexiones_dia', ''),
            }
            tareas_json = request.POST.get('tareas_dia', '[]')
            data['tareas_dia'] = json.loads(tareas_json)

            if entrada_existente:
                for key, value in data.items():
                    setattr(entrada_existente, key, value)
                entrada_existente.save()
                messages.success(request, 'Entrada actualizada correctamente.')
            else:
                data['prosoche_mes'] = prosoche_mes
                data['fecha'] = fecha
                ProsocheDiario.objects.create(**data)
                messages.success(request, 'Nueva entrada creada correctamente.')

            # Redirigimos a la URL correcta usando el namespace 'diario'
            return redirect('diario:prosoche_dashboard')

        except Exception as e:
            messages.error(request, f"Error al guardar la entrada: {e}")
            # Si hay un error, es mejor redirigir al dashboard para evitar bucles.
            return redirect('diario:prosoche_dashboard')

    # --- LÓGICA GET (Cuando se carga la página por primera vez) ---
    else:
        form_data = {}
        if entrada_existente:
            form_data = {
                'etiquetas': entrada_existente.etiquetas,
                'estado_animo': entrada_existente.estado_animo,
                'persona_quiero_ser': entrada_existente.persona_quiero_ser,
                'tareas_dia': entrada_existente.tareas_dia,
                'gratitud_1': entrada_existente.gratitud_1,
                'gratitud_2': entrada_existente.gratitud_2,
                'gratitud_3': entrada_existente.gratitud_3,
                'gratitud_4': entrada_existente.gratitud_4,
                'gratitud_5': entrada_existente.gratitud_5,
                'podcast_libro_dia': entrada_existente.podcast_libro_dia,
                'felicidad': entrada_existente.felicidad,
                'que_ha_ido_bien': entrada_existente.que_ha_ido_bien,
                'que_puedo_mejorar': entrada_existente.que_puedo_mejorar,
                'reflexiones_dia': entrada_existente.reflexiones_dia,
            }

        # ¡AQUÍ ES DONDE DEBE IR LA LÓGICA DE LA SUGERENCIA!
        sugerencias_de_reflexion = [
            "¿Qué mentira te has repetido tantas veces que la has acabado sintiendo como una verdad? Cuestiónala.",
            "¿Qué decisión importante estás postergando por miedo o comodidad? ¿Es imposible o solo incómodo?",
            "¿En qué área de tu vida estás dejando que la inercia decida por ti? ¿Qué pequeña acción consciente puedes tomar hoy para romperla?",
            "Sobre tu miedo más recurrente: ¿Cómo puedes actuar 'a pesar de él' hoy, aunque sea en algo pequeño?",
            "¿Qué significa para ti 'ser un buen hombre/mujer' hoy? ¿Qué acción específica te acerca a ese ideal?",
            "Piensa en una interacción reciente. ¿Cómo podrías haberla comunicado mejor, desde la perspectiva de 'estamos en el mismo equipo'?",
            "¿Qué acción de hoy, por pequeña que sea, refuerza la confianza que tienes en ti mismo?",
            "¿En qué situación de hoy has elegido la comodidad a corto plazo sabiendo que te aleja de tu 'yo' futuro? ¿Qué harás diferente mañana?",
            "¿Qué 'contrato' contigo mismo has roto recientemente? ¿Cómo puedes repararlo?",
            "¿Estás siendo un 'guerrero en un jardín' o un 'jardinero en una guerra'? ¿Cómo se ha manifestado hoy?",

            # Basadas en "Batman y Superman" (Identidad y Valores)
            "¿Qué 'máscara' has llevado hoy? ¿Qué parte de tu 'yo' verdadero has ocultado y por qué?",
            "Piensa en un héroe o referente que admires. ¿Qué cualidad suya podrías haber encarnado mejor hoy?",
            "¿Has actuado hoy desde el 'miedo' (tu Batman) o desde la 'esperanza' (tu Superman)? Describe un momento.",
            "¿Qué significa para ti 'ser un buen hombre/mujer' en el contexto de tu día de hoy? ¿En qué acción concreta se ha reflejado?",

            # Basadas en "Frena la Inercia" y "Decir que Sí"
            "¿Qué 'no' has dicho hoy por pura inercia o comodidad? ¿Era una renuncia necesaria o una oportunidad perdida?",
            "¿Qué decisión importante estás postergando? ¿Es realmente 'imposible' actuar o simplemente 'incómodo'?",
            "Describe una acción de hoy que no fue una elección consciente, sino producto de la inercia. ¿Cómo podrías introducir 'fricción consciente' ahí?",

            # Basadas en "Sesgos Cognitivos"
            "¿Qué opinión has defendido hoy? ¿Has buscado activamente una prueba que la contradiga (sesgo de confirmación)?",
            "Piensa en un juicio rápido que has hecho sobre alguien hoy. ¿Podría ser un 'efecto halo' o un 'sesgo de afinidad'?",
            "¿Qué 'historia' te has contado hoy para justificar una incoherencia entre tus creencias y tus acciones (disonancia cognitiva)?",

            # Basadas en "Miedo" y "Te vas a morir"
            "Sobre tu miedo más recurrente: ¿Cómo puedes actuar 'a pesar de él' mañana, aunque sea en algo pequeño?",
            "Si supieras que este es tu último mes de vida, ¿qué cambiaría en tu lista de tareas para mañana?",
            "¿Qué cosa buena que te ha pasado hoy has dado por sentada? Dedica un momento a sentir gratitud por ello."

        ]
        sugerencia_actual = random.choice(sugerencias_de_reflexion)

        context = {
            'fecha': fecha,
            'prosoche_mes': prosoche_mes,
            'form': type('Form', (), form_data)(),
            'entrada_existente': entrada_existente,
            'es_edicion': entrada_existente is not None,
            'sugerencia_reflexion': sugerencia_actual,  # ¡AHORA SÍ SE PASA!
        }

        return render(request, 'diario/prosoche_entrada_form.html', context)


@login_required
@require_http_methods(["POST"])  # Asegura que solo se pueda acceder por método POST
def prosoche_eliminar_entrada(request, entrada_id):
    """
    Elimina una entrada del diario.
    """
    # Busca la entrada asegurándose de que pertenece al usuario logueado
    entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)

    try:
        entrada.delete()
        messages.success(request, 'La entrada del diario ha sido eliminada correctamente.')
    except Exception as e:
        messages.error(request, f'Ocurrió un error al eliminar la entrada: {e}')

    return redirect('prosoche_dashboard')


@login_required
@require_http_methods(["POST"])
def prosoche_auto_save_entrada(request):
    """Vista para auto-guardado de entrada (AJAX)"""
    try:
        data = json.loads(request.body)
        fecha_str = data.get('fecha')
        campo = data.get('campo')
        valor = data.get('valor')

        if not all([fecha_str, campo]):
            return JsonResponse({'success': False, 'error': 'Datos incompletos'})

        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # Obtener o crear el mes de Prosoche
        mes_nombre = fecha.strftime('%B')
        año = fecha.year

        prosoche_mes, created = ProsocheMes.objects.get_or_create(
            usuario=request.user,
            mes=mes_nombre,
            año=año
        )

        # Obtener o crear la entrada
        entrada, created = ProsocheDiario.objects.get_or_create(
            prosoche_mes=prosoche_mes,
            fecha=fecha,
            defaults={'estado_animo': 3}
        )

        # Actualizar el campo específico
        if hasattr(entrada, campo):
            setattr(entrada, campo, valor)
            entrada.save()

            return JsonResponse({
                'success': True,
                'message': f'Campo {campo} guardado automáticamente'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Campo {campo} no válido'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def prosoche_entrada_detalle(request, entrada_id):
    """Vista para mostrar detalle de una entrada específica"""
    entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)

    context = {
        'entrada': entrada,
        'prosoche_mes': entrada.prosoche_mes,
        'tareas_completadas': entrada.get_tareas_completadas(),
        'total_tareas': entrada.get_total_tareas(),
        'gratitud_items': entrada.get_gratitud_items(),
        'porcentaje_completado': entrada.get_porcentaje_completado(),
    }

    return render(request, 'diario/prosoche_entrada_detalle.html', context)


@login_required
@require_http_methods(["POST"])
def prosoche_toggle_tarea(request):
    """Vista para marcar/desmarcar tarea como completada (AJAX)"""
    try:
        data = json.loads(request.body)
        entrada_id = data.get('entrada_id')
        tarea_index = data.get('tarea_index')
        completada = data.get('completada', False)

        entrada = get_object_or_404(ProsocheDiario, id=entrada_id, prosoche_mes__usuario=request.user)

        if 0 <= tarea_index < len(entrada.tareas_dia):
            entrada.tareas_dia[tarea_index]['completada'] = completada
            entrada.save()

            return JsonResponse({
                'success': True,
                'tareas_completadas': entrada.get_tareas_completadas(),
                'total_tareas': entrada.get_total_tareas()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Índice de tarea no válido'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def prosoche_entradas_mes(request, mes, año):
    """Vista para mostrar todas las entradas de un mes específico"""
    try:
        prosoche_mes = get_object_or_404(
            ProsocheMes,
            usuario=request.user,
            mes=mes,
            año=año
        )

        entradas = ProsocheDiario.objects.filter(
            prosoche_mes=prosoche_mes
        ).order_by('-fecha')

        context = {
            'prosoche_mes': prosoche_mes,
            'entradas': entradas,
            'mes': mes,
            'año': año,
        }

        return render(request, 'diario/prosoche_entradas_mes.html', context)

    except ProsocheMes.DoesNotExist:
        messages.error(request, f'No se encontraron datos para {mes} {año}')
        return redirect('prosoche_dashboard')


# Template filter personalizado para acceder a campos dinámicos
from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """Filtro para acceder a valores dinámicos en templates"""
    if hasattr(dictionary, key):
        return getattr(dictionary, key)
    return dictionary.get(key, '')


@register.filter
def add(value, arg):
    """Filtro para sumar valores"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value


@login_required
def eudaimonia_dashboard(request):
    """Dashboard de la sección Eudaimonia."""
    areas_usuario = Eudaimonia.objects.filter(usuario=request.user).select_related('area')

    # Organizar por prioridad
    areas_alta = areas_usuario.filter(prioridad='alta')
    areas_media = areas_usuario.filter(prioridad='media')
    areas_baja = areas_usuario.filter(prioridad='baja')

    context = {
        'areas_alta': areas_alta,
        'areas_media': areas_media,
        'areas_baja': areas_baja,
        'total_areas': areas_usuario.count()
    }
    return render(request, 'diario/eudaimonia_dashboard.html', context)


@login_required
def eudaimonia_area_detalle(request, area_id):
    """Detalle de un área de vida específica."""
    eudaimonia = get_object_or_404(Eudaimonia, id=area_id, usuario=request.user)
    trimestres = TrimestreEudaimonia.objects.filter(eudaimonia=eudaimonia).order_by('-año', '-trimestre')

    context = {
        'eudaimonia': eudaimonia,
        'trimestres': trimestres
    }
    return render(request, 'diario/eudaimonia_detalle.html', context)


@login_required
def eudaimonia_actualizar(request):
    """Actualizar puntuación y prioridad de un área de vida."""
    if request.method == 'POST':
        data = json.loads(request.body)
        eudaimonia = get_object_or_404(Eudaimonia, id=data['area_id'], usuario=request.user)

        if 'puntuacion' in data:
            eudaimonia.puntuacion = data['puntuacion']
        if 'prioridad' in data:
            eudaimonia.prioridad = data['prioridad']

        eudaimonia.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ========================================
# ARETÉ - DESARROLLO PERSONAL
# ========================================

# diario/views.py

# REEMPLAZA tu vista arete_dashboard con esta versión completa

# REEMPLAZA tu vista arete_dashboard con esta versión final y completa

@login_required
def arete_dashboard(request):
    """Dashboard de la sección Areté."""
    # Obtener todos los ejercicios del usuario para los cálculos totales
    todos_los_ejercicios = EjercicioArete.objects.filter(usuario=request.user).order_by('numero_orden')
    total_ejercicios = todos_los_ejercicios.count()
    completados = todos_los_ejercicios.filter(estado='completado').count()
    a_repetir_count = todos_los_ejercicios.filter(estado='a_repetir').count()

    # Calcular el número de ejercicios pendientes
    pendientes = total_ejercicios - completados - a_repetir_count

    # Calcular el ángulo para el círculo de progreso en grados
    progreso_deg = 0
    if total_ejercicios > 0:
        progreso_deg = int((completados * 360) / total_ejercicios)

    # Calcular el porcentaje de completitud
    porcentaje_completado = 0
    if total_ejercicios > 0:
        porcentaje_completado = int((completados * 100) / total_ejercicios)

    # --- INICIO DE LA NUEVA MODIFICACIÓN ---
    # Encontrar el próximo ejercicio pendiente
    proximo_ejercicio = todos_los_ejercicios.filter(estado='sin_completar').first()
    # --- FIN DE LA NUEVA MODIFICACIÓN ---

    # Aplicar filtros para la lista que se muestra en la página
    ejercicios_filtrados = todos_los_ejercicios
    filtro = request.GET.get('filtro', 'todos')
    if filtro == 'completados':
        ejercicios_filtrados = ejercicios_filtrados.filter(estado='completado')
    elif filtro == 'a_repetir':
        ejercicios_filtrados = ejercicios_filtrados.filter(estado='a_repetir')
    elif filtro == 'sin_completar':
        ejercicios_filtrados = ejercicios_filtrados.filter(estado='sin_completar')

    context = {
        'ejercicios': ejercicios_filtrados,
        'filtro_actual': filtro,
        'total_ejercicios': total_ejercicios,
        'completados': completados,
        'pendientes': pendientes,
        'a_repetir_count': a_repetir_count,
        'progreso_deg': progreso_deg,
        'porcentaje_completado': porcentaje_completado,
        'proximo_ejercicio': proximo_ejercicio,  # <-- Pasamos el próximo ejercicio a la plantilla
    }
    return render(request, 'diario/arete_dashboard.html', context)


@login_required
def arete_ejercicio_actualizar(request, ejercicio_id):
    """Actualizar estado de un ejercicio Areté."""
    ejercicio = get_object_or_404(EjercicioArete, id=ejercicio_id, usuario=request.user)

    if request.method == 'POST':
        data = request.POST
        ejercicio.estado = data.get('estado')
        if data.get('reflexiones'):
            ejercicio.reflexiones = data.get('reflexiones')

        if ejercicio.estado == 'completado' and not ejercicio.fecha_completado:
            ejercicio.fecha_completado = timezone.now()

        ejercicio.save()
        messages.success(request, 'Ejercicio actualizado correctamente.')
        return redirect('arete_dashboard')

    context = {'ejercicio': ejercicio}
    return render(request, 'diario/arete_ejercicio_detalle.html', context)


# ========================================
# GNOSIS - GESTIÓN DE CONOCIMIENTO
# ========================================

@login_required
def gnosis_dashboard(request):
    """Dashboard de la sección Gnosis."""
    contenido = Gnosis.objects.filter(usuario=request.user)

    # Filtros
    categoria = request.GET.get('categoria', 'todos')
    if categoria != 'todos':
        contenido = contenido.filter(categoria=categoria)

    # Búsqueda
    busqueda = request.GET.get('busqueda', '')
    if busqueda:
        contenido = contenido.filter(
            Q(titulo__icontains=busqueda) |
            Q(autor__icontains=busqueda) |
            Q(tematica__icontains=busqueda)
        )

    context = {
        'contenido': contenido.order_by('-fecha_creacion'),
        'categoria_actual': categoria,
        'busqueda_actual': busqueda,
        'categorias': Gnosis.CATEGORIA_CHOICES,
        'total_contenido': Gnosis.objects.filter(usuario=request.user).count()
    }
    return render(request, 'diario/gnosis_dashboard.html', context)


@login_required
def gnosis_crear(request):
    """Crear nuevo contenido en Gnosis."""
    if request.method == 'POST':
        data = request.POST
        Gnosis.objects.create(
            usuario=request.user,
            titulo=data.get('titulo'),
            categoria=data.get('categoria'),
            estado=data.get('estado', 'no_empezado'),
            tematica=data.get('tematica', ''),
            autor=data.get('autor', ''),
            url=data.get('url', ''),
            notas=data.get('notas', '')
        )
        messages.success(request, 'Contenido agregado correctamente.')
        return redirect('gnosis_dashboard')

    context = {
        'categorias': Gnosis.CATEGORIA_CHOICES,
        'estados': Gnosis.ESTADO_CHOICES,
        'puntuaciones': Gnosis.PUNTUACION_CHOICES
    }
    return render(request, 'diario/gnosis_crear.html', context)


# ========================================
# VIRES - SALUD Y DEPORTE
# ========================================

@login_required
def vires_dashboard(request):
    """Dashboard de la sección Vires."""
    fecha_hoy = timezone.now().date()
    seguimiento_hoy = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha=fecha_hoy
    ).first()

    # Entrenamientos de la semana actual
    inicio_semana = fecha_hoy - timedelta(days=fecha_hoy.weekday())
    entrenamientos_semana = EntrenamientoSemanal.objects.filter(
        usuario=request.user,
        semana_inicio=inicio_semana
    )

    # Últimos seguimientos
    seguimientos_recientes = SeguimientoVires.objects.filter(
        usuario=request.user
    ).order_by('-fecha')[:7]

    context = {
        'seguimiento_hoy': seguimiento_hoy,
        'entrenamientos_semana': entrenamientos_semana,
        'seguimientos_recientes': seguimientos_recientes,
        'fecha_hoy': fecha_hoy
    }
    return render(request, 'diario/vires_dashboard.html', context)


# diario/views.py

@login_required
def vires_seguimiento_crear(request):
    """Crear o actualizar seguimiento diario de Vires."""
    if request.method == 'POST':
        data = request.POST
        fecha_str = data.get('fecha', timezone.now().date())
        # Convertir a objeto date si es una cadena
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if isinstance(fecha_str, str) else fecha_str

        # --- Diccionario con los datos a guardar/actualizar ---
        # Usamos .get() con un valor por defecto de None para manejar campos vacíos
        defaults = {
            'peso': data.get('peso') or None,
            'grasa_corporal': data.get('grasa_corporal') or None,
            'masa_muscular': data.get('masa_muscular') or None,
            'horas_sueno': data.get('horas_sueno') or None,
            'calidad_sueno': data.get('calidad_sueno') or None,
            'nivel_energia': data.get('nivel_energia') or None,
            'nivel_estres': data.get('nivel_estres') or None,
            'pasos': data.get('pasos') or None,
            'entrenamiento_realizado': data.get('entrenamiento_realizado') == 'on',
            'alimentacion_saludable': data.get('alimentacion_saludable') == 'on',
            'hidratacion_adecuada': data.get('hidratacion_adecuada') == 'on',
            'descanso_suficiente': data.get('descanso_suficiente') == 'on',
            'notas': data.get('notas', '')
        }

        # get_or_create es más limpio para este caso de uso
        seguimiento, created = SeguimientoVires.objects.update_or_create(
            usuario=request.user,
            fecha=fecha,
            defaults=defaults
        )

        if created:
            messages.success(request, 'Seguimiento guardado correctamente.')
        else:
            messages.success(request, 'Seguimiento actualizado correctamente.')

        return redirect('diario:vires_dashboard')

    # Lógica para el método GET
    fecha_hoy = timezone.now().date()
    seguimiento_existente = SeguimientoVires.objects.filter(usuario=request.user, fecha=fecha_hoy).first()

    context = {
        'fecha_hoy': fecha_hoy,
        'seguimiento': seguimiento_existente
    }
    return render(request, 'diario/vires_seguimiento_form.html', context)


# ========================================
# KAIROS - CALENDARIO Y EVENTOS
# ========================================

@login_required
def kairos_dashboard(request):
    """Dashboard de la sección Kairos - Calendario."""
    fecha_actual = timezone.now().date()
    mes_actual = request.GET.get('mes', fecha_actual.month)
    año_actual = request.GET.get('año', fecha_actual.year)

    # Eventos del mes
    eventos_mes = EventoKairos.objects.filter(
        usuario=request.user,
        fecha_inicio__month=mes_actual,
        fecha_inicio__year=año_actual
    ).order_by('fecha_inicio')

    # Eventos de hoy
    eventos_hoy = EventoKairos.objects.filter(
        usuario=request.user,
        fecha_inicio__date=fecha_actual
    ).order_by('fecha_inicio')

    context = {
        'eventos_mes': eventos_mes,
        'eventos_hoy': eventos_hoy,
        'mes_actual': int(mes_actual),
        'año_actual': int(año_actual),
        'fecha_actual': fecha_actual
    }
    return render(request, 'diario/kairos_dashboard.html', context)


@login_required
def kairos_evento_crear(request):
    """Crear nuevo evento en Kairos."""
    if request.method == 'POST':
        data = request.POST
        EventoKairos.objects.create(
            usuario=request.user,
            titulo=data.get('titulo'),
            descripcion=data.get('descripcion', ''),
            tipo=data.get('tipo', 'personal'),
            fecha_inicio=data.get('fecha_inicio'),
            fecha_fin=data.get('fecha_fin') if data.get('fecha_fin') else None,
            todo_el_dia=data.get('todo_el_dia') == 'on',
            recordatorio=data.get('recordatorio') == 'on',
            color=data.get('color', '#00ffff')
        )
        messages.success(request, 'Evento creado correctamente.')
        return redirect('kairos_dashboard')

    context = {
        'tipos_evento': EventoKairos.TIPO_CHOICES
    }
    return render(request, 'diario/kairos_evento_form.html', context)


@login_required
def kairos_eventos_api(request):
    """API para obtener eventos en formato JSON para el calendario."""
    eventos = EventoKairos.objects.filter(usuario=request.user)

    eventos_json = []
    for evento in eventos:
        eventos_json.append({
            'id': evento.id,
            'title': evento.titulo,
            'start': evento.fecha_inicio.isoformat(),
            'end': evento.fecha_fin.isoformat() if evento.fecha_fin else None,
            'color': evento.color,
            'allDay': evento.todo_el_dia,
            'description': evento.descripcion
        })

    return JsonResponse(eventos_json, safe=False)


# Pega esto en la sección PROSOCHE de tu views.py

@login_required
def habito_prosoche_crear(request):
    """Crea un nuevo hábito para un diario Prosoche existente."""
    if request.method == 'POST':
        data = request.POST
        prosoche_id = data.get('prosoche_id')
        nombre_habito = data.get('nombre')
        descripcion_habito = data.get('descripcion', '')

        if not prosoche_id or not nombre_habito:
            messages.error(request, 'Faltan datos para crear el hábito.')
            return redirect('prosoche_dashboard')

        prosoche = get_object_or_404(Prosoche, id=prosoche_id, usuario=request.user)

        HabitoProsoche.objects.create(
            prosoche=prosoche,
            nombre=nombre_habito,
            descripcion=descripcion_habito
        )

        messages.success(request, f'Hábito "{nombre_habito}" creado correctamente.')
        return redirect('prosoche_dashboard')

    return redirect('prosoche_dashboard')


# Pega esto en la sección EUDAIMONIA de tu views.py
# diario/views.py

@login_required
def eudaimonia_crear_area(request):
    """
    Crea una nueva AreaVida y la asocia al perfil Eudaimonia del usuario.
    """
    if request.method == 'POST':
        data = request.POST
        nombre_area = data.get('nombre')
        puntuacion = data.get('puntuacion', 5)
        prioridad = data.get('prioridad', 'media')
        descripcion = data.get('descripcion', '')  # Capturamos la descripción

        # --- VALIDACIÓN CORREGIDA ---
        # Ahora comprobamos si se ha proporcionado un nombre
        if not nombre_area:
            messages.error(request, 'Debes proporcionar un nombre para el área de vida.')
            return redirect('diario:eudaimonia_dashboard')

        # --- LÓGICA DE CREACIÓN CORREGIDA ---
        # 1. Creamos o encontramos el objeto AreaVida (el modelo "maestro").
        #    Usamos get_or_create para evitar duplicados si un área "Salud" ya existe.
        area_vida, created = AreaVida.objects.get_or_create(
            nombre=nombre_area,
            defaults={'descripcion': descripcion}
        )
        # Si no fue creada, pero el usuario envió una nueva descripción, la actualizamos.
        if not created and descripcion:
            area_vida.descripcion = descripcion
            area_vida.save()

        # 2. Verificamos si el usuario YA tiene esta área en su perfil Eudaimonia.
        if Eudaimonia.objects.filter(usuario=request.user, area=area_vida).exists():
            messages.warning(request, f'Ya tienes el área "{area_vida.nombre}" en tu dashboard.')
            return redirect('diario:eudaimonia_dashboard')

        # 3. Creamos la conexión en Eudaimonia para este usuario.
        Eudaimonia.objects.create(
            usuario=request.user,
            area=area_vida,
            puntuacion=puntuacion,
            prioridad=prioridad
        )

        messages.success(request, f'Área "{area_vida.nombre}" añadida a tu dashboard.')
        return redirect('diario:eudaimonia_dashboard')

    # Si el método no es POST, simplemente redirigimos (el formulario está en la misma página)
    return redirect('diario:eudaimonia_dashboard')


@login_required
def prosoche_crear_habito(request):
    """Crear nuevo hábito"""
    if request.method == 'POST':
        prosoche_id = request.POST.get('prosoche_id')
        prosoche_mes = get_object_or_404(ProsocheMes, id=prosoche_id, usuario=request.user)

        nombre = request.POST.get('nombre')
        if nombre:
            habito, created = ProsocheHabito.objects.get_or_create(
                prosoche_mes=prosoche_mes,
                nombre=nombre,
                defaults={
                    'descripcion': request.POST.get('descripcion', ''),
                    'color': request.POST.get('color', '#00ffff')
                }
            )

            if created:
                messages.success(request, f'Hábito "{nombre}" creado correctamente.')
            else:
                messages.info(request, f'El hábito "{nombre}" ya existe.')

        return redirect('prosoche_dashboard')

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# diario/views.py

@login_required
def prosoche_dashboard(request):
    """Dashboard principal de Prosoche (VERSIÓN FUNCIONAL RESTAURADA)"""
    hoy = timezone.now()
    mes_actual_str = hoy.strftime('%B')
    año_actual = hoy.year

    # 1. Obtenemos o creamos el mes actual. Simple y directo.
    prosoche_mes, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_actual_str,
        año=año_actual
    )

    # 2. Obtenemos los datos relacionados de forma separada. Es más claro y evita los problemas del prefetch.
    semanas = ProsocheSemana.objects.filter(prosoche_mes=prosoche_mes).order_by('numero_semana')
    entradas_del_mes = ProsocheDiario.objects.filter(prosoche_mes=prosoche_mes).order_by('-fecha')
    habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

    # 3. Lógica para la semana actual (sin cambios, es correcta)
    numero_semana_actual = (hoy.day - 1) // 7 + 1
    semana_actual = semanas.filter(numero_semana=numero_semana_actual).first()

    # 4. Lógica para preparar los datos de hábitos (¡AQUÍ ESTÁ LA CLAVE!)
    # Esta es la lógica que funciona. La ejecutamos para cada hábito por separado.
    dias_mes = list(range(1, calendar.monthrange(año_actual, hoy.month)[1] + 1))
    habitos_con_dias = []
    for habito in habitos:
        # Obtenemos SOLO los días completados PARA ESTE HÁBITO.
        dias_completados_query = ProsocheHabitoDia.objects.filter(
            habito=habito,
            completado=True
        ).values_list('dia', flat=True)

        # Convertimos a un conjunto para búsquedas rápidas (eficiente).
        dias_completados_set = set(dias_completados_query)

        dias_para_plantilla = []
        for dia_num in dias_mes:
            dias_para_plantilla.append({
                'dia': dia_num,
                'completado': dia_num in dias_completados_set
            })

        porcentaje = round((len(dias_completados_set) / len(dias_mes)) * 100) if dias_mes else 0
        habitos_con_dias.append({'habito': habito, 'dias': dias_para_plantilla, 'porcentaje': porcentaje})

    # 5. Obtenemos los meses anteriores (sin cambios)
    meses_anteriores = ProsocheMes.objects.filter(
        usuario=request.user
    ).exclude(id=prosoche_mes.id).order_by('-año', '-mes')[:6]

    # 6. Construimos el contexto final
    context = {
        'prosoche_mes': prosoche_mes,
        'semanas': semanas,
        'semana_actual': semana_actual,
        'entradas_del_mes': entradas_del_mes,
        'habitos_con_dias': habitos_con_dias,
        'dias_mes': dias_mes,
        'meses_anteriores': meses_anteriores,
        'mes_actual': mes_actual_str,
        'año_actual': año_actual,
    }

    return render(request, 'diario/prosoche_dashboard.html', context)


@login_required
@require_http_methods(["POST"])  # Es buena práctica restringir el método
def prosoche_actualizar_objetivos(request):
    """
    Actualiza objetivos mensuales y semanales de forma dinámica.
    """
    try:
        data = json.loads(request.body)
        prosoche_id = data.get('prosoche_id')
        tipo = data.get('tipo')

        prosoche_mes = get_object_or_404(ProsocheMes, id=prosoche_id, usuario=request.user)

        if tipo == 'mensual':
            # --- LÓGICA CORREGIDA ---
            # Itera sobre los datos recibidos y actualiza solo los campos correspondientes.
            for key, value in data.items():
                # Solo actualiza los campos que existen en el modelo ProsocheMes
                if hasattr(prosoche_mes, key):
                    setattr(prosoche_mes, key, value)
            prosoche_mes.save()

        elif tipo == 'semanal':
            semana_num = data.get('semana')
            if semana_num is None:
                return JsonResponse({'success': False, 'error': 'Número de semana no proporcionado'}, status=400)

            semana = get_object_or_404(ProsocheSemana, prosoche_mes=prosoche_mes, numero_semana=semana_num)

            # Lógica dinámica también para las semanas
            for key, value in data.items():
                if hasattr(semana, key):
                    setattr(semana, key, value)
            semana.save()

        return JsonResponse({'success': True, 'message': 'Objetivo actualizado'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# diario/views.py

@login_required
def prosoche_toggle_habito(request):
    """
    Marcar/desmarcar hábito para un día específico (VERSIÓN FINAL Y ROBUSTA).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        habito_id = data.get('habito_id')
        dia = data.get('dia')

        if not all([habito_id, dia]):
            return JsonResponse({'success': False, 'error': 'Faltan datos.'}, status=400)

        # 1. Obtenemos el hábito para asegurar que pertenece al usuario.
        habito = get_object_or_404(ProsocheHabito, id=habito_id, prosoche_mes__usuario=request.user)

        # 2. Intentamos obtener el registro del día para ese hábito.
        dia_habito = ProsocheHabitoDia.objects.filter(habito=habito, dia=dia).first()

        # 3. Lógica de decisión clara:
        if dia_habito:
            # Si el registro existe, lo eliminamos. Esto equivale a "desmarcar".
            dia_habito.delete()
            estado_final = False
            mensaje = f"Día {dia} para '{habito.nombre}' desmarcado."
        else:
            # Si el registro no existe, lo creamos. Esto equivale a "marcar".
            ProsocheHabitoDia.objects.create(habito=habito, dia=dia, completado=True)
            estado_final = True
            mensaje = f"Día {dia} para '{habito.nombre}' marcado como completado."

        print(mensaje)  # Para depuración en la consola del servidor.

        return JsonResponse({
            'success': True,
            'completado': estado_final,
            'message': mensaje
        })

    except Exception as e:
        # Capturamos cualquier otro error para depuración.
        print(f"ERROR en prosoche_toggle_habito: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def prosoche_revision_mes(request):
    """Actualizar revisión del mes"""
    if request.method == 'POST':
        prosoche_id = request.POST.get('prosoche_id')
        prosoche_mes = get_object_or_404(ProsocheMes, id=prosoche_id, usuario=request.user)

        prosoche_mes.logro_principal = request.POST.get('logro_principal', '')
        prosoche_mes.obstaculo_principal = request.POST.get('obstaculo_principal', '')
        prosoche_mes.aprendizaje_principal = request.POST.get('aprendizaje_principal', '')
        prosoche_mes.momento_felicidad = request.POST.get('momento_felicidad', '')
        prosoche_mes.save()

        messages.success(request, 'Revisión del mes guardada correctamente.')
        return redirect('diario:prosoche_dashboard')

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ============================================
# VISTA MEJORADA: prosoche_mes_anterior
# Con análisis completo de hábitos y estadísticas
# ============================================

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from collections import Counter
import calendar
from datetime import datetime, timedelta

from .models import (
    ProsocheMes, ProsocheSemana, ProsocheDiario,
    ProsocheHabito, ProsocheHabitoDia
)

# ============================================
# VISTA CORREGIDA: prosoche_mes_anterior
# CORRECCIÓN: Porcentajes calculados sobre días del mes, no días registrados
# ============================================

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from collections import Counter
import calendar
from datetime import datetime, timedelta

from .models import (
    ProsocheMes, ProsocheSemana, ProsocheDiario,
    ProsocheHabito, ProsocheHabitoDia
)


@login_required
def prosoche_mes_anterior(request, mes, año):
    """
    Ver mes anterior específico con análisis completo de estadísticas.
    CORREGIDO: Porcentajes calculados correctamente sobre días del mes.
    """
    prosoche_mes = get_object_or_404(
        ProsocheMes,
        usuario=request.user,
        mes=mes,
        año=año
    )

    semanas = ProsocheSemana.objects.filter(prosoche_mes=prosoche_mes).order_by('numero_semana')
    entradas = ProsocheDiario.objects.filter(prosoche_mes=prosoche_mes).order_by('fecha')
    habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

    # CORRECCIÓN: Calcular días reales del mes
    mes_num = list(calendar.month_name).index(mes)
    dias_reales_del_mes = calendar.monthrange(año, mes_num)[1]

    # Preparar datos de hábitos con seguimiento
    dias_mes = list(range(1, dias_reales_del_mes + 1))  # CORRECCIÓN: Usar días reales
    habitos_con_dias = []

    for habito in habitos:
        dias_habito = []
        dias_completados = 0
        racha_actual = 0
        racha_mas_larga = 0
        racha_temp = 0

        # Calcular estadísticas por semana
        semanas_stats = {}

        # CORRECCIÓN: Iterar sobre TODOS los días del mes, no solo los registrados
        for dia in dias_mes:
            try:
                dia_obj = ProsocheHabitoDia.objects.get(habito=habito, dia=dia)
                dias_habito.append(dia_obj)

                if dia_obj.completado:
                    dias_completados += 1
                    racha_temp += 1
                    racha_mas_larga = max(racha_mas_larga, racha_temp)
                else:
                    racha_temp = 0

                # Calcular semana del mes (1-5)
                semana_num = ((dia - 1) // 7) + 1
                if semana_num not in semanas_stats:
                    semanas_stats[semana_num] = {'completados': 0, 'total': 0}
                semanas_stats[semana_num]['total'] += 1
                if dia_obj.completado:
                    semanas_stats[semana_num]['completados'] += 1

            except ProsocheHabitoDia.DoesNotExist:
                # CORRECCIÓN: Contar días sin registro como NO completados
                dias_habito.append(None)
                racha_temp = 0  # Rompe la racha

                # Añadir a estadísticas semanales como día no completado
                semana_num = ((dia - 1) // 7) + 1
                if semana_num not in semanas_stats:
                    semanas_stats[semana_num] = {'completados': 0, 'total': 0}
                semanas_stats[semana_num]['total'] += 1

        # Racha actual (desde el último día del mes hacia atrás)
        for dia_obj in reversed([d for d in dias_habito if d is not None]):
            if dia_obj.completado:
                racha_actual += 1
            else:
                break

        # CORRECCIÓN: Calcular porcentaje sobre días REALES del mes
        porcentaje = (dias_completados / dias_reales_del_mes * 100) if dias_reales_del_mes > 0 else 0

        # Consistencia: mide qué tan distribuidos están los días completados
        consistencia = 0
        if semanas_stats:
            porcentajes_semanales = [
                (s['completados'] / s['total'] * 100) if s['total'] > 0 else 0
                for s in semanas_stats.values()
            ]
            consistencia = sum(porcentajes_semanales) / len(porcentajes_semanales)

        # Mejor semana
        mejor_semana = 1
        mejor_porcentaje = 0
        for semana_num, stats in semanas_stats.items():
            porcentaje_semana = (stats['completados'] / stats['total'] * 100) if stats['total'] > 0 else 0
            if porcentaje_semana > mejor_porcentaje:
                mejor_porcentaje = porcentaje_semana
                mejor_semana = semana_num

        habitos_con_dias.append({
            'habito': habito,
            'dias': dias_habito,
            'estadisticas': {
                'dias_completados': dias_completados,
                'dias_totales': dias_reales_del_mes,  # CORRECCIÓN: Usar días reales
                'porcentaje': porcentaje,
                'racha_actual': racha_actual,
                'racha_mas_larga': racha_mas_larga,
                'consistencia': consistencia,
                'mejor_semana': mejor_semana,
            }
        })

    # ============================================
    # ESTADÍSTICAS GENERALES DEL MES
    # ============================================

    estadisticas = {}

    # Total de entradas
    estadisticas['total_entradas'] = entradas.count()

    # CORRECCIÓN: Porcentaje sobre días reales del mes
    estadisticas['porcentaje_dias_con_entrada'] = (
            estadisticas['total_entradas'] / dias_reales_del_mes * 100
    ) if dias_reales_del_mes > 0 else 0

    # Estado de ánimo promedio
    if entradas.exists():
        estadisticas['estado_animo_promedio'] = entradas.aggregate(
            Avg('estado_animo')
        )['estado_animo__avg'] or 0

        # Tendencia del estado de ánimo (comparar primera mitad vs segunda mitad)
        mitad = dias_reales_del_mes // 2
        primera_mitad = entradas.filter(fecha__day__lte=mitad).aggregate(
            Avg('estado_animo')
        )['estado_animo__avg'] or 0
        segunda_mitad = entradas.filter(fecha__day__gt=mitad).aggregate(
            Avg('estado_animo')
        )['estado_animo__avg'] or 0

        if segunda_mitad > primera_mitad + 0.3:
            estadisticas['tendencia_animo'] = 'mejorando'
        elif segunda_mitad < primera_mitad - 0.3:
            estadisticas['tendencia_animo'] = 'empeorando'
        else:
            estadisticas['tendencia_animo'] = 'estable'
    else:
        estadisticas['estado_animo_promedio'] = 0
        estadisticas['tendencia_animo'] = 'sin_datos'

    # Promedio de éxito en hábitos
    if habitos_con_dias:
        estadisticas['promedio_habitos'] = sum(
            h['estadisticas']['porcentaje'] for h in habitos_con_dias
        ) / len(habitos_con_dias)
        estadisticas['total_habitos'] = len(habitos_con_dias)
    else:
        estadisticas['promedio_habitos'] = 0
        estadisticas['total_habitos'] = 0

    # Racha más larga de escritura
    racha_mas_larga = 0
    racha_temp = 0
    fechas_entradas = set(entradas.values_list('fecha', flat=True))

    # CORRECCIÓN: Iterar sobre días reales del mes
    for dia in range(1, dias_reales_del_mes + 1):
        fecha = datetime(año, mes_num, dia).date()
        if fecha in fechas_entradas:
            racha_temp += 1
            racha_mas_larga = max(racha_mas_larga, racha_temp)
        else:
            racha_temp = 0

    estadisticas['racha_mas_larga'] = racha_mas_larga

    # Distribución de estados de ánimo
    distribucion_animo = []
    estados = {
        1: {'nombre': 'Muy Mal', 'emoji': '😢', 'color': '#f44336'},
        2: {'nombre': 'Mal', 'emoji': '😟', 'color': '#ff9800'},
        3: {'nombre': 'Normal', 'emoji': '😐', 'color': '#ffc107'},
        4: {'nombre': 'Bien', 'emoji': '🙂', 'color': '#8bc34a'},
        5: {'nombre': 'Muy Bien', 'emoji': '😄', 'color': '#4caf50'},
    }

    for valor, info in estados.items():
        cantidad = entradas.filter(estado_animo=valor).count()
        porcentaje = (cantidad / estadisticas['total_entradas'] * 100) if estadisticas['total_entradas'] > 0 else 0
        distribucion_animo.append({
            'valor': valor,
            'nombre': info['nombre'],
            'emoji': info['emoji'],
            'color': info['color'],
            'cantidad': cantidad,
            'porcentaje': porcentaje
        })

    estadisticas['distribucion_animo'] = distribucion_animo

    # Mejor día (estado de ánimo más alto)
    estadisticas['mejor_dia'] = entradas.order_by('-estado_animo', '-fecha').first()

    # Día más productivo (más tareas completadas)
    dia_mas_productivo = None
    max_tareas = 0
    for entrada in entradas:
        if entrada.tareas_dia:
            num_tareas = len(entrada.tareas_dia)
            if num_tareas > max_tareas:
                max_tareas = num_tareas
                dia_mas_productivo = entrada
    estadisticas['dia_mas_productivo'] = dia_mas_productivo

    # Etiquetas más frecuentes
    todas_etiquetas = []
    for entrada in entradas:
        if entrada.etiquetas:
            etiquetas = [e.strip() for e in entrada.etiquetas.split(',') if e.strip()]
            todas_etiquetas.extend(etiquetas)

    if todas_etiquetas:
        contador_etiquetas = Counter(todas_etiquetas)
        estadisticas['etiquetas_frecuentes'] = [
            {'nombre': etiqueta, 'count': count}
            for etiqueta, count in contador_etiquetas.most_common(5)
        ]
    else:
        estadisticas['etiquetas_frecuentes'] = []

    # ============================================
    # INSIGHTS AUTOMÁTICOS
    # ============================================

    insights = []

    # Insight 1: Hábito más consistente
    if habitos_con_dias:
        mejor_habito = max(habitos_con_dias, key=lambda h: h['estadisticas']['porcentaje'])
        if mejor_habito['estadisticas']['porcentaje'] >= 80:
            insights.append({
                'icono': 'fa-trophy',
                'titulo': 'Hábito Estrella',
                'descripcion': f'Tu hábito "{mejor_habito["habito"].nombre}" tuvo un {mejor_habito["estadisticas"]["porcentaje"]:.0f}% de éxito. ¡Excelente consistencia!',
                'sugerencia': 'Aplica la misma estrategia a otros hábitos.'
            })

        # Insight 2: Hábito que necesita atención
        peor_habito = min(habitos_con_dias, key=lambda h: h['estadisticas']['porcentaje'])
        if peor_habito['estadisticas']['porcentaje'] < 50:
            insights.append({
                'icono': 'fa-exclamation-triangle',
                'titulo': 'Área de Mejora',
                'descripcion': f'El hábito "{peor_habito["habito"].nombre}" solo alcanzó un {peor_habito["estadisticas"]["porcentaje"]:.0f}% de éxito.',
                'sugerencia': 'Considera si este hábito es realista o necesita ser reformulado.'
            })

    # Insight 3: Tendencia de estado de ánimo
    if estadisticas['tendencia_animo'] == 'mejorando':
        insights.append({
            'icono': 'fa-arrow-up',
            'titulo': 'Tendencia Positiva',
            'descripcion': 'Tu estado de ánimo mejoró durante el mes. La segunda mitad fue mejor que la primera.',
            'sugerencia': '¿Qué cambió? Identifica qué funcionó para repetirlo.'
        })
    elif estadisticas['tendencia_animo'] == 'empeorando':
        insights.append({
            'icono': 'fa-arrow-down',
            'titulo': 'Atención Requerida',
            'descripcion': 'Tu estado de ánimo descendió durante el mes.',
            'sugerencia': 'Reflexiona sobre qué factores pudieron influir negativamente.'
        })

    # Insight 4: Consistencia en escritura
    if estadisticas['porcentaje_dias_con_entrada'] >= 80:
        insights.append({
            'icono': 'fa-pen',
            'titulo': 'Escritor Consistente',
            'descripcion': f'Escribiste en el {estadisticas["porcentaje_dias_con_entrada"]:.0f}% de los días del mes.',
            'sugerencia': 'Tu disciplina en la escritura es admirable. Sigue así.'
        })
    elif estadisticas['porcentaje_dias_con_entrada'] < 30:
        insights.append({
            'icono': 'fa-calendar-times',
            'titulo': 'Oportunidad de Mejora',
            'descripcion': f'Solo escribiste en el {estadisticas["porcentaje_dias_con_entrada"]:.0f}% de los días.',
            'sugerencia': 'Intenta establecer un recordatorio diario para mantener el hábito.'
        })

    # Insight 5: Racha impresionante
    if estadisticas['racha_mas_larga'] >= 7:
        insights.append({
            'icono': 'fa-fire',
            'titulo': 'Racha Impresionante',
            'descripcion': f'Mantuviste una racha de {estadisticas["racha_mas_larga"]} días consecutivos escribiendo.',
            'sugerencia': '¡Eso es disciplina estoica en acción!'
        })

    # Insight 6: Etiquetas recurrentes
    if estadisticas['etiquetas_frecuentes']:
        etiqueta_top = estadisticas['etiquetas_frecuentes'][0]
        insights.append({
            'icono': 'fa-tag',
            'titulo': 'Tema Recurrente',
            'descripcion': f'La etiqueta "{etiqueta_top["nombre"]}" apareció {etiqueta_top["count"]} veces.',
            'sugerencia': 'Este tema parece importante para ti. ¿Necesita más atención?'
        })

    # ============================================
    # CONTEXTO FINAL
    # ============================================

    context = {
        'prosoche_mes': prosoche_mes,
        'semanas': semanas,
        'entradas': entradas,
        'habitos_con_dias': habitos_con_dias,
        'dias_mes': dias_mes,  # CORRECCIÓN: Ahora contiene días reales del mes
        'es_mes_anterior': True,
        'estadisticas': estadisticas,
        'insights': insights,
    }

    return render(request, 'diario/prosoche_mes_anterior.html', context)


from .models import RevisionSemanal  # Asegúrate de que esta importación está al principio

from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Avg


@login_required
def prosoche_revision_semanal(request):
    """
    Vista para la revisión semanal guiada (VERSIÓN CORREGIDA Y UNIFICADA).
    """
    # --- LÓGICA GET (Preparación de datos para mostrar) ---
    hoy = timezone.now().date()

    # 1. Definir rangos de semana (pasada y actual)
    inicio_semana_pasada = hoy - timedelta(days=hoy.weekday() + 7)
    fin_semana_pasada = inicio_semana_pasada + timedelta(days=6)

    # 2. Recopilar y calcular datos de la semana pasada
    entradas_semana_pasada = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha__range=[inicio_semana_pasada, fin_semana_pasada]
    ).order_by('fecha')

    animo_promedio = entradas_semana_pasada.aggregate(Avg('estado_animo'))['estado_animo__avg']
    if animo_promedio:
        animo_promedio = round(animo_promedio, 1)

    #
    total_tareas = sum(e.get_total_tareas() for e in entradas_semana_pasada)
    tareas_completadas = sum(e.get_tareas_completadas() for e in entradas_semana_pasada)
    porcentaje_tareas = round((tareas_completadas / total_tareas) * 100) if total_tareas > 0 else 0

    # 3. Obtener la semana actual (para el formulario de planificación)
    prosoche_mes_actual = ProsocheMes.objects.filter(usuario=request.user, año=hoy.year, mes=hoy.strftime('%B')).first()
    numero_semana_actual = (hoy.day - 1) // 7 + 1
    semana_actual = None
    if prosoche_mes_actual:
        semana_actual, _ = ProsocheSemana.objects.get_or_create(
            prosoche_mes=prosoche_mes_actual,
            numero_semana=numero_semana_actual
        )

    # 4. Obtener la semana pasada (para asociar la revisión)
    numero_semana_pasada = (inicio_semana_pasada.day - 1) // 7 + 1
    prosoche_mes_pasado = ProsocheMes.objects.filter(año=inicio_semana_pasada.year,
                                                     mes=inicio_semana_pasada.strftime('%B'),
                                                     usuario=request.user).first()
    semana_pasada = None
    if prosoche_mes_pasado:
        semana_pasada, _ = ProsocheSemana.objects.get_or_create(prosoche_mes=prosoche_mes_pasado,
                                                                numero_semana=numero_semana_pasada)

    # 5. Obtener o crear el objeto de revisión para mostrarlo en el formulario
    revision = None
    if semana_pasada:
        revision, created = RevisionSemanal.objects.get_or_create(semana=semana_pasada, usuario=request.user)
        if created and entradas_semana_pasada.exists():
            logros_sugeridos = [e.que_ha_ido_bien for e in entradas_semana_pasada if e.que_ha_ido_bien]
            revision.logro_principal = " - " + "\n - ".join(logros_sugeridos)

            aprendizajes_sugeridos = [e.que_puedo_mejorar for e in entradas_semana_pasada if e.que_puedo_mejorar]
            revision.aprendizaje_principal = " - " + "\n - ".join(aprendizajes_sugeridos)
            # No lo guardamos aquí, solo pre-rellenamos el objeto para el template

    # --- LÓGICA POST (Manejo de envío de formularios) ---
    if request.method == 'POST':
        # Como ahora es un solo formulario, guardamos todo a la vez.

        # 1. Guardar la Revisión
        if revision:
            revision.logro_principal = request.POST.get('logro_principal', '')
            revision.obstaculo_principal = request.POST.get('obstaculo_principal', '')
            revision.aprendizaje_principal = request.POST.get('aprendizaje_principal', '')
            revision.save()
            messages.info(request, 'Revisión de la semana guardada.')

        # 2. Guardar la Planificación
        if semana_actual:
            semana_actual.objetivo_1 = request.POST.get('objetivo_1', '')
            semana_actual.objetivo_2 = request.POST.get('objetivo_2', '')
            semana_actual.objetivo_3 = request.POST.get('objetivo_3', '')
            semana_actual.save()
            messages.success(request, '¡Planificación para la nueva semana guardada con éxito!')

        return redirect('diario:prosoche_dashboard')
        # Redirigir al dashboard de Prosoche

        # Si algo falla, simplemente se vuelve a renderizar la página
        messages.warning(request, 'Ocurrió un error al procesar el formulario.')

    # --- CONTEXTO FINAL ---
    context = {
        'inicio_semana_pasada': inicio_semana_pasada,
        'fin_semana_pasada': fin_semana_pasada,
        'entradas_semana': entradas_semana_pasada,
        'animo_promedio': animo_promedio,
        'total_tareas': total_tareas,
        'tareas_completadas': tareas_completadas,
        'porcentaje_tareas': porcentaje_tareas,
        'semana_actual': semana_actual,
        'prosoche_mes_actual': prosoche_mes_actual,
        'revision': revision,
    }
    return render(request, 'diario/prosoche_revision_semanal.html', context)


@login_required
def oraculo_insights(request):
    """
    Página que muestra los insights generados por el motor de análisis.
    """
    insights = generar_insights_semanales(request.user)

    context = {
        'insights': insights
    }
    return render(request, 'diario/oraculo_insights.html', context)


@login_required
def analiticas_personales(request):
    """
    Página de visualización de datos históricos y tendencias.
    """
    periodo_dias = int(request.GET.get('periodo', 30))
    fecha_fin = timezone.now().date()
    fecha_inicio = fecha_fin - timedelta(days=periodo_dias - 1)

    entradas = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('fecha')

    seguimientos_vires = SeguimientoVires.objects.filter(
        usuario=request.user,
        fecha__range=[fecha_inicio, fecha_fin]
    ).order_by('fecha')

    # --- LÓGICA DE DATOS MEJORADA ---
    labels = []
    animo_data = []
    peso_data = []
    sueno_data = []
    energia_data = []
    estres_data = []

    # Creamos un mapa de seguimientos para un acceso rápido
    vires_map = {s.fecha: s for s in seguimientos_vires}

    # Iteramos sobre el rango de fechas para asegurar que todos los días estén en el gráfico
    for i in range(periodo_dias):
        fecha_actual = fecha_inicio + timedelta(days=i)
        labels.append(fecha_actual.strftime('%d/%m'))

        entrada_dia = next((e for e in entradas if e.fecha == fecha_actual), None)
        seguimiento_dia = vires_map.get(fecha_actual)

        animo_data.append(entrada_dia.estado_animo if entrada_dia else 'NaN')
        peso_data.append(float(seguimiento_dia.peso) if seguimiento_dia and seguimiento_dia.peso else 'NaN')
        sueno_data.append(
            float(seguimiento_dia.horas_sueno) if seguimiento_dia and seguimiento_dia.horas_sueno else 'NaN')
        energia_data.append(
            seguimiento_dia.nivel_energia if seguimiento_dia and seguimiento_dia.nivel_energia else 'NaN')
        estres_data.append(seguimiento_dia.nivel_estres if seguimiento_dia and seguimiento_dia.nivel_estres else 'NaN')

    context = {
        'periodo_actual': periodo_dias,
        'chart_data': json.dumps({
            'labels': labels,
            'animo_data': animo_data,
            'peso_data': peso_data,
            'sueno_data': sueno_data,
            'energia_data': energia_data,
            'estres_data': estres_data,
        })
    }
    return render(request, 'diario/analiticas_personales.html', context)


# diario/views.py

@login_required
def simbiosis_dashboard(request):
    """Dashboard de Simbiosis (VERSIÓN OPTIMIZADA)"""

    # OPTIMIZACIÓN: No hay mucho que optimizar aquí ya que son dos listas separadas,
    # pero es una buena práctica ser explícito.
    personas = PersonaImportante.objects.filter(usuario=request.user).order_by('tipo_relacion', 'nombre')

    # OPTIMIZACIÓN: Usamos prefetch_related para cargar las personas asociadas a cada interacción.
    ultimas_interacciones = Interaccion.objects.filter(
        usuario=request.user
    ).prefetch_related('personas').order_by('-fecha')[:10]

    context = {
        'personas': personas,
        'ultimas_interacciones': ultimas_interacciones,
    }
    return render(request, 'diario/simbiosis_dashboard.html', context)


@login_required
def persona_crear_editar(request, persona_id=None):
    """
    Vista para crear o editar una PersonaImportante.
    """
    instance = None
    if persona_id:
        instance = get_object_or_404(PersonaImportante, id=persona_id, usuario=request.user)

    if request.method == 'POST':
        form = PersonaImportanteForm(request.POST, instance=instance)
        if form.is_valid():
            persona = form.save(commit=False)
            persona.usuario = request.user
            persona.save()
            messages.success(request, f'Se ha guardado a "{persona.nombre}" correctamente.')
            return redirect('diario:simbiosis_dashboard')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        form = PersonaImportanteForm(instance=instance)

    context = {
        'form': form,
        'instance': instance,  # Para saber en la plantilla si estamos editando o creando
    }
    return render(request, 'diario/persona_form.html', context)


@login_required
def interaccion_crear_editar(request, interaccion_id=None):
    """
    Vista para crear o editar una Interaccion.
    """
    instance = None
    if interaccion_id:
        instance = get_object_or_404(Interaccion, id=interaccion_id, usuario=request.user)

    if request.method == 'POST':
        # Pasamos el usuario al formulario para que pueda filtrar el campo 'personas'
        form = InteraccionForm(request.POST, instance=instance, usuario=request.user)
        if form.is_valid():
            interaccion = form.save(commit=False)
            interaccion.usuario = request.user
            interaccion.save()
            # El método .set() es la forma correcta de guardar relaciones ManyToMany
            form.save_m2m()
            messages.success(request, f'Interacción "{interaccion.titulo}" guardada correctamente.')
            return redirect('diario:simbiosis_dashboard')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
    else:
        # Pasamos el usuario también en el método GET
        form = InteraccionForm(instance=instance, usuario=request.user)

    context = {
        'form': form,
        'instance': instance,
    }
    return render(request, 'diario/interaccion_form.html', context)


# diario/views.py

@login_required
def persona_detalle(request, persona_id):
    """
    Muestra el perfil de una PersonaImportante y todas las interacciones asociadas.
    """
    persona = get_object_or_404(PersonaImportante, id=persona_id, usuario=request.user)

    # Obtenemos todas las interacciones donde esta persona estuvo involucrada
    interacciones_con_persona = persona.interaccion_set.all().order_by('-fecha')

    context = {
        'persona': persona,
        'interacciones': interacciones_con_persona,
    }
    return render(request, 'diario/persona_detalle.html', context)


# ============================================
# VISTAS PARA EL MÓDULO LOGOS
# Añadir estas vistas al archivo diario/views.py
# ============================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from datetime import date, timedelta
from .models import (
    ReflexionLibre, ReflexionGuiadaTema, Virtud, Insignia,
    InsigniaUsuario, RachaEscritura
)


# ============================================
# DASHBOARD DE LOGOS
# ============================================

@login_required
def logos_dashboard(request):
    """
    Dashboard principal del módulo Logos.
    Muestra reflexiones recientes, reflexión del día, y estadísticas.
    """
    hoy = timezone.now().date()

    # Reflexiones recientes del usuario
    reflexiones_recientes = ReflexionLibre.objects.filter(
        usuario=request.user
    ).order_by('-fecha')[:5]

    # Reflexión guiada del día (si existe)
    reflexion_del_dia = ReflexionGuiadaTema.objects.filter(
        activa=True,
        fecha_activacion=hoy
    ).first()

    # Si no hay reflexión para hoy exacto, buscar la más reciente del mes
    if not reflexion_del_dia:
        reflexion_del_dia = ReflexionGuiadaTema.objects.filter(
            activa=True,
            fecha_activacion__month=hoy.month,
            fecha_activacion__day__lte=hoy.day
        ).order_by('-fecha_activacion').first()

    # Estadísticas
    total_reflexiones = ReflexionLibre.objects.filter(usuario=request.user).count()
    reflexiones_guiadas_completadas = ReflexionLibre.objects.filter(
        usuario=request.user,
        tipo='guiada'
    ).count()

    # Racha de escritura
    racha, _ = RachaEscritura.objects.get_or_create(usuario=request.user)

    context = {
        'reflexiones_recientes': reflexiones_recientes,
        'reflexion_del_dia': reflexion_del_dia,
        'total_reflexiones': total_reflexiones,
        'reflexiones_guiadas_completadas': reflexiones_guiadas_completadas,
        'racha': racha,
    }

    return render(request, 'diario/logos_dashboard.html', context)


# ============================================
# ESCRITURA LIBRE
# ============================================

@login_required
def logos_escritura_libre(request):
    """
    Vista para crear una reflexión de escritura libre.
    """
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        contenido = request.POST.get('contenido', '').strip()
        etiquetas = request.POST.get('etiquetas', '').strip()
        estado_animo_post = request.POST.get('estado_animo_post')

        if not contenido:
            messages.error(request, 'El contenido de la reflexión no puede estar vacío.')
            return redirect('diario:logos_escritura_libre')

        # Crear la reflexión
        reflexion = ReflexionLibre.objects.create(
            usuario=request.user,
            titulo=titulo if titulo else f"Reflexión del {timezone.now().strftime('%d/%m/%Y')}",
            contenido=contenido,
            etiquetas=etiquetas,
            tipo='espontanea',
            estado_animo_post=int(estado_animo_post) if estado_animo_post else None
        )

        # Actualizar racha de escritura
        racha, _ = RachaEscritura.objects.get_or_create(usuario=request.user)
        racha_crecio = racha.actualizar_racha(timezone.now().date())

        # Otorgar puntos de Sabiduría
        virtud_sabiduria = Virtud.objects.get(usuario=request.user, tipo='sabiduria')
        virtud_sabiduria.puntos += 5
        nivel_subio = virtud_sabiduria.actualizar_nivel()

        # Mensaje de éxito
        messages.success(request, '¡Reflexión guardada! +5 puntos de Sabiduría.')

        # Verificar si desbloqueó insignias por racha
        if racha_crecio:
            verificar_insignias_racha(request.user, racha.dias_consecutivos)

        return redirect('diario:logos_ver_reflexion', reflexion_id=reflexion.id)

    # GET: Mostrar formulario
    return render(request, 'diario/logos_escritura_libre.html')


@login_required
def logos_ver_reflexion(request, reflexion_id):
    """
    Vista para ver una reflexión específica.
    """
    reflexion = get_object_or_404(ReflexionLibre, id=reflexion_id, usuario=request.user)

    context = {
        'reflexion': reflexion,
    }

    return render(request, 'diario/logos_ver_reflexion.html', context)


@login_required
def logos_editar_reflexion(request, reflexion_id):
    """
    Vista para editar una reflexión existente.
    """
    reflexion = get_object_or_404(ReflexionLibre, id=reflexion_id, usuario=request.user)

    if request.method == 'POST':
        reflexion.titulo = request.POST.get('titulo', '').strip()
        reflexion.contenido = request.POST.get('contenido', '').strip()
        reflexion.etiquetas = request.POST.get('etiquetas', '').strip()

        estado_animo_post = request.POST.get('estado_animo_post')
        if estado_animo_post:
            reflexion.estado_animo_post = int(estado_animo_post)

        reflexion.save()

        messages.success(request, 'Reflexión actualizada correctamente.')
        return redirect('diario:logos_ver_reflexion', reflexion_id=reflexion.id)

    context = {
        'reflexion': reflexion,
    }

    return render(request, 'diario/logos_editar_reflexion.html', context)


@login_required
def logos_lista_reflexiones(request):
    """
    Vista para listar todas las reflexiones del usuario con filtros.
    """
    reflexiones = ReflexionLibre.objects.filter(usuario=request.user)

    # Filtros
    tipo_filtro = request.GET.get('tipo')
    if tipo_filtro:
        reflexiones = reflexiones.filter(tipo=tipo_filtro)

    etiqueta_filtro = request.GET.get('etiqueta')
    if etiqueta_filtro:
        reflexiones = reflexiones.filter(etiquetas__icontains=etiqueta_filtro)

    busqueda = request.GET.get('q')
    if busqueda:
        reflexiones = reflexiones.filter(
            Q(titulo__icontains=busqueda) | Q(contenido__icontains=busqueda)
        )

    reflexiones = reflexiones.order_by('-fecha')

    # Obtener todas las etiquetas únicas del usuario
    todas_reflexiones = ReflexionLibre.objects.filter(usuario=request.user)
    etiquetas_set = set()
    for r in todas_reflexiones:
        if r.etiquetas:
            etiquetas_set.update([e.strip() for e in r.etiquetas.split(',')])
    etiquetas_disponibles = sorted(list(etiquetas_set))

    context = {
        'reflexiones': reflexiones,
        'etiquetas_disponibles': etiquetas_disponibles,
        'tipo_filtro': tipo_filtro,
        'etiqueta_filtro': etiqueta_filtro,
        'busqueda': busqueda,
    }

    return render(request, 'diario/logos_lista_reflexiones.html', context)


# ============================================
# REFLEXIONES GUIADAS
# ============================================

@login_required
def logos_reflexion_guiada(request, slug):
    """
    Vista para completar una reflexión guiada específica.
    """
    tema = get_object_or_404(ReflexionGuiadaTema, slug=slug, activa=True)

    # Verificar si el usuario ya completó esta reflexión
    ya_completada = ReflexionLibre.objects.filter(
        usuario=request.user,
        reflexion_guiada=tema
    ).exists()

    if request.method == 'POST':
        contenido = request.POST.get('contenido', '').strip()
        estado_animo_post = request.POST.get('estado_animo_post')

        if not contenido:
            messages.error(request, 'Debes escribir tu reflexión antes de guardar.')
            return redirect('diario:logos_reflexion_guiada', slug=slug)

        # Crear la reflexión
        reflexion = ReflexionLibre.objects.create(
            usuario=request.user,
            titulo=tema.titulo,
            contenido=contenido,
            tipo='guiada',
            reflexion_guiada=tema,
            estado_animo_post=int(estado_animo_post) if estado_animo_post else None
        )

        # Actualizar estadísticas del tema
        tema.veces_completada += 1
        tema.save()

        # Actualizar racha de escritura
        racha, _ = RachaEscritura.objects.get_or_create(usuario=request.user)
        racha_crecio = racha.actualizar_racha(timezone.now().date())

        # Otorgar puntos de virtudes
        virtud_sabiduria, created_sabiduria = Virtud.objects.get_or_create(
            usuario=request.user,
            tipo='sabiduria',
            defaults={'puntos': 0, 'nivel': 1}  # Eliminamos el campo 'nombre'
        )
        virtud_sabiduria.puntos += 10
        virtud_sabiduria.actualizar_nivel()

        # 2. Virtud de la Justicia (si aplica)
        if tema.categoria == 'social':
            virtud_justicia, created_justicia = Virtud.objects.get_or_create(
                usuario=request.user,
                tipo='justicia',
                defaults={'puntos': 0, 'nivel': 1}  # Eliminamos el campo 'nombre'
            )
            virtud_justicia.puntos += 5
            virtud_justicia.actualizar_nivel()

        # Verificar insignias
        verificar_insignias_reflexiones_guiadas(request.user)

        messages.success(request, f'¡Reflexión completada! +10 puntos de Sabiduría.')
        return redirect('diario:logos_ver_reflexion', reflexion_id=reflexion.id)

    context = {
        'tema': tema,
        'ya_completada': ya_completada,
        'preguntas': tema.get_preguntas(),
    }

    return render(request, 'diario/logos_reflexion_guiada.html', context)


@login_required
def logos_calendario_reflexiones(request):
    """
    Vista para ver el calendario anual de reflexiones guiadas.
    """
    reflexiones = ReflexionGuiadaTema.objects.filter(
        activa=True
    ).order_by('fecha_activacion')

    # Agrupar por mes
    reflexiones_por_mes = {}
    for reflexion in reflexiones:
        mes = reflexion.fecha_activacion.month
        if mes not in reflexiones_por_mes:
            reflexiones_por_mes[mes] = []
        reflexiones_por_mes[mes].append(reflexion)

    context = {
        'reflexiones_por_mes': reflexiones_por_mes,
    }

    return render(request, 'diario/logos_calendario.html', context)


# ============================================
# FUNCIONES AUXILIARES PARA INSIGNIAS
# ============================================

def verificar_insignias_racha(usuario, dias_consecutivos):
    """
    Verifica y otorga insignias basadas en rachas de escritura.
    """
    insignias_racha = {
        7: 'racha_7_dias',
        14: 'racha_14_dias',
        30: 'racha_30_dias',
        60: 'racha_60_dias',
        100: 'racha_100_dias',
        365: 'racha_365_dias',
    }

    for dias, codigo in insignias_racha.items():
        if dias_consecutivos >= dias:
            try:
                insignia = Insignia.objects.get(codigo=codigo)
                InsigniaUsuario.objects.get_or_create(
                    usuario=usuario,
                    insignia=insignia
                )
            except Insignia.DoesNotExist:
                pass


def verificar_insignias_reflexiones_guiadas(usuario):
    """
    Verifica y otorga insignias basadas en reflexiones guiadas completadas.
    """
    total_guiadas = ReflexionLibre.objects.filter(
        usuario=usuario,
        tipo='guiada'
    ).count()

    insignias_guiadas = {
        1: 'primera_reflexion_guiada',
        5: 'explorador_curioso',
        10: 'mente_abierta',
        25: 'buscador_sabiduria',
        50: 'filosofo_practico',
    }

    for cantidad, codigo in insignias_guiadas.items():
        if total_guiadas >= cantidad:
            try:
                insignia = Insignia.objects.get(codigo=codigo)
                InsigniaUsuario.objects.get_or_create(
                    usuario=usuario,
                    insignia=insignia
                )
            except Insignia.DoesNotExist:
                pass


# ============================================
# VISTAS PARA EL SISTEMA DE VIRTUDES E INSIGNIAS
# Añadir estas vistas al archivo diario/views.py
# ============================================

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Virtud, Insignia, InsigniaUsuario


@login_required
def virtudes_dashboard(request):
    """
    Dashboard principal de virtudes.
    Muestra las 4 virtudes del usuario con su progreso.
    """
    virtudes = Virtud.objects.filter(usuario=request.user).order_by('tipo')

    # Insignias recientes no vistas
    insignias_nuevas = InsigniaUsuario.objects.filter(
        usuario=request.user,
        vista=False
    ).select_related('insignia')

    # Marcar insignias como vistas
    if insignias_nuevas.exists():
        insignias_nuevas.update(vista=True)

    # Total de insignias desbloqueadas
    total_insignias = InsigniaUsuario.objects.filter(usuario=request.user).count()
    total_insignias_disponibles = Insignia.objects.filter(activa=True, es_secreta=False).count()

    context = {
        'virtudes': virtudes,
        'insignias_nuevas': insignias_nuevas,
        'total_insignias': total_insignias,
        'total_insignias_disponibles': total_insignias_disponibles,
    }

    return render(request, 'diario/virtudes_dashboard.html', context)


@login_required
def virtud_detalle(request, tipo):
    """
    Vista detallada de una virtud específica.
    Muestra progreso, insignias relacionadas, y consejos para mejorarla.
    """
    virtud = get_object_or_404(Virtud, usuario=request.user, tipo=tipo)

    # Insignias relacionadas con esta virtud
    insignias_relacionadas = Insignia.objects.filter(
        virtud_asociada=tipo,
        activa=True
    ).order_by('orden')

    # Verificar cuáles ha desbloqueado el usuario
    insignias_desbloqueadas_ids = InsigniaUsuario.objects.filter(
        usuario=request.user,
        insignia__virtud_asociada=tipo
    ).values_list('insignia_id', flat=True)

    # Consejos para mejorar la virtud
    consejos = obtener_consejos_virtud(tipo)

    context = {
        'virtud': virtud,
        'insignias_relacionadas': insignias_relacionadas,
        'insignias_desbloqueadas_ids': list(insignias_desbloqueadas_ids),
        'consejos': consejos,
    }

    return render(request, 'diario/virtud_detalle.html', context)


@login_required
def insignias_lista(request):
    """
    Vista de todas las insignias disponibles y desbloqueadas.
    """
    # Todas las insignias activas
    insignias = Insignia.objects.filter(activa=True).order_by('virtud_asociada', 'orden')

    # Insignias que el usuario ha desbloqueado
    insignias_usuario = InsigniaUsuario.objects.filter(
        usuario=request.user
    ).values_list('insignia_id', flat=True)

    # Agrupar por virtud
    insignias_por_virtud = {}
    for insignia in insignias:
        virtud = insignia.get_virtud_asociada_display()
        if virtud not in insignias_por_virtud:
            insignias_por_virtud[virtud] = []

        insignias_por_virtud[virtud].append({
            'insignia': insignia,
            'desbloqueada': insignia.id in insignias_usuario
        })

    context = {
        'insignias_por_virtud': insignias_por_virtud,
        'total_desbloqueadas': len(insignias_usuario),
        'total_disponibles': insignias.count(),
    }

    return render(request, 'diario/insignias_lista.html', context)


def obtener_consejos_virtud(tipo):
    """
    Retorna consejos personalizados para mejorar cada virtud.
    """
    consejos_dict = {
        'sabiduria': [
            'Completa tu entrada de Prosoche diariamente para reflexionar sobre tus acciones.',
            'Lee al menos un capítulo de un libro en Gnosis cada semana.',
            'Completa ejercicios de Areté regularmente para entrenar tu mente.',
            'Escribe reflexiones guiadas cuando aparezcan en el calendario.',
        ],
        'coraje': [
            'Enfrenta tus miedos escribiendo sobre ellos en Logos.',
            'Mantén tu racha de escritura incluso en días difíciles.',
            'Completa reflexiones guiadas sobre temas que te incomoden.',
            'Vuelve a escribir después de una ausencia prolongada.',
        ],
        'justicia': [
            'Registra interacciones significativas en Simbiosis.',
            'Reflexiona sobre cómo puedes servir mejor a otros.',
            'Completa reflexiones guiadas sobre causas sociales.',
            'Mejora la salud de tus relaciones importantes.',
        ],
        'templanza': [
            'Mantén balance en los 6 pilares de tu vida.',
            'Registra tu seguimiento de Vires consistentemente.',
            'Evita extremos en tus hábitos y rutinas.',
            'Practica la moderación en todas las áreas.',
        ],
    }

    return consejos_dict.get(tipo, [])


# ============================================
# SCRIPT PARA CREAR INSIGNIAS INICIALES
# ============================================

def crear_insignias_iniciales():
    """
    Crea las insignias iniciales del sistema.
    Ejecutar una vez después de las migraciones.
    """
    insignias = [
        # SABIDURÍA
        {
            'codigo': 'primera_reflexion_guiada',
            'nombre': 'Primer Paso',
            'descripcion': 'Completaste tu primera reflexión guiada',
            'virtud_asociada': 'sabiduria',
            'icono': 'fa-seedling',
            'color': '#4CAF50',
            'criterio_logro': 'Completar 1 reflexión guiada',
            'puntos_virtud': 10,
            'orden': 1,
        },
        {
            'codigo': 'explorador_curioso',
            'nombre': 'Explorador Curioso',
            'descripcion': 'Completaste 5 reflexiones guiadas',
            'virtud_asociada': 'sabiduria',
            'icono': 'fa-compass',
            'color': '#2196F3',
            'criterio_logro': 'Completar 5 reflexiones guiadas',
            'puntos_virtud': 15,
            'orden': 2,
        },
        {
            'codigo': 'mente_abierta',
            'nombre': 'Mente Abierta',
            'descripcion': 'Completaste 10 reflexiones guiadas',
            'virtud_asociada': 'sabiduria',
            'icono': 'fa-brain',
            'color': '#9C27B0',
            'criterio_logro': 'Completar 10 reflexiones guiadas',
            'puntos_virtud': 20,
            'orden': 3,
        },
        {
            'codigo': 'buscador_sabiduria',
            'nombre': 'Buscador de Sabiduría',
            'descripcion': 'Completaste 25 reflexiones guiadas',
            'virtud_asociada': 'sabiduria',
            'icono': 'fa-book-open',
            'color': '#FF9800',
            'criterio_logro': 'Completar 25 reflexiones guiadas',
            'puntos_virtud': 30,
            'orden': 4,
        },
        {
            'codigo': 'filosofo_practico',
            'nombre': 'Filósofo Práctico',
            'descripcion': 'Completaste 50 reflexiones guiadas',
            'virtud_asociada': 'sabiduria',
            'icono': 'fa-scroll',
            'color': '#795548',
            'criterio_logro': 'Completar 50 reflexiones guiadas',
            'puntos_virtud': 50,
            'orden': 5,
        },

        # CORAJE
        {
            'codigo': 'racha_7_dias',
            'nombre': 'Constancia Inicial',
            'descripcion': 'Escribiste durante 7 días consecutivos',
            'virtud_asociada': 'coraje',
            'icono': 'fa-fire',
            'color': '#FF5722',
            'criterio_logro': 'Racha de 7 días',
            'puntos_virtud': 15,
            'orden': 1,
        },
        {
            'codigo': 'racha_14_dias',
            'nombre': 'Disciplina Forjada',
            'descripcion': 'Escribiste durante 14 días consecutivos',
            'virtud_asociada': 'coraje',
            'icono': 'fa-fire',
            'color': '#FF5722',
            'criterio_logro': 'Racha de 14 días',
            'puntos_virtud': 20,
            'orden': 2,
        },
        {
            'codigo': 'racha_30_dias',
            'nombre': 'Hábito Inquebrantable',
            'descripcion': 'Escribiste durante 30 días consecutivos',
            'virtud_asociada': 'coraje',
            'icono': 'fa-fire',
            'color': '#FF5722',
            'criterio_logro': 'Racha de 30 días',
            'puntos_virtud': 30,
            'orden': 3,
        },
        {
            'codigo': 'racha_100_dias',
            'nombre': 'Voluntad de Hierro',
            'descripcion': 'Escribiste durante 100 días consecutivos',
            'virtud_asociada': 'coraje',
            'icono': 'fa-fire',
            'color': '#FF5722',
            'criterio_logro': 'Racha de 100 días',
            'puntos_virtud': 50,
            'orden': 4,
        },
        {
            'codigo': 'racha_365_dias',
            'nombre': 'Maestro del Tiempo',
            'descripcion': 'Escribiste durante 365 días consecutivos',
            'virtud_asociada': 'coraje',
            'icono': 'fa-crown',
            'color': '#FFD700',
            'criterio_logro': 'Racha de 365 días',
            'puntos_virtud': 100,
            'orden': 5,
        },

        # JUSTICIA
        {
            'codigo': 'primera_interaccion',
            'nombre': 'Conexión Humana',
            'descripcion': 'Registraste tu primera interacción significativa',
            'virtud_asociada': 'justicia',
            'icono': 'fa-handshake',
            'color': '#00BCD4',
            'criterio_logro': 'Registrar 1 interacción en Simbiosis',
            'puntos_virtud': 10,
            'orden': 1,
        },
        {
            'codigo': 'tejedor_lazos',
            'nombre': 'Tejedor de Lazos',
            'descripcion': 'Registraste 10 interacciones significativas',
            'virtud_asociada': 'justicia',
            'icono': 'fa-users',
            'color': '#3F51B5',
            'criterio_logro': 'Registrar 10 interacciones',
            'puntos_virtud': 20,
            'orden': 2,
        },

        # TEMPLANZA
        {
            'codigo': 'balance_semanal',
            'nombre': 'Equilibrio Semanal',
            'descripcion': 'Activaste los 6 pilares durante una semana',
            'virtud_asociada': 'templanza',
            'icono': 'fa-balance-scale',
            'color': '#607D8B',
            'criterio_logro': 'Todos los pilares activos en una semana',
            'puntos_virtud': 25,
            'orden': 1,
        },
        {
            'codigo': 'cuerpo_sano',
            'nombre': 'Mens Sana in Corpore Sano',
            'descripcion': 'Registraste tu seguimiento de Vires durante 30 días',
            'virtud_asociada': 'templanza',
            'icono': 'fa-heartbeat',
            'color': '#E91E63',
            'criterio_logro': 'Vires registrado 30 días',
            'puntos_virtud': 30,
            'orden': 2,
        },
    ]

    for insignia_data in insignias:
        Insignia.objects.get_or_create(
            codigo=insignia_data['codigo'],
            defaults=insignia_data
        )

    print(f"{len(insignias)} insignias creadas exitosamente.")


# ============================================
# ANÁLISIS DE HÁBITOS
# ============================================

@login_required
def analisis_habitos_mes_actual(request):
    """
    Vista completa con análisis detallado de hábitos del mes actual.
    """
    hoy = timezone.now().date()
    mes_nombre = hoy.strftime('%B')
    año = hoy.year

    # Obtener o crear ProsocheMes del mes actual
    prosoche_mes, _ = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_nombre,
        año=año
    )

    # Obtener hábitos del mes
    habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

    # Calcular días reales del mes
    mes_num = hoy.month
    dias_reales_del_mes = calendar.monthrange(año, mes_num)[1]
    dias_mes = list(range(1, dias_reales_del_mes + 1))

    # Preparar datos de hábitos con estadísticas completas
    habitos_con_dias = []

    for habito in habitos:
        dias_habito = []
        dias_completados = 0
        racha_actual = 0
        racha_mas_larga = 0
        racha_temp = 0

        # Calcular estadísticas por semana
        semanas_stats = {}

        for dia in dias_mes:
            try:
                dia_obj = ProsocheHabitoDia.objects.get(habito=habito, dia=dia)
                dias_habito.append(dia_obj)

                if dia_obj.completado:
                    dias_completados += 1
                    racha_temp += 1
                    racha_mas_larga = max(racha_mas_larga, racha_temp)
                else:
                    racha_temp = 0

                # Calcular semana del mes
                semana_num = ((dia - 1) // 7) + 1
                if semana_num not in semanas_stats:
                    semanas_stats[semana_num] = {'completados': 0, 'total': 0}
                semanas_stats[semana_num]['total'] += 1
                if dia_obj.completado:
                    semanas_stats[semana_num]['completados'] += 1

            except ProsocheHabitoDia.DoesNotExist:
                dias_habito.append(None)
                racha_temp = 0

                semana_num = ((dia - 1) // 7) + 1
                if semana_num not in semanas_stats:
                    semanas_stats[semana_num] = {'completados': 0, 'total': 0}
                semanas_stats[semana_num]['total'] += 1

        # Racha actual (desde hoy hacia atrás)
        for dia in range(hoy.day, 0, -1):
            try:
                dia_obj = ProsocheHabitoDia.objects.get(habito=habito, dia=dia)
                if dia_obj.completado:
                    racha_actual += 1
                else:
                    break
            except ProsocheHabitoDia.DoesNotExist:
                break

        # Calcular porcentaje sobre días transcurridos del mes
        dias_transcurridos = hoy.day
        porcentaje = (dias_completados / dias_transcurridos * 100) if dias_transcurridos > 0 else 0

        # Consistencia
        consistencia = 0
        if semanas_stats:
            porcentajes_semanales = [
                (s['completados'] / s['total'] * 100) if s['total'] > 0 else 0
                for s in semanas_stats.values()
            ]
            consistencia = sum(porcentajes_semanales) / len(porcentajes_semanales)

        # Mejor semana
        mejor_semana = 1
        mejor_porcentaje = 0
        for semana_num, stats in semanas_stats.items():
            porcentaje_semana = (stats['completados'] / stats['total'] * 100) if stats['total'] > 0 else 0
            if porcentaje_semana > mejor_porcentaje:
                mejor_porcentaje = porcentaje_semana
                mejor_semana = semana_num

        # Proyección de fin de mes
        if dias_transcurridos > 0:
            tasa_diaria = dias_completados / dias_transcurridos
            proyeccion_fin_mes = (tasa_diaria * dias_reales_del_mes / dias_reales_del_mes * 100)
        else:
            proyeccion_fin_mes = 0

        habitos_con_dias.append({
            'habito': habito,
            'dias': dias_habito,
            'estadisticas': {
                'dias_completados': dias_completados,
                'dias_transcurridos': dias_transcurridos,
                'dias_totales_mes': dias_reales_del_mes,
                'porcentaje': porcentaje,
                'racha_actual': racha_actual,
                'racha_mas_larga': racha_mas_larga,
                'consistencia': consistencia,
                'mejor_semana': mejor_semana,
                'proyeccion_fin_mes': proyeccion_fin_mes,
            }
        })

    # Estadísticas generales
    estadisticas = {}

    if habitos_con_dias:
        estadisticas['promedio_habitos'] = sum(
            h['estadisticas']['porcentaje'] for h in habitos_con_dias
        ) / len(habitos_con_dias)
        estadisticas['total_habitos'] = len(habitos_con_dias)
        estadisticas['mejor_habito'] = max(habitos_con_dias, key=lambda h: h['estadisticas']['porcentaje'])
        estadisticas['habito_a_mejorar'] = min(habitos_con_dias, key=lambda h: h['estadisticas']['porcentaje'])
    else:
        estadisticas['promedio_habitos'] = 0
        estadisticas['total_habitos'] = 0
        estadisticas['mejor_habito'] = None
        estadisticas['habito_a_mejorar'] = None

    # Entradas del mes para contexto
    entradas = ProsocheDiario.objects.filter(
        prosoche_mes=prosoche_mes
    ).order_by('fecha')

    estadisticas['total_entradas'] = entradas.count()
    estadisticas['porcentaje_dias_con_entrada'] = (
            entradas.count() / hoy.day * 100
    ) if hoy.day > 0 else 0

    # Insights automáticos
    insights = []

    if habitos_con_dias:
        # Insight 1: Hábito estrella
        mejor = estadisticas['mejor_habito']
        if mejor and mejor['estadisticas']['porcentaje'] >= 80:
            insights.append({
                'icono': 'fa-trophy',
                'titulo': 'Hábito Estrella del Mes',
                'descripcion': f'"{mejor["habito"].nombre}" va excelente con {mejor["estadisticas"]["porcentaje"]:.0f}% de éxito.',
                'sugerencia': 'Mantén el ritmo para terminar el mes con fuerza.'
            })

        # Insight 2: Hábito que necesita atención
        peor = estadisticas['habito_a_mejorar']
        if peor and peor['estadisticas']['porcentaje'] < 50:
            insights.append({
                'icono': 'fa-exclamation-triangle',
                'titulo': 'Necesita Atención',
                'descripcion': f'"{peor["habito"].nombre}" solo tiene {peor["estadisticas"]["porcentaje"]:.0f}% de éxito.',
                'sugerencia': f'Aún quedan {dias_reales_del_mes - hoy.day} días para mejorar.'
            })

        # Insight 3: Rachas activas
        rachas_activas = [h for h in habitos_con_dias if h['estadisticas']['racha_actual'] >= 3]
        if rachas_activas:
            insights.append({
                'icono': 'fa-fire',
                'titulo': 'Rachas Activas',
                'descripcion': f'Tienes {len(rachas_activas)} hábito(s) con racha activa de 3+ días.',
                'sugerencia': '¡No rompas la racha! La consistencia es clave.'
            })

    # Insight 4: Progreso general
    if estadisticas['promedio_habitos'] >= 70:
        insights.append({
            'icono': 'fa-chart-line',
            'titulo': 'Excelente Progreso',
            'descripcion': f'Tu promedio general es {estadisticas["promedio_habitos"]:.0f}%.',
            'sugerencia': 'Vas por buen camino. Sigue así.'
        })

    context = {
        'prosoche_mes': prosoche_mes,
        'habitos_con_dias': habitos_con_dias,
        'dias_mes': dias_mes,
        'estadisticas': estadisticas,
        'insights': insights,
        'hoy': hoy,
        'dias_restantes': dias_reales_del_mes - hoy.day,
    }

    return render(request, 'diario/analisis_habitos_completo.html', context)


def obtener_analisis_habitos_compacto(usuario):
    """
    Función auxiliar para obtener datos compactos de hábitos
    para mostrar en el dashboard principal.
    """
    hoy = timezone.now().date()
    mes_nombre = hoy.strftime('%B')
    año = hoy.year

    try:
        prosoche_mes = ProsocheMes.objects.get(
            usuario=usuario,
            mes=mes_nombre,
            año=año
        )
    except ProsocheMes.DoesNotExist:
        return None

    habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

    if not habitos.exists():
        return None

    # Calcular estadísticas básicas
    dias_transcurridos = hoy.day
    habitos_stats = []

    for habito in habitos[:3]:  # Solo los primeros 3 para el widget compacto
        dias_completados = ProsocheHabitoDia.objects.filter(
            habito=habito,
            dia__lte=dias_transcurridos,
            completado=True
        ).count()

        porcentaje = (dias_completados / dias_transcurridos * 100) if dias_transcurridos > 0 else 0

        # Racha actual
        racha_actual = 0
        for dia in range(hoy.day, 0, -1):
            try:
                dia_obj = ProsocheHabitoDia.objects.get(habito=habito, dia=dia)
                if dia_obj.completado:
                    racha_actual += 1
                else:
                    break
            except ProsocheHabitoDia.DoesNotExist:
                break

        habitos_stats.append({
            'habito': habito,
            'porcentaje': porcentaje,
            'racha_actual': racha_actual,
            'dias_completados': dias_completados,
            'dias_transcurridos': dias_transcurridos,
        })

    # Promedio general
    promedio_general = sum(h['porcentaje'] for h in habitos_stats) / len(habitos_stats) if habitos_stats else 0

    return {
        'habitos': habitos_stats,
        'promedio_general': promedio_general,
        'total_habitos': habitos.count(),
        'dias_transcurridos': dias_transcurridos,
    }


# ============================================
# NUEVAS VISTAS: Análisis Anual e Histórico
# ============================================

import calendar
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Avg
from collections import defaultdict

from .models import ProsocheMes, ProsocheHabito, ProsocheHabitoDia, ProsocheDiario


@login_required
def analisis_habitos_anual(request, año=None):
    """
    Vista de análisis de hábitos para un año completo.
    Muestra estadísticas agregadas de todos los meses del año.
    """
    if año is None:
        año = timezone.now().year

    # Obtener todos los meses del año
    meses_prosoche = ProsocheMes.objects.filter(
        usuario=request.user,
        año=año
    ).order_by('mes')

    if not meses_prosoche.exists():
        context = {
            'año': año,
            'sin_datos': True,
            'años_disponibles': ProsocheMes.objects.filter(
                usuario=request.user
            ).values_list('año', flat=True).distinct().order_by('-año')
        }
        return render(request, 'diario/analisis_habitos_anual.html', context)

    # Recopilar todos los hábitos del año (únicos por nombre)
    habitos_del_año = {}

    for prosoche_mes in meses_prosoche:
        habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

        for habito in habitos:
            nombre = habito.nombre
            if nombre not in habitos_del_año:
                habitos_del_año[nombre] = {
                    'nombre': nombre,
                    'color': habito.color,
                    'meses_activo': [],
                    'total_dias_completados': 0,
                    'total_dias_posibles': 0,
                    'porcentaje_anual': 0,
                    'mejor_mes': None,
                    'peor_mes': None,
                    'meses_con_datos': 0,
                }

            # Calcular estadísticas del hábito en este mes
            mes_num = list(calendar.month_name).index(prosoche_mes.mes)
            dias_del_mes = calendar.monthrange(año, mes_num)[1]

            dias_completados = ProsocheHabitoDia.objects.filter(
                habito=habito,
                completado=True
            ).count()

            porcentaje_mes = (dias_completados / dias_del_mes * 100) if dias_del_mes > 0 else 0

            habitos_del_año[nombre]['meses_activo'].append({
                'mes': prosoche_mes.mes,
                'mes_num': mes_num,
                'dias_completados': dias_completados,
                'dias_totales': dias_del_mes,
                'porcentaje': porcentaje_mes
            })

            habitos_del_año[nombre]['total_dias_completados'] += dias_completados
            habitos_del_año[nombre]['total_dias_posibles'] += dias_del_mes
            habitos_del_año[nombre]['meses_con_datos'] += 1

            # Actualizar mejor y peor mes
            if (habitos_del_año[nombre]['mejor_mes'] is None or
                    porcentaje_mes > habitos_del_año[nombre]['mejor_mes']['porcentaje']):
                habitos_del_año[nombre]['mejor_mes'] = {
                    'mes': prosoche_mes.mes,
                    'porcentaje': porcentaje_mes
                }

            if (habitos_del_año[nombre]['peor_mes'] is None or
                    porcentaje_mes < habitos_del_año[nombre]['peor_mes']['porcentaje']):
                habitos_del_año[nombre]['peor_mes'] = {
                    'mes': prosoche_mes.mes,
                    'porcentaje': porcentaje_mes
                }

    # Calcular porcentaje anual para cada hábito
    for habito_data in habitos_del_año.values():
        if habito_data['total_dias_posibles'] > 0:
            habito_data['porcentaje_anual'] = (
                    habito_data['total_dias_completados'] /
                    habito_data['total_dias_posibles'] * 100
            )

    # Convertir a lista y ordenar por porcentaje
    habitos_lista = sorted(
        habitos_del_año.values(),
        key=lambda x: x['porcentaje_anual'],
        reverse=True
    )

    # Estadísticas generales del año
    estadisticas = {
        'total_habitos': len(habitos_lista),
        'meses_con_datos': meses_prosoche.count(),
        'promedio_anual': sum(h['porcentaje_anual'] for h in habitos_lista) / len(
            habitos_lista) if habitos_lista else 0,
        'mejor_habito': habitos_lista[0] if habitos_lista else None,
        'habito_a_mejorar': habitos_lista[-1] if habitos_lista else None,
    }

    # Entradas del año
    total_entradas = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=request.user,
        prosoche_mes__año=año
    ).count()

    # Calcular días transcurridos del año
    hoy = timezone.now().date()
    if hoy.year == año:
        dias_transcurridos_año = hoy.timetuple().tm_yday
    else:
        dias_transcurridos_año = 365 if año % 4 != 0 else 366

    estadisticas['total_entradas'] = total_entradas
    estadisticas['porcentaje_dias_con_entrada'] = (
            total_entradas / dias_transcurridos_año * 100
    ) if dias_transcurridos_año > 0 else 0

    # Insights del año
    insights = []

    if habitos_lista:
        # Insight 1: Hábito más consistente del año
        mejor = estadisticas['mejor_habito']
        if mejor and mejor['porcentaje_anual'] >= 70:
            insights.append({
                'icono': 'fa-trophy',
                'titulo': 'Campeón del Año',
                'descripcion': f'"{mejor["nombre"]}" fue tu hábito más consistente con {mejor["porcentaje_anual"]:.0f}% de éxito.',
                'sugerencia': 'Analiza qué hizo que este hábito funcionara tan bien.'
            })

        # Insight 2: Evolución general
        if estadisticas['promedio_anual'] >= 60:
            insights.append({
                'icono': 'fa-chart-line',
                'titulo': 'Año Exitoso',
                'descripcion': f'Tu promedio anual fue {estadisticas["promedio_anual"]:.0f}%. ¡Excelente consistencia!',
                'sugerencia': 'Mantén este nivel de compromiso el próximo año.'
            })

        # Insight 3: Hábitos con mejora progresiva
        habitos_mejorando = [h for h in habitos_lista if h['meses_con_datos'] >= 3]
        for habito in habitos_mejorando:
            meses = sorted(habito['meses_activo'], key=lambda x: x['mes_num'])
            if len(meses) >= 3:
                primera_mitad = sum(m['porcentaje'] for m in meses[:len(meses) // 2]) / (len(meses) // 2)
                segunda_mitad = sum(m['porcentaje'] for m in meses[len(meses) // 2:]) / (len(meses) - len(meses) // 2)

                if segunda_mitad > primera_mitad + 15:
                    insights.append({
                        'icono': 'fa-arrow-trend-up',
                        'titulo': 'Mejora Progresiva',
                        'descripcion': f'"{habito["nombre"]}" mejoró significativamente durante el año.',
                        'sugerencia': 'Este hábito está consolidándose. Sigue así.'
                    })
                    break

    # Años disponibles para navegación
    años_disponibles = ProsocheMes.objects.filter(
        usuario=request.user
    ).values_list('año', flat=True).distinct().order_by('-año')

    context = {
        'año': año,
        'habitos': habitos_lista,
        'estadisticas': estadisticas,
        'insights': insights,
        'sin_datos': False,
        'años_disponibles': años_disponibles,
        'vista': 'anual',
    }

    return render(request, 'diario/analisis_habitos_anual.html', context)


@login_required
def analisis_habitos_historico(request):
    """
    Vista de análisis histórico de todos los hábitos registrados.
    Muestra estadísticas de todos los años.
    """
    # Obtener todos los meses registrados
    todos_los_meses = ProsocheMes.objects.filter(
        usuario=request.user
    ).order_by('año', 'mes')

    if not todos_los_meses.exists():
        context = {
            'sin_datos': True,
        }
        return render(request, 'diario/analisis_habitos_historico.html', context)

    # Recopilar todos los hábitos históricos (únicos por nombre)
    habitos_historicos = {}
    años_con_datos = defaultdict(lambda: {
        'meses': 0,
        'entradas': 0,
        'habitos_activos': set()
    })

    for prosoche_mes in todos_los_meses:
        año = prosoche_mes.año
        años_con_datos[año]['meses'] += 1

        # Contar entradas del mes
        entradas_mes = ProsocheDiario.objects.filter(
            prosoche_mes=prosoche_mes
        ).count()
        años_con_datos[año]['entradas'] += entradas_mes

        habitos = ProsocheHabito.objects.filter(prosoche_mes=prosoche_mes)

        for habito in habitos:
            nombre = habito.nombre
            años_con_datos[año]['habitos_activos'].add(nombre)

            if nombre not in habitos_historicos:
                habitos_historicos[nombre] = {
                    'nombre': nombre,
                    'color': habito.color,
                    'años_activo': [],
                    'total_dias_completados': 0,
                    'total_dias_posibles': 0,
                    'porcentaje_historico': 0,
                    'primer_registro': prosoche_mes.año,
                    'ultimo_registro': prosoche_mes.año,
                    'meses_totales': 0,
                }

            # Calcular estadísticas del hábito en este mes
            mes_num = list(calendar.month_name).index(prosoche_mes.mes)
            dias_del_mes = calendar.monthrange(prosoche_mes.año, mes_num)[1]

            dias_completados = ProsocheHabitoDia.objects.filter(
                habito=habito,
                completado=True
            ).count()

            habitos_historicos[nombre]['total_dias_completados'] += dias_completados
            habitos_historicos[nombre]['total_dias_posibles'] += dias_del_mes
            habitos_historicos[nombre]['meses_totales'] += 1
            habitos_historicos[nombre]['ultimo_registro'] = max(
                habitos_historicos[nombre]['ultimo_registro'],
                prosoche_mes.año
            )

    # Calcular porcentaje histórico para cada hábito
    for habito_data in habitos_historicos.values():
        if habito_data['total_dias_posibles'] > 0:
            habito_data['porcentaje_historico'] = (
                    habito_data['total_dias_completados'] /
                    habito_data['total_dias_posibles'] * 100
            )

        # Calcular antigüedad
        habito_data['años_de_antiguedad'] = (
                habito_data['ultimo_registro'] - habito_data['primer_registro'] + 1
        )

    # Convertir a lista y ordenar
    habitos_lista = sorted(
        habitos_historicos.values(),
        key=lambda x: x['porcentaje_historico'],
        reverse=True
    )

    # Estadísticas generales históricas
    años_lista = sorted(años_con_datos.keys())

    estadisticas = {
        'total_habitos': len(habitos_lista),
        'años_registrados': len(años_lista),
        'primer_año': años_lista[0] if años_lista else None,
        'ultimo_año': años_lista[-1] if años_lista else None,
        'promedio_historico': sum(h['porcentaje_historico'] for h in habitos_lista) / len(
            habitos_lista) if habitos_lista else 0,
        'mejor_habito': habitos_lista[0] if habitos_lista else None,
        'habito_mas_antiguo': max(habitos_lista, key=lambda x: x['años_de_antiguedad']) if habitos_lista else None,
        'total_entradas': sum(año_data['entradas'] for año_data in años_con_datos.values()),
    }

    # Estadísticas por año
    años_estadisticas = []
    for año in sorted(años_lista, reverse=True):
        año_data = años_con_datos[año]
        años_estadisticas.append({
            'año': año,
            'meses': año_data['meses'],
            'entradas': año_data['entradas'],
            'habitos_unicos': len(año_data['habitos_activos']),
        })

    # Insights históricos
    insights = []

    if habitos_lista:
        # Insight 1: Hábito más consistente de todos los tiempos
        mejor = estadisticas['mejor_habito']
        if mejor:
            insights.append({
                'icono': 'fa-crown',
                'titulo': 'Leyenda Personal',
                'descripcion': f'"{mejor["nombre"]}" es tu hábito más consistente con {mejor["porcentaje_historico"]:.0f}% histórico.',
                'sugerencia': f'Has trabajado en este hábito durante {mejor["meses_totales"]} meses.'
            })

        # Insight 2: Hábito más antiguo
        mas_antiguo = estadisticas['habito_mas_antiguo']
        if mas_antiguo and mas_antiguo['años_de_antiguedad'] >= 2:
            insights.append({
                'icono': 'fa-hourglass',
                'titulo': 'Veterano',
                'descripcion': f'"{mas_antiguo["nombre"]}" lleva {mas_antiguo["años_de_antiguedad"]} años contigo.',
                'sugerencia': 'La persistencia es la clave del éxito.'
            })

        # Insight 3: Progreso general
        if estadisticas['promedio_historico'] >= 50:
            insights.append({
                'icono': 'fa-medal',
                'titulo': 'Compromiso Demostrado',
                'descripcion': f'Tu promedio histórico es {estadisticas["promedio_historico"]:.0f}%.',
                'sugerencia': 'Has demostrado consistencia a largo plazo.'
            })

    context = {
        'habitos': habitos_lista,
        'estadisticas': estadisticas,
        'años_estadisticas': años_estadisticas,
        'insights': insights,
        'sin_datos': False,
        'vista': 'historico',
    }

    return render(request, 'diario/analisis_habitos_historico.html', context)


import calendar
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import ProsocheMes, ProsocheHabito


@login_required
def copiar_habitos_mes_anterior(request):
    """
    Copia los hábitos del mes anterior que NO existan en el mes actual.
    Compara por nombre para evitar duplicados.
    """
    hoy = timezone.now().date()
    mes_actual_nombre = calendar.month_name[hoy.month]
    año_actual = hoy.year

    # Obtener o crear el ProsocheMes actual
    prosoche_mes_actual, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_actual_nombre,
        año=año_actual
    )

    # Calcular el mes anterior
    if hoy.month == 1:
        mes_anterior_num = 12
        año_anterior = año_actual - 1
    else:
        mes_anterior_num = hoy.month - 1
        año_anterior = año_actual

    mes_anterior_nombre = calendar.month_name[mes_anterior_num]

    # Buscar el ProsocheMes del mes anterior
    try:
        prosoche_mes_anterior = ProsocheMes.objects.get(
            usuario=request.user,
            mes=mes_anterior_nombre,
            año=año_anterior
        )
    except ProsocheMes.DoesNotExist:
        messages.error(
            request,
            f'No se encontró el mes anterior ({mes_anterior_nombre} {año_anterior}).'
        )
        return redirect('diario:prosoche_dashboard')

    # Obtener hábitos del mes anterior
    habitos_anteriores = ProsocheHabito.objects.filter(
        prosoche_mes=prosoche_mes_anterior
    )

    if not habitos_anteriores.exists():
        messages.warning(
            request,
            f'El mes anterior ({mes_anterior_nombre}) no tiene hábitos para copiar.'
        )
        return redirect('diario:prosoche_dashboard')

    # Obtener nombres de hábitos que YA existen en el mes actual
    habitos_actuales = ProsocheHabito.objects.filter(
        prosoche_mes=prosoche_mes_actual
    )
    nombres_existentes = set(habitos_actuales.values_list('nombre', flat=True))

    # Copiar solo los hábitos que NO existan (por nombre)
    habitos_copiados = 0
    habitos_omitidos = 0
    nombres_omitidos = []

    for habito_anterior in habitos_anteriores:
        # Verificar si ya existe un hábito con ese nombre
        if habito_anterior.nombre in nombres_existentes:
            habitos_omitidos += 1
            nombres_omitidos.append(habito_anterior.nombre)
            continue

        # Crear nuevo hábito
        nuevo_habito = ProsocheHabito.objects.create(
            prosoche_mes=prosoche_mes_actual,
            nombre=habito_anterior.nombre,
            color=habito_anterior.color,

        )
        habitos_copiados += 1
        nombres_existentes.add(habito_anterior.nombre)  # Añadir a la lista para evitar duplicados en el mismo proceso

    # Mensajes informativos
    if habitos_copiados > 0 and habitos_omitidos == 0:
        # Todos se copiaron
        messages.success(
            request,
            f'✅ Se copiaron {habitos_copiados} hábito(s) de {mes_anterior_nombre} {año_anterior}.'
        )
    elif habitos_copiados > 0 and habitos_omitidos > 0:
        # Algunos se copiaron, otros se omitieron
        mensaje = f'✅ Se copiaron {habitos_copiados} hábito(s) de {mes_anterior_nombre} {año_anterior}.'
        mensaje += f' Se omitieron {habitos_omitidos} hábito(s) que ya existían: {", ".join(nombres_omitidos)}.'
        messages.success(request, mensaje)
    elif habitos_copiados == 0 and habitos_omitidos > 0:
        # Todos ya existían
        messages.info(
            request,
            f'ℹ️ Todos los hábitos de {mes_anterior_nombre} ya existen en {mes_actual_nombre}. '
            f'No se copió nada.'
        )

    return redirect('diario:prosoche_dashboard')


# ============================================
# VISTA: Eliminar Hábito Individual
# ============================================

@login_required
def eliminar_habito(request, habito_id):
    """
    Elimina un hábito específico.
    Solo el propietario puede eliminar sus hábitos.
    """
    try:
        habito = ProsocheHabito.objects.get(id=habito_id)

        # Verificar que el hábito pertenece al usuario
        if habito.prosoche_mes.usuario != request.user:
            messages.error(request, '❌ No tienes permiso para eliminar este hábito.')
            return redirect('diario:prosoche_dashboard')

        nombre_habito = habito.nombre
        habito.delete()

        messages.success(
            request,
            f'✅ El hábito "{nombre_habito}" fue eliminado correctamente.'
        )

    except ProsocheHabito.DoesNotExist:
        messages.error(request, '❌ El hábito no existe.')

    return redirect('diario:prosoche_dashboard')


@login_required
def copiar_habitos_desde_mes(request, mes, año):
    """
    Copia hábitos desde un mes específico al mes actual.
    Útil si quieres copiar de un mes que no sea el anterior.

    Ejemplo de URL: /prosoche/copiar-habitos/October/2024/
    """
    hoy = timezone.now().date()
    mes_actual_nombre = calendar.month_name[hoy.month]
    año_actual = hoy.year

    # Obtener o crear el ProsocheMes actual
    prosoche_mes_actual, created = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=mes_actual_nombre,
        año=año_actual
    )

    # Verificar si ya tiene hábitos
    habitos_existentes = ProsocheHabito.objects.filter(
        prosoche_mes=prosoche_mes_actual
    ).count()

    if habitos_existentes > 0:
        messages.warning(
            request,
            f'El mes actual ({mes_actual_nombre}) ya tiene {habitos_existentes} hábito(s). '
            'Elimina los hábitos existentes antes de copiar.'
        )
        return redirect('diario:prosoche_dashboard')

    # Buscar el ProsocheMes de origen
    try:
        prosoche_mes_origen = ProsocheMes.objects.get(
            usuario=request.user,
            mes=mes,
            año=año
        )
    except ProsocheMes.DoesNotExist:
        messages.error(
            request,
            f'No se encontró el mes {mes} {año}.'
        )
        return redirect('diario:prosoche_dashboard')

    # Obtener hábitos del mes de origen
    habitos_origen = ProsocheHabito.objects.filter(
        prosoche_mes=prosoche_mes_origen
    )

    if not habitos_origen.exists():
        messages.warning(
            request,
            f'El mes {mes} {año} no tiene hábitos para copiar.'
        )
        return redirect('diario:prosoche_dashboard')

    # Copiar cada hábito
    habitos_copiados = 0
    for habito_origen in habitos_origen:
        nuevo_habito = ProsocheHabito.objects.create(
            prosoche_mes=prosoche_mes_actual,
            nombre=habito_origen.nombre,
            color=habito_origen.color,
            orden=habito_origen.orden
        )
        habitos_copiados += 1

    messages.success(
        request,
        f'✅ Se copiaron {habitos_copiados} hábito(s) de {mes} {año} '
        f'a {mes_actual_nombre} {año_actual}.'
    )

    return redirect('diario:prosoche_dashboard')


import json
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.timezone import localdate


def _insight_post_guardado(estado_animo: int, texto: str) -> str:
    # Recompensa simple por reglas (sin IA)
    texto_len = len((texto or "").strip())

    if texto_len == 0:
        return "Guardado. A veces solo registrar el día ya cuenta."
    if estado_animo <= 2 and texto_len > 120:
        return "Hoy no era fácil y aun así lo soltaste en palabras. Eso es fuerza real."
    if estado_animo >= 4 and texto_len > 120:
        return "Buen día + reflexión. Así es como se consolida la claridad."
    if texto_len < 80:
        return "Entrada breve, pero honesta. Mantener el hábito gana."
    return "Bien. Hoy has dejado una huella clara. Mañana lo agradecerás."


from django.utils.timezone import localdate
from .models import ProsocheDiario, ProsocheMes


def prosoche_entrada_rapida(request):
    fecha = localdate()

    # Obtener mes actual
    prosoche_mes, _ = ProsocheMes.objects.get_or_create(
        usuario=request.user,
        mes=fecha.strftime('%B'),
        año=fecha.year
    )

    if request.method == "POST":
        estado_animo = int(request.POST.get("estado_animo", 3))
        nota = (request.POST.get("nota_rapida") or "").strip()
        etiquetas = (request.POST.get("etiquetas") or "").strip()

        entrada, creada = ProsocheDiario.objects.get_or_create(
            prosoche_mes=prosoche_mes,
            fecha=fecha,
            defaults={
                "estado_animo": estado_animo,
                "etiquetas": etiquetas,
                "reflexiones_dia": nota,
            }
        )

        if not creada:
            entrada.estado_animo = estado_animo
            entrada.etiquetas = etiquetas
            if nota:
                if entrada.reflexiones_dia:
                    entrada.reflexiones_dia += "\n\n---\n\n" + nota
                else:
                    entrada.reflexiones_dia = nota
            entrada.save()

        return redirect("diario:dashboard_diario")

    return render(request, "diario/prosoche_entrada_rapida.html", {"fecha": fecha})
