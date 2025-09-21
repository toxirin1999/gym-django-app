from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
import json

from .models import (
    UserProfile, CalculoNivel1, CalculoNivel2, ProgresoNivel,
    SeguimientoPeso, ConfiguracionNivel3
)
from .forms import UserProfileForm, Nivel1Form, Nivel2Form, SeguimientoPesoForm
from .utils import CalculadoraNutricion, ValidadorNutricion


# En nutricion_app_django/views.py
# En nutricion_app_django/views.py

@login_required
def piramide_principal(request):
    """
    Vista principal de la pirámide nutricional.
    Prepara todos los datos necesarios para el panel de control.
    """
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # Obtenemos los datos más recientes de cada nivel.
    # .last() es eficiente y devuelve None si no hay resultados.
    ultimo_calculo_nivel1 = CalculoNivel1.objects.filter(user_profile=user_profile).last()
    ultimo_calculo_nivel2 = CalculoNivel2.objects.filter(user_profile=user_profile).last()

    # Calculamos los niveles completados de forma eficiente
    niveles_completados = ProgresoNivel.objects.filter(user_profile=user_profile, completado=True).count()

    context = {
        'user_profile': user_profile,
        'ultimo_calculo_nivel1': ultimo_calculo_nivel1,
        'ultimo_calculo_nivel2': ultimo_calculo_nivel2,
        'niveles_completados': niveles_completados,
    }

    return render(request, 'nutricion_app_django/piramide_principal.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

# --- ¡IMPORTA EL MODELO CLIENTE! ---
from clientes.models import Cliente
from .models import UserProfile
from .forms import UserProfileForm


@login_required
def configurar_perfil(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        es_edicion = True
    except UserProfile.DoesNotExist:
        user_profile = None
        es_edicion = False

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user_profile)
        if form.is_valid():
            with transaction.atomic():
                # Guardamos el perfil de nutrición
                nuevo_perfil_nutricion = form.save(commit=False)
                nuevo_perfil_nutricion.user = request.user
                nuevo_perfil_nutricion.save()

                # --- INICIO DE LA LÓGICA DE ENLACE ---
                try:
                    # Buscamos el perfil de Cliente asociado a este usuario
                    cliente = Cliente.objects.get(user=request.user)
                    # Enlazamos el perfil de nutrición recién creado/guardado al cliente
                    cliente.perfil_nutricion = nuevo_perfil_nutricion
                    cliente.save(update_fields=['perfil_nutricion'])  # Más eficiente

                    if es_edicion:
                        messages.success(request, 'Perfil de nutrición actualizado y sincronizado.')
                    else:
                        messages.success(request, '¡Perfil de nutrición creado y enlazado a tu cuenta!')

                except Cliente.DoesNotExist:
                    # Esto no debería pasar si todos los usuarios son clientes, pero es una buena práctica manejarlo
                    messages.warning(request,
                                     'Perfil de nutrición guardado, pero no se encontró una cuenta de cliente para enlazar.')
                # --- FIN DE LA LÓGICA DE ENLACE ---

                return redirect('nutricion_app_django:piramide_principal')
    else:
        form = UserProfileForm(instance=user_profile)

    context = {
        'form': form,
        'es_edicion': es_edicion,
        'user_profile': user_profile,
    }

    return render(request, 'nutricion_app_django/configurar_perfil.html', context)


# En nutricion_app_django/views.py

# En nutricion_app_django/views.py

@login_required
def nivel1_balance(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)

    if request.method == 'POST':
        form = Nivel1Form(request.POST)
        if form.is_valid():
            factor_actividad = form.cleaned_data['factor_actividad']

            with transaction.atomic():
                calorias_mantenimiento = CalculadoraNutricion.calcular_calorias_mantenimiento(
                    user_profile.peso, factor_actividad
                )
                calorias_objetivo, deficit_superavit = CalculadoraNutricion.calcular_calorias_objetivo(
                    calorias_mantenimiento, user_profile.objetivo
                )

                CalculoNivel1.objects.create(
                    user_profile=user_profile,
                    calorias_mantenimiento=calorias_mantenimiento,
                    calorias_objetivo=calorias_objetivo,
                    factor_actividad=factor_actividad,
                    deficit_superavit_porcentaje=deficit_superavit
                )
                ProgresoNivel.objects.update_or_create(
                    user_profile=user_profile, nivel=1,
                    defaults={'completado': True, 'fecha_completado': timezone.now()}
                )
                messages.success(request, '¡Nivel 1 calculado y guardado! Tus resultados han sido actualizados.')

            # Esta es la línea más importante. Se ejecuta después de un POST exitoso.
            return redirect('nutricion_app_django:nivel1_balance')
        else:
            # Si el formulario no es válido, mostramos los errores y volvemos a renderizar.
            # Esto es útil para depuración.
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en el campo '{field}': {error}")

    # --- Lógica para la petición GET (Carga de página) ---
    ultimo_calculo = CalculoNivel1.objects.filter(user_profile=user_profile).last()

    # El formulario se inicializa aquí para las peticiones GET
    initial_data = {'factor_actividad': ultimo_calculo.factor_actividad if ultimo_calculo else 1.7}
    form = Nivel1Form(initial=initial_data)

    # Preparar el resto del contexto
    diferencia_calorica = 0
    peso_objetivo_semanal = 0
    recomendaciones = []
    if ultimo_calculo:
        diferencia_calorica = ultimo_calculo.calorias_objetivo - ultimo_calculo.calorias_mantenimiento
        peso_objetivo_semanal = CalculadoraNutricion.calcular_peso_objetivo_semanal(user_profile.peso,
                                                                                    user_profile.objetivo)
        recomendaciones = CalculadoraNutricion.obtener_recomendaciones_nivel1(user_profile.objetivo,
                                                                              ultimo_calculo.deficit_superavit_porcentaje)

    context = {
        'form': form,
        'user_profile': user_profile,
        'ultimo_calculo': ultimo_calculo,
        'peso_objetivo_semanal': peso_objetivo_semanal,
        'recomendaciones': recomendaciones,
        'diferencia_calorica': diferencia_calorica,
    }
    return render(request, 'nutricion_app_django/nivel1_balance.html', context)


# En nutricion_app_django/views.py

@login_required
def nivel2_macros(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    calculo_nivel1 = CalculoNivel1.objects.filter(user_profile=user_profile).last()

    if not calculo_nivel1:
        messages.error(request, "Debes completar el Nivel 1 antes de continuar.")
        return redirect('nutricion_app_django:nivel1_balance')

    if request.method == 'POST':
        form = Nivel2Form(request.POST)
        if form.is_valid():
            # Extraemos los datos validados
            proteina_g_kg = form.cleaned_data['proteina_gramos_kg']
            grasa_pct = form.cleaned_data['grasa_porcentaje']

            # Calculamos los macros
            proteina_gramos = user_profile.peso * proteina_g_kg
            macros = CalculadoraNutricion.calcular_macronutrientes(
                calculo_nivel1.calorias_objetivo,
                proteina_gramos,
                grasa_pct,
                user_profile.peso
            )

            # Guardamos el nuevo cálculo
            with transaction.atomic():
                CalculoNivel2.objects.create(user_profile=user_profile, **macros)
                ProgresoNivel.objects.update_or_create(
                    user_profile=user_profile, nivel=2,
                    defaults={'completado': True, 'fecha_completado': timezone.now()}
                )
                messages.success(request, '¡Nivel 2 calculado y guardado!')

            # Redirigimos para seguir el patrón Post/Redirect/Get
            return redirect('nutricion_app_django:nivel2_macros')
        else:
            # Si el formulario no es válido, mostramos los errores
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Error en '{field}': {error}")

    # --- Lógica para peticiones GET ---

    ultimo_calculo_nivel2 = CalculoNivel2.objects.filter(user_profile=user_profile).last()

    # Valores iniciales para los sliders
    initial_proteina = 2.0
    initial_grasa = 25

    if ultimo_calculo_nivel2:
        # Si ya existe un cálculo, usamos sus valores
        initial_proteina = ultimo_calculo_nivel2.proteina_gramos / user_profile.peso
        initial_grasa = ultimo_calculo_nivel2.grasa_porcentaje
    else:
        # Si no, recomendamos según el objetivo del perfil
        if user_profile.objetivo == "Pérdida de grasa":
            initial_proteina = 2.4
        elif user_profile.objetivo == "Ganancia muscular":
            initial_proteina = 1.9

    context = {
        'form': Nivel2Form(),  # Pasamos una instancia vacía
        'user_profile': user_profile,
        'calculo_nivel1': calculo_nivel1,
        'ultimo_calculo_nivel2': ultimo_calculo_nivel2,
        'initial_proteina': initial_proteina,
        'initial_grasa': initial_grasa,
    }
    return render(request, 'nutricion_app_django/nivel2_macros.html', context)


# En nutricion_app_django/views.py
from .forms import Nivel3Form  # ¡No olvides importar el nuevo formulario!


@login_required
def nivel3_micros(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # Verificar que el nivel 2 esté completo
    if not ProgresoNivel.objects.filter(user_profile=user_profile, nivel=2, completado=True).exists():
        messages.error(request, 'Debes completar el Nivel 2 antes de continuar.')
        return redirect('nutricion_app_django:nivel2_macros')

    agua_recomendada = (user_profile.peso * 35) / 1000
    configuracion_guardada = ConfiguracionNivel3.objects.filter(user_profile=user_profile).first()

    if request.method == 'POST':
        form = Nivel3Form(request.POST)
        if form.is_valid():
            # Si el formulario es válido (todos los checks marcados), guardamos y redirigimos
            with transaction.atomic():
                ConfiguracionNivel3.objects.update_or_create(
                    user_profile=user_profile,
                    defaults={'agua_litros': agua_recomendada}
                )
                ProgresoNivel.objects.update_or_create(
                    user_profile=user_profile, nivel=3,
                    defaults={'completado': True, 'fecha_completado': timezone.now()}
                )
                messages.success(request, '¡Compromiso aceptado! Nivel 3 completado.')
            return redirect('nutricion_app_django:nivel4_timing')
        else:
            # Si no es válido, mostramos el error
            messages.error(request, "Debes aceptar todos los compromisos para poder continuar.")
    else:
        # Para peticiones GET, creamos un formulario vacío
        form = Nivel3Form()

    context = {
        'form': form,
        'user_profile': user_profile,
        'agua_recomendada': agua_recomendada,
        'configuracion_guardada': configuracion_guardada,
    }
    return render(request, 'nutricion_app_django/nivel3_micros.html', context)


@login_required
def seguimiento_peso(request):
    """Vista para el seguimiento de peso"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        messages.error(request, 'Primero debes configurar tu perfil.')
        return redirect('nutricion_app_django:configurar_perfil')

    if request.method == 'POST':
        form = SeguimientoPesoForm(request.POST)
        if form.is_valid():
            SeguimientoPeso.objects.create(
                user_profile=user_profile,
                peso=form.cleaned_data['peso'],
                notas=form.cleaned_data.get('notas', '')
            )
            messages.success(request, 'Peso registrado correctamente.')
            return redirect('nutricion_app_django:seguimiento_peso')
    else:
        form = SeguimientoPesoForm(initial={'peso': user_profile.peso})

    # Obtener historial de peso (últimos 30 registros)
    historial_peso = SeguimientoPeso.objects.filter(
        user_profile=user_profile
    ).order_by('-fecha_registro')[:30]

    context = {
        'form': form,
        'user_profile': user_profile,
        'historial_peso': historial_peso,
    }

    return render(request, 'nutricion_app_django/seguimiento_peso.html', context)


# Vista corregida para dashboard_completo.html
# Reemplaza la función dashboard_completo en tu views.py con esta versión corregida

import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

# En nutricion_app_django/views.py
from .models import ConfiguracionNivel4, ConfiguracionNivel5  # Asegúrate de importar estos modelos


@login_required
def dashboard_completo(request):
    """Vista para el dashboard nutricional completo, ahora más robusta."""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # Inicializamos el contexto con los datos básicos
    context = {
        'user_profile': user_profile,
        'ultimo_calculo_nivel1': None,
        'ultimo_calculo_nivel2': None,
        'configuracion_nivel3': None,
        'configuracion_nivel4': None,
        'configuracion_nivel5': None,
        'historial_peso': [],
        'historial_peso_json': "[]",
        'progreso': {},
        'calorias_macros': {},
        'niveles_completados': 0,
        'diferencia_calorica': 0,
    }

    # --- Nivel 1: Balance Energético ---
    ultimo_calculo_nivel1 = CalculoNivel1.objects.filter(user_profile=user_profile).last()
    if ultimo_calculo_nivel1:
        context['ultimo_calculo_nivel1'] = ultimo_calculo_nivel1
        context[
            'diferencia_calorica'] = ultimo_calculo_nivel1.calorias_objetivo - ultimo_calculo_nivel1.calorias_mantenimiento

    # --- Nivel 2: Macronutrientes ---
    ultimo_calculo_nivel2 = CalculoNivel2.objects.filter(user_profile=user_profile).last()
    if ultimo_calculo_nivel2:
        context['ultimo_calculo_nivel2'] = ultimo_calculo_nivel2
        context['calorias_macros'] = {
            'proteina': ultimo_calculo_nivel2.proteina_gramos * 4,
            'grasa': ultimo_calculo_nivel2.grasa_gramos * 9,
            'carbohidratos': ultimo_calculo_nivel2.carbohidratos_gramos * 4
        }

    # --- Nivel 3: Micronutrientes ---
    context['configuracion_nivel3'] = ConfiguracionNivel3.objects.filter(user_profile=user_profile).first()

    # --- Nivel 4: Timing ---
    context['configuracion_nivel4'] = ConfiguracionNivel4.objects.filter(user_profile=user_profile).first()

    # --- Nivel 5: Suplementos ---
    context['configuracion_nivel5'] = ConfiguracionNivel5.objects.filter(user_profile=user_profile).first()

    # --- Progreso de la Pirámide ---
    progreso_niveles = ProgresoNivel.objects.filter(user_profile=user_profile, completado=True).values_list('nivel',
                                                                                                            flat=True)
    niveles_completados_set = set(progreso_niveles)
    context['niveles_completados'] = len(niveles_completados_set)
    for i in range(1, 6):
        context['progreso'][f'nivel_{i}_completado'] = i in niveles_completados_set

    # --- Historial de Peso ---
    historial_peso = SeguimientoPeso.objects.filter(user_profile=user_profile).order_by('fecha_registro')
    if historial_peso.exists():
        context['historial_peso'] = historial_peso
        historial_peso_json = [
            {'fecha': r.fecha_registro.strftime('%Y-%m-%d'), 'peso': float(r.peso)}
            for r in historial_peso
        ]
        context['historial_peso_json'] = json.dumps(historial_peso_json)

    return render(request, 'nutricion_app_django/dashboard_completo.html', context)


@login_required
def ajax_calcular_preview(request):
    """Vista AJAX para calcular preview de macronutrientes"""
    if request.method == 'POST':
        try:
            user_profile = UserProfile.objects.get(user=request.user)

            # Obtener datos del POST
            proteina_gramos_kg = float(request.POST.get('proteina_gramos_kg', 2.0))
            grasa_porcentaje = int(request.POST.get('grasa_porcentaje', 25))

            # Obtener calorías objetivo del nivel 1
            calculo_nivel1 = CalculoNivel1.objects.filter(
                user_profile=user_profile
            ).latest('fecha_calculo')

            # Calcular proteína
            proteina_gramos = user_profile.peso * proteina_gramos_kg

            # Calcular macronutrientes
            macros = CalculadoraNutricion.calcular_macronutrientes(
                calculo_nivel1.calorias_objetivo,
                proteina_gramos,
                grasa_porcentaje,
                user_profile.peso
            )

            return JsonResponse({
                'success': True,
                'macros': macros
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})


# En nutricion_app_django/views.py

from .forms import Nivel4Form  # Asegúrate de importar el nuevo formulario
from .models import ConfiguracionNivel4  # Y el modelo


@login_required
def nivel4_timing(request):
    """Vista para el Nivel 4 - Timing y Frecuencia"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # Verificar que el nivel 3 esté completado
    if not ProgresoNivel.objects.filter(user_profile=user_profile, nivel=3, completado=True).exists():
        messages.error(request, 'Debes completar el Nivel 3 antes de continuar.')
        return redirect('nutricion_app_django:nivel3_micros')  # Asumiendo que la URL se llama así

    # Intentar obtener la configuración existente para pre-rellenar el formulario
    try:
        configuracion_existente = ConfiguracionNivel4.objects.get(user_profile=user_profile)
    except ConfiguracionNivel4.DoesNotExist:
        configuracion_existente = None

    if request.method == 'POST':
        form = Nivel4Form(request.POST, instance=configuracion_existente)
        if form.is_valid():
            with transaction.atomic():
                configuracion = form.save(commit=False)
                configuracion.user_profile = user_profile
                configuracion.save()

                # Marcar nivel como completado
                ProgresoNivel.objects.update_or_create(
                    user_profile=user_profile,
                    nivel=4,
                    defaults={'completado': True, 'fecha_completado': timezone.now()}
                )
                messages.success(request, 'Nivel 4 configurado. ¡Ya casi terminas!')
                return redirect('nutricion_app_django:nivel5_suplementos')  # Redirigir al Nivel 5
    else:
        # Inicializar con valores por defecto si no hay configuración guardada
        initial_data = {'comidas_por_dia': 4, 'timing_pre_entreno': 'carbohidratos',
                        'timing_post_entreno': 'proteina_carbohidratos', 'distribucion_macros': 'uniforme'}
        form = Nivel4Form(instance=configuracion_existente, initial=initial_data)

    context = {
        'form': form,
        'user_profile': user_profile,
    }
    return render(request, 'nutricion_app_django/nivel4_timing.html', context)


# En nutricion_app_django/views.py

from .forms import Nivel5Form  # Importar el nuevo formulario
from .models import ConfiguracionNivel5  # Y el modelo


@login_required
def nivel5_suplementos(request):
    """Vista para el Nivel 5 - Suplementos"""
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # Verificar que el nivel 4 esté completado
    if not ProgresoNivel.objects.filter(user_profile=user_profile, nivel=4, completado=True).exists():
        messages.error(request, 'Debes completar el Nivel 4 antes de continuar.')
        return redirect('nutricion_app_django:nivel4_timing')

    try:
        configuracion_existente = ConfiguracionNivel5.objects.get(user_profile=user_profile)
    except ConfiguracionNivel5.DoesNotExist:
        configuracion_existente = None

    if request.method == 'POST':
        form = Nivel5Form(request.POST, instance=configuracion_existente)
        if form.is_valid():
            with transaction.atomic():
                configuracion = form.save(commit=False)
                configuracion.user_profile = user_profile
                configuracion.save()

                # Marcar nivel como completado
                ProgresoNivel.objects.update_or_create(
                    user_profile=user_profile,
                    nivel=5,
                    defaults={'completado': True, 'fecha_completado': timezone.now()}
                )
                messages.success(request, '¡Felicidades! Has completado toda la pirámide nutricional.')
                return redirect('nutricion_app_django:dashboard_completo')
    else:
        form = Nivel5Form(instance=configuracion_existente)

    context = {
        'form': form,
        'user_profile': user_profile,
    }
    return render(request, 'nutricion_app_django/nivel5_suplementos.html', context)


# nutricion_app_django/views.py

# ... (tus otras importaciones)

@login_required
def vista_lista_niveles(request):
    """
    Esta vista se dedica exclusivamente a mostrar la lista detallada
    de los niveles de la pirámide para que el usuario interactúe con ellos.
    """
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        messages.error(request, 'Primero debes configurar tu perfil.')
        return redirect('nutricion_app_django:configurar_perfil')

    context = {
        'user_profile': user_profile,
        # Pasamos el perfil al contexto. La plantilla usará los métodos
        # que ya hemos definido en el modelo para obtener el resto de datos.
    }

    return render(request, 'nutricion_app_django/vista_lista_niveles.html', context)
