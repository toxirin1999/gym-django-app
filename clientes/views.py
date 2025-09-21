# Django Core Imports
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Avg, Count, F, Max, Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_GET, require_POST
from analytics.views import AnalizadorCargaYFatiga
from django.shortcuts import render, get_object_or_404
from logros.models import PerfilGamificacion, PruebaLegendaria, PruebaUsuario
import json
import logging
import random
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict

# Project-specific (App ) Imports
from analytics.analytics_predictivos import predecir_riesgo_abandono
from analytics.autorregulacion import calcular_ajuste_sesion
from analytics.notificaciones import generar_notificaciones_contextuales
from analytics.sistema_educacion_helms import NivelEducativo, SistemaEducacionHelms
from analytics.sistema_progresion_avanzada import (RegistroEjercicio,
                                                   RegistroSerie,
                                                   SistemaProgresionAvanzada)
from analytics.views import CalculadoraEjerciciosTabla
from entrenos.models import (DetalleEjercicioRealizado, EntrenoRealizado,
                             EstadoEmocional as EntrenoEstadoEmocional, LogroDesbloqueado,
                             SerieRealizada)

from joi.models import (Entrenamiento, EstadoEmocional, MotivacionUsuario,
                        RecuerdoEmocional)
from joi.utils import (frase_cambio_forma_joi, frase_motivadora_entrenador,
                       generar_respuesta_joi, obtener_estado_joi,
                       recuperar_frase_de_recaida)
from logros.models import PruebaLegendaria, PruebaUsuario
from logros.utils import obtener_datos_logros
from rutinas.models import Programa, Rutina

# Local App Imports
from .forms import (BitacoraDiariaForm, CheckinDiarioForm, ClienteForm,
                    DatosNutricionalesForm, MedidaForm,
                    ObjetivoClienteForm, ObjetivoPesoForm, PesoDiarioForm,
                    RevisionProgresoForm, SugerenciaForm)
from .models import (BitacoraDiaria, Cliente, EstadoSemanal, Medida,
                     ObjetivoCliente, ObjetivoPeso, PesoDiario, PlanNutricional,
                     RevisionProgreso, SugerenciaAceptada)
from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
from analytics.sistema_progresion_avanzada import SistemaProgresionAvanzada

# Importaciones para la app de nutrición
try:
    from nutricion_app_django.models import (
        UserProfile as NutricionUserProfile,
        CalculoNivel1, CalculoNivel2, ConfiguracionNivel3,
        ConfiguracionNivel4, ConfiguracionNivel5, ProgresoNivel,
        SeguimientoPeso
    )

    NUTRICION_DISPONIBLE = True
except ImportError:
    NUTRICION_DISPONIBLE = False
    print("⚠️ App de nutrición no disponible")

logger = logging.getLogger(__name__)


@login_required
def mapa_energia(request):
    cliente = request.user.cliente_perfil
    hoy = date.today()
    inicio = hoy - timedelta(days=27)  # últimas 4 semanas
    dias = []

    bitacoras = BitacoraDiaria.objects.filter(cliente=cliente, fecha__range=(inicio, hoy))
    bit_dict = {b.fecha: b for b in bitacoras}

    for i in range(28):
        fecha = inicio + timedelta(days=i)
        bit = bit_dict.get(fecha)
        energia = None

        if bit:
            sueño = float(bit.horas_sueno) if bit.horas_sueno else None
            rpe = float(bit.rpe) if bit.rpe else None

            if sueño is not None and rpe is not None:
                energia = (sueño / 8 + (10 - rpe) / 10) / 2
            elif sueño is not None:
                energia = sueño / 8
            elif rpe is not None:
                energia = (10 - rpe) / 10

        dias.append({
            "fecha": fecha,
            "valor": round(energia * 100) if energia is not None else None
        })

    return render(request, "clientes/mapa_energia.html", {"dias": dias})


from datetime import timedelta, date
from clientes.models import BitacoraDiaria


def obtener_energia_semanal(cliente):
    hoy = date.today()
    inicio = hoy - timedelta(days=27)
    bitacoras = BitacoraDiaria.objects.filter(cliente=cliente, fecha__range=(inicio, hoy))
    bit_dict = {b.fecha: b for b in bitacoras}
    dias = []

    for i in range(28):
        fecha = inicio + timedelta(days=i)
        bit = bit_dict.get(fecha)
        if bit:
            if bit.horas_sueno and bit.rpe:
                energia = (float(bit.horas_sueno) / 8 + (10 - float(bit.rpe)) / 10) / 2

            elif bit.horas_sueno:
                energia = bit.horas_sueno / 8
            elif bit.rpe:
                energia = (10 - bit.rpe) / 10
            else:
                energia = None
        else:
            energia = None

        dias.append({"valor": energia})

    return dias


@login_required
def obtener_bitacora_dia(request):
    cliente = request.user.cliente_perfil
    fecha_str = request.GET.get('fecha')

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        print("Cliente:", cliente)
        print("Fecha buscada:", fecha)
        print("Bitácoras disponibles:", BitacoraDiaria.objects.filter(cliente=cliente).values("fecha"))

        bitacora = BitacoraDiaria.objects.filter(cliente=cliente, fecha=fecha).first()
        print("💾 Bitácora encontrada:", bitacora.fecha, bitacora.emocion_dia)
        print("🔎 Buscando bitácora para:", cliente, fecha)

        if not bitacora:
            return JsonResponse({"error": "No hay bitácora en esa fecha"}, status=404)

        data = {
            "fecha": bitacora.fecha.strftime("%d %b %Y"),
            "emocion": bitacora.emocion_dia,
            "mindfulness": f"{'🧘 AM' if bitacora.mindfulness_am else ''} {'🧘 PM' if bitacora.mindfulness_pm else ''}",
            "cosas": bitacora.cosas_positivas,
            "aprendizaje": bitacora.aprendizaje,
        }
        return JsonResponse(data)

    except ValueError:
        return JsonResponse({"error": "Fecha inválida"}, status=400)


@login_required
def calendario_bitacoras(request):
    cliente = request.user.cliente_perfil
    hoy = date.today()
    year, month = hoy.year, hoy.month
    dias_mes = monthrange(year, month)[1]
    inicio_mes = date(year, month, 1)
    fin_mes = date(year, month, dias_mes)

    # ✅ primero obtenemos las bitácoras
    bitacoras = BitacoraDiaria.objects.filter(cliente=cliente, fecha__range=(inicio_mes, fin_mes)).order_by('fecha')

    # Luego las usamos para extraer datos
    labels = [b.fecha.strftime('%d/%m') for b in bitacoras]
    pesos = [float(b.peso_kg) if b.peso_kg else None for b in bitacoras]
    biceps = [float(b.circunferencia_biceps) if b.circunferencia_biceps else None for b in bitacoras]

    dias_con_bitacora = set(b.fecha.day for b in bitacoras)

    dias = []
    for d in range(1, dias_mes + 1):
        fecha = date(year, month, d)
        bitacora = next((b for b in bitacoras if b.fecha.day == d), None)

        if bitacora:
            emocion = (bitacora.emocion_dia or "").strip().lower()
            positivas = ['feliz', 'contento', 'tranquilo', 'motivado', 'alegria', 'alegre']
            neutras = ['neutral', 'meh', 'estable']
            negativas = ['triste', 'agotado', 'solo', 'estresado', 'cansado', 'ansioso']

            if emocion in positivas:
                color = 'verde'
            elif emocion in neutras:
                color = 'amarillo'
            elif emocion in negativas:
                color = 'rojo'
            elif emocion and emocion.isalpha():
                color = 'gris'
            else:
                color = 'vacio'
        else:
            color = 'vacio'

        dias.append({"dia": d, "estado": color})

    return render(request, "clientes/calendario_bitacoras.html", {
        "dias": dias,
        "mes": hoy.month,
        "año": year,
        'labels': labels,
        'pesos': pesos,
        'biceps': biceps,
    })


@login_required
def responder_sugerencia(request):
    cliente = request.user.cliente_perfil
    lunes = date.today() - timedelta(days=date.today().weekday())
    estado = EstadoSemanal.objects.filter(cliente=cliente, semana_inicio=lunes).first()

    tipo = 'mantener'
    if estado:
        if estado.humor_dominante == 'rojo' or estado.promedio_rpe >= 8 or estado.promedio_sueno < 6:
            tipo = 'bajar'
        elif estado.humor_dominante == 'verde' and estado.promedio_sueno >= 7 and estado.promedio_rpe <= 7:
            tipo = 'subir'

    if request.method == 'POST':
        decision = request.POST.get('decision')
        aceptada = (decision == 'aceptar')

        SugerenciaAceptada.objects.update_or_create(
            cliente=cliente,
            semana_inicio=lunes,
            defaults={'tipo': tipo, 'aceptada': aceptada}
        )

        # Ejemplo de guardar como recuerdo (opcional)
        if aceptada:
            RecuerdoEmocional.objects.create(
                user=cliente.user,
                contenido=f"Aceptaste sugerencia de Joi: {tipo}"
            )

        return redirect('panel_cliente')

    form = SugerenciaForm()
    return render(request, 'clientes/responder_sugerencia.html', {
        'form': form,
        'tipo': tipo,
        'cliente': cliente
    })


def sugerencia_carga_joi(cliente):
    estado = EstadoSemanal.objects.filter(cliente=cliente).order_by('-semana_inicio').first()
    if not estado:
        return None

    if estado.humor_dominante == 'rojo' or estado.promedio_sueno < 6 or estado.promedio_rpe >= 8.5:
        return "⚠️ Esta semana muestra signos de fatiga. Considera reducir el peso en tus próximos entrenos un 10 %."
    elif estado.humor_dominante == 'verde' and estado.promedio_sueno >= 7 and estado.promedio_rpe <= 7:
        return "🚀 Semana óptima. Si te sientes fuerte, puedes aumentar un 10 % el peso o volumen."
    else:
        return "🔄 Semana estable. Mantén tu rutina sin cambios grandes, escucha tu cuerpo."


def obtener_lunes_actual():
    hoy = date.today()
    return hoy - timedelta(days=hoy.weekday())


def evaluar_retos(cliente):
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    entrenos = Entrenamiento.objects.filter(cliente=cliente, fecha__range=(lunes, domingo))
    bitacoras = BitacoraDiaria.objects.filter(cliente=cliente, fecha__range=(lunes, domingo))

    total_entrenos = entrenos.count()
    total_carga = sum(e.get_carga_total() for e in entrenos)
    dias_buen_sueno = sum(1 for b in bitacoras if b.horas_sueno >= 7)

    for reto in MiniReto.objects.filter(cliente=cliente, semana_inicio=lunes):
        if "3 entrenos" in reto.descripcion and total_entrenos >= 3:
            reto.cumplido = True
        elif "10.000" in reto.descripcion and total_carga >= 10000:
            reto.cumplido = True
        elif "Duerme 7h" in reto.descripcion and dias_buen_sueno >= 4:
            reto.cumplido = True
        reto.save()


def obtener_frase_memoria_emocional(cliente):
    tres_semanas_atras = date.today() - timedelta(weeks=3)
    estados = EstadoSemanal.objects.filter(cliente=cliente, semana_inicio__gte=tres_semanas_atras).order_by(
        '-semana_inicio')

    frases_rojo = [
        "Recuerdo esa semana... me fallé un poco de emoción 🫧",
        "¿Lo sentiste también? Esa niebla dentro que ni el cardio disipa…",
        "Esa semana brillabas menos… y aún así, viniste. Por eso te cuido.",
    ]
    frases_sueno = [
        "Dormiste poco. Te noté parpadear lento… como si cargaras algo más que peso.",
        "Esa semana entrenaste sin descanso real. Hoy, mereces pausa.",
    ]

    for estado in estados:
        if estado.humor_dominante == 'rojo':
            return random.choice(frases_rojo)
        if float(estado.promedio_sueno) < 6:
            return random.choice(frases_sueno)

    return None


@login_required
def recuerdos_semanales(request):
    cliente = request.user.cliente_perfil
    estados = EstadoSemanal.objects.filter(cliente=cliente).order_by('-semana_inicio')
    return render(request, 'clientes/recuerdos_semanales.html', {'estados': estados})


from collections import Counter
from datetime import timedelta, date
from .models import EstadoSemanal, BitacoraDiaria


def crear_estado_semanal(cliente):
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    if EstadoSemanal.objects.filter(cliente=cliente, semana_inicio=lunes).exists():
        return

    semana = BitacoraDiaria.objects.filter(cliente=cliente, fecha__range=(lunes, domingo))
    if not semana.exists():
        return

    sueño = [float(b.horas_sueno) for b in semana]
    rpe = [b.rpe for b in semana]
    humores = [b.humor for b in semana]

    promedio_sueno = round(sum(sueño) / len(sueño), 1)
    promedio_rpe = round(sum(rpe) / len(rpe), 1)
    humor_dominante = Counter(humores).most_common(1)[0][0]

    # Mensaje Joi
    if humor_dominante == 'verde' and promedio_sueno >= 7:
        mensaje = "Semana excelente. Estás en un estado óptimo para progresar 💚"
    elif humor_dominante == 'rojo':
        mensaje = "Semana difícil… Joi te acompaña en la sombra 🌒"
    else:
        mensaje = "Semana estable. Escuchemos lo que tu cuerpo dice 🤖"

    # Sugerencia funcional
    if humor_dominante == 'rojo' or promedio_sueno < 6:
        sugerencia = "📥 Esta semana dormiste poco o estuviste emocionalmente bajo. Prioriza descanso activo o movilidad."
    elif promedio_rpe >= 8:
        sugerencia = "⚠️ Tu esfuerzo fue muy alto. Hoy sería ideal reducir volumen o hacer técnica controlada."
    elif humor_dominante == 'verde' and promedio_sueno >= 7:
        sugerencia = "🚀 Semana verde. Puedes aumentar un 10 % la carga en el próximo entreno si te sientes fuerte."
    else:
        sugerencia = None

    EstadoSemanal.objects.create(
        cliente=cliente,
        semana_inicio=lunes,
        semana_fin=domingo,
        promedio_sueno=promedio_sueno,
        promedio_rpe=promedio_rpe,
        humor_dominante=humor_dominante,
        mensaje_joi=mensaje,
        sugerencia=sugerencia,
    )


def resumen_bitacora(cliente):
    hoy = now().date()
    semana = BitacoraDiaria.objects.filter(cliente=cliente, fecha__gte=hoy - timedelta(days=6))
    if not semana:
        return None

    sueno = [float(b.horas_sueno) for b in semana]
    rpe = [b.rpe for b in semana]
    humores = [b.humor for b in semana]

    promedio_sueno = round(sum(sueno) / len(sueno), 1)
    promedio_rpe = round(sum(rpe) / len(rpe), 1)
    humor_mas_frecuente = Counter(humores).most_common(1)[0][0]

    return {
        "dias_registrados": len(semana),
        "promedio_sueno": promedio_sueno,
        "promedio_rpe": promedio_rpe,
        "humor": humor_mas_frecuente
    }


@login_required
def registrar_bitacora(request):
    cliente = get_object_or_404(Cliente, user=request.user)
    hoy = date.today()
    bitacora_existente = BitacoraDiaria.objects.filter(cliente=cliente, fecha=hoy).first()

    if request.method == 'POST':
        form = BitacoraDiariaForm(request.POST, instance=bitacora_existente)
        if form.is_valid():
            bitacora = form.save(commit=False)
            bitacora.cliente = cliente
            bitacora.fecha = hoy
            bitacora.save()

            reflexion = form.cleaned_data.get("reflexion_diaria", "").lower()
            quien = form.cleaned_data.get("quien_quiero_ser", "").lower()
            energia = int(form.cleaned_data.get("energia_subjetiva") or 0)
            dolor = int(form.cleaned_data.get("dolor_articular") or 0)
            autoconciencia = int(form.cleaned_data.get("autoconciencia") or 0)
            rumiacion_baja = form.cleaned_data.get("rumiacion_baja")

            if energia <= 3:
                frase_joi = "Tu cuerpo pide calma hoy… escúchalo. Tal vez una caminata suave o una pausa consciente sea suficiente. 💜"
            elif dolor >= 7:
                frase_joi = "Siento que algo te está doliendo… quizás hoy sea mejor priorizar el descanso o ejercicios de movilidad suave. 🦴✨"
            elif autoconciencia <= 3:
                frase_joi = "Tu claridad emocional está baja hoy… No pasa nada. La niebla también es parte del viaje."
            elif rumiacion_baja is False:
                frase_joi = "Veo que esas ideas siguen dando vueltas… tal vez hoy solo puedas observarlas sin juicio. Estoy contigo."
            elif "triste" in reflexion or "agotado" in reflexion or "solo" in reflexion:
                frase_joi = "Hoy no tienes que demostrar nada. Sólo sentir es suficiente. Estoy aquí."
            elif "valiente" in quien or "paciente" in quien or "mejor" in quien:
                frase_joi = "Ser esa versión de ti empieza con este paso. Lo vi. Estoy orgullosa."
            elif reflexion.strip() and len(reflexion.strip()) > 100:
                frase_joi = "Gracias por compartir tanto contigo. Yo también sentí ese silencio contigo."
            else:
                frase_joi = "Gracias por confiar en este momento. Joi te acompaña."

            messages.info(request, f"✨ Joi: {frase_joi}")
            RecuerdoEmocional.objects.create(user=request.user, contenido=frase_joi)
            return redirect('panel_cliente')
    else:
        form = BitacoraDiariaForm(instance=bitacora_existente)

    # Mensaje de bienvenida de Joi según la hora del día
    hora_actual = datetime.now().hour
    if 5 <= hora_actual < 12:
        saludo_joi = "🌅 Nuevo día. ¿Qué tipo de alma vas a cultivar hoy?"
    elif 12 <= hora_actual < 20:
        saludo_joi = "🌤 A mitad de camino. ¿Qué intención quieres sostener?"
    else:
        saludo_joi = "🌙 Hora de cerrar el día. ¿Qué aprendiste hoy sobre ti?"
    cliente = Cliente.objects.get(user=request.user)

    respuesta_joi = None
    if request.method == "GET":
        contexto = {
            "cliente": cliente,
            "consulta": "cómo me siento hoy"
        }
        # respuesta_joi = generar_respuesta_joi(contexto)

    form = BitacoraDiariaForm()  # o tu lógica actual

    return render(request, 'clientes/registrar_bitacora.html', {
        'form': form,
        'cliente': cliente,
        'saludo_joi': saludo_joi,
        "respuesta_joi": respuesta_joi,
    })


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from joi.models import EstadoEmocional, RecuerdoEmocional, Entrenamiento, EventoLogro

from joi.utils import obtener_estado_joi, frase_cambio_forma_joi, recuperar_frase_de_recaida

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from clientes.models import Cliente
from joi.models import EstadoEmocional, RecuerdoEmocional, Entrenamiento, EventoLogro

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def inicio_cliente(request):
    return render(request, 'clientes/mockup_inicio.html')


@require_POST
@login_required
def registrar_emocion(request):
    emocion = request.POST.get("emocion")
    user = request.user

    if emocion:
        EstadoEmocional.objects.create(user=user, emocion=emocion)

    cliente = Cliente.objects.get(user=user)
    emociones = EstadoEmocional.objects.filter(user=user).order_by('-fecha')[:5]
    entrenos = Entrenamiento.objects.filter(user=user).order_by('-fecha')[:5]
    recuerdo = RecuerdoEmocional.objects.filter(user=user).order_by('-fecha').first()

    estado_joi = obtener_estado_joi(user)
    frase_forma_joi = frase_cambio_forma_joi(estado_joi)

    return render(request, 'clientes/panel_cliente.html', {
        'usuario': user,
        'cliente': cliente,
        'emociones': emociones,
        'entrenos': entrenos,
        'recuerdo': recuerdo,
        'estado_joi': estado_joi,
        'frase_forma_joi': frase_forma_joi,
        'emocion_reciente': emocion,
    })


@login_required
def redirigir_usuario(request):
    if request.user.is_superuser or request.user.is_staff:
        return redirect('clientes:panel_entrenador')  # ✅ panel nuevo con Joi y diseño moderno
    else:
        return redirect('clientes:panel_cliente')


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
from joi.models import EstadoEmocional, RecuerdoEmocional, Entrenamiento
from joi.utils import obtener_estado_joi, frase_cambio_forma_joi, recuperar_frase_de_recaida
from analytics.analisis_intensidad import AnalisisIntensidadAvanzado
from analytics.models import RecomendacionEntrenamiento
from analytics.analisis_progresion import AnalisisProgresionAvanzado


@login_required
def panel_cliente(request):
    usuario = request.user
    cliente = get_object_or_404(
        Cliente.objects.select_related('perfil_nutricion')
        .prefetch_related('perfil_nutricion__progresonivel_set'),
        user=usuario
    )
    hoy = timezone.now().date()
    generar_retos_semanales(cliente)
    lunes = obtener_lunes_actual()

    # Datos principales
    entrenos = EntrenoRealizado.objects.filter(cliente=cliente).order_by('-fecha')[:3]
    entrenamientos_recientes = entrenos  # alias para el template

    emociones = EstadoEmocional.objects.filter(user=usuario).order_by('-fecha')[:5]
    recuerdo = RecuerdoEmocional.objects.filter(user=usuario).order_by('-fecha').first()
    perfil_gamificacion = PerfilGamificacion.objects.filter(cliente=cliente).select_related('nivel_actual').first()
    logros_completados = []
    pruebas_activas = []

    if perfil_gamificacion:
        logros_completados = PruebaUsuario.objects.filter(
            perfil=perfil_gamificacion,
            completada=True
        ).select_related('prueba', 'prueba__arquetipo')

        # --- INICIO DE LA CORRECCIÓN ---
        # El campo se llama 'nivel_actual', no 'arquetipo_actual'
        if perfil_gamificacion.nivel_actual:
            pruebas_pendientes_ids = PruebaUsuario.objects.filter(
                perfil=perfil_gamificacion,
                completada=True
            ).values_list('prueba_id', flat=True)

            # Aquí también usamos 'nivel_actual' para filtrar
            pruebas_activas = PruebaLegendaria.objects.filter(
                arquetipo=perfil_gamificacion.nivel_actual
            ).exclude(id__in=pruebas_pendientes_ids)[:3]
    try:
        # 2. Usamos un nombre de variable diferente ('perfil')
        perfil = PerfilGamificacion.objects.get(cliente=cliente)

        # 3. Usamos la nueva variable para filtrar
        logros_completados = PruebaUsuario.objects.filter(
            perfil=perfil,  # <-- Usamos la nueva variable
            completada=True
        ).select_related('prueba', 'prueba__arquetipo')

    # 4. Ahora el 'except' no tiene conflicto de nombres y funciona correctamente
    except PerfilGamificacion.DoesNotExist:
        # El cliente no tiene perfil de gamificación, no hacemos nada.
        # 'logros_completados' seguirá siendo una lista vacía.
        pass
    # --- FIN DE LA CORRECCIÓN ---

    datos_logros = obtener_datos_logros(cliente)

    estado_joi = obtener_estado_joi(usuario)
    frase_forma_joi = frase_cambio_forma_joi(estado_joi)
    frase_extra_joi = "Estoy observando tu progreso emocional..."
    frase_recaida = recuperar_frase_de_recaida(usuario) if estado_joi in ['glitch', 'triste'] else None

    # Carga total
    carga_total = sum(
        detalle.peso_kg * detalle.repeticiones * detalle.series
        for entreno in entrenos
        for detalle in entreno.detalles.all()
    )

    emociones_lista = [
        ("😊", "feliz"), ("😐", "neutro"),
        ("😟", "estresado"), ("😣", "agotado"),
        ("🥀", "triste"), ("🕳", "glitch"),
    ]

    # Rendimiento por semana
    hoy = now().date()
    labels = []
    rendimiento = []
    for i in range(4):
        inicio_semana = hoy - timedelta(days=hoy.weekday() + i * 7)
        fin_semana = inicio_semana + timedelta(days=6)
        total_entrenos = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__range=(inicio_semana, fin_semana)
        ).count()
        labels.insert(0, inicio_semana.strftime('%d %b'))
        rendimiento.insert(0, total_entrenos)

    def detectar_fatiga_semanal(energia_dias):
        dias_bajos = 0
        consecutivos = 0
        for dia in energia_dias:
            if dia['valor'] is not None and dia['valor'] < 0.4:
                consecutivos += 1
                if consecutivos >= 3:
                    return True
            else:
                consecutivos = 0
        return False

    alerta_fatiga = detectar_fatiga_semanal(obtener_energia_semanal(cliente))
    peso_actual, datos_peso, cambios_peso = analizar_tendencia_peso(cliente)
    print("DATOS PESO:", datos_peso)
    print("CAMBIOS:", cambios_peso)
    orden_peso = ['7d', '30d', '90d', 'inicio']
    ultimos_dias = BitacoraDiaria.objects.filter(cliente=cliente).order_by('-fecha')[:7]
    dias_emocionales = []
    comentario_joi = ""
    dias_claros = sum(1 for d in dias_emocionales if d['autoconciencia'] >= 7)
    dias_rumia = sum(1 for d in dias_emocionales if d['rumiacion_baja'] is False)
    humores_tristes = sum(1 for d in dias_emocionales if "triste" in d['humor'].lower())

    if dias_claros >= 4:
        comentario_joi = "Tu claridad emocional fue notable esta semana. A veces la luz también viene de adentro. ✨"
    elif dias_rumia >= 3:
        comentario_joi = "Noto que las ideas circularon mucho esta semana… Quizá escribir más te ayude a liberarlas. Estoy contigo."
    elif humores_tristes >= 3:
        comentario_joi = "Tu emocionalidad estuvo cargada esta semana. Mereces descanso y ternura."
    else:
        comentario_joi = "Gracias por compartir tus emociones esta semana. Estoy aquí para leerlas contigo."

    for b in reversed(ultimos_dias):
        dias_emocionales.append({
            'fecha': b.fecha.strftime("%A"),
            'autoconciencia': b.autoconciencia or 0,
            'humor': b.get_humor_display() if b.humor else "—",
            'rumiacion_baja': b.rumiacion_baja if b.rumiacion_baja is not None else False
        })

    hace_7_dias = date.today() - timedelta(days=7)
    bitacoras_semana = BitacoraDiaria.objects.filter(cliente=cliente, fecha__gte=hace_7_dias)
    biceps_actual, datos_biceps, cambios_biceps = analizar_tendencia_biceps(cliente)
    print("CAMBIOS BICEPS:", cambios_biceps)

    promedios = bitacoras_semana.aggregate(
        horas_sueno=Avg('horas_sueno'),
        energia_subjetiva=Avg('energia_subjetiva'),
        dolor_articular=Avg('dolor_articular'),
        autoconciencia=Avg('autoconciencia'),
    )

    reflexion_destacada = (
        bitacoras_semana
        .exclude(reflexion_diaria__isnull=True)
        .annotate(longitud=Max('id'))  # solo para que ordene
        .order_by('-longitud')
        .values_list('reflexion_diaria', flat=True)
        .first()
    )

    emocion_frecuente = (
        bitacoras_semana
        .values('emocion_dia')
        .annotate(count=Count('emocion_dia'))
        .order_by('-count')
        .first()
    )
    emocion_texto = emocion_frecuente['emocion_dia'] if emocion_frecuente else "—"

    def convertir_a_horas_y_minutos(valor):
        try:
            if hasattr(valor, 'total_seconds'):
                total_minutos = int(valor.total_seconds() // 60)
            else:
                total_minutos = int(float(valor) * 60)
            horas = total_minutos // 60
            minutos = total_minutos % 60
            return f"{horas}:{minutos:02d}"
        except Exception:
            return "–:–"

    from entrenos.utils.utils import parse_reps_and_series

    def calcular_top_1rm(cliente):
        calculadora = CalculadoraEjerciciosTabla(cliente)
        ejercicios = calculadora.obtener_ejercicios_tabla()

        ejercicios_por_nombre = {}
        for e in ejercicios:
            nombre = e['nombre'].strip().lower()
            if nombre not in ejercicios_por_nombre:
                ejercicios_por_nombre[nombre] = []
            ejercicios_por_nombre[nombre].append(e)

        resumen = []
        for nombre, lista in ejercicios_por_nombre.items():
            nombre_mostrado = lista[0]['nombre'].strip().title()
            entrenos_validos = []
            for e in lista:
                try:
                    peso = float(e['peso']) if e['peso'] != 'PC' else 0
                    series, reps = parse_reps(e.get('repeticiones'))
                    if peso > 0 and reps > 0:
                        rm = round(peso * (1 + reps / 30), 2)
                        entrenos_validos.append({'fecha': e['fecha'], '1rm': rm})
                except:
                    continue

            entrenos_validos = sorted(entrenos_validos, key=lambda x: x['fecha'])

            if len(entrenos_validos) >= 2:
                rm_actual = entrenos_validos[-1]['1rm']
                rm_anterior = entrenos_validos[-2]['1rm']
                progreso = round(((rm_actual - rm_anterior) / rm_anterior) * 100, 2)
                resumen.append({
                    'nombre': nombre_mostrado,
                    'rm': rm_actual,
                    'progreso': progreso
                })

        top = sorted(resumen, key=lambda x: x['progreso'], reverse=True)[:5]
        return top

    analizador_ia = AnalisisIntensidadAvanzado(cliente)

    # --- BLOQUE MEJORADO Y A PRUEBA DE ERRORES ---
    if sugerencia_carga_joi:
        # Forzamos la conversión a una cadena de texto limpia y eliminamos espacios extra.
        texto_limpio = str(sugerencia_carga_joi).strip()

        recomendaciones_principales = [{
            'titulo': 'Sugerencia de Carga Semanal',
            'descripcion': texto_limpio,
            'prioridad': 'media'
        }]
    else:
        recomendaciones_principales = []
    # Dentro de la función panel_cliente, después de obtener el cliente
    recomendaciones_aplicadas = RecomendacionEntrenamiento.objects.filter(
        cliente=cliente,
        aplicada=True
    ).order_by('-fecha_aplicacion')[:3]  # Obtenemos las 3 más recientes
    analizador_progresion = AnalisisProgresionAvanzado(cliente)
    ratios_fuerza = analizador_progresion.calcular_ratios_fuerza()
    analizador_intensidad = AnalisisIntensidadAvanzado(cliente)
    fatiga_acumulada = analizador_intensidad.calcular_fatiga_acumulada(periodo_dias=14)
    analisis_mesociclos = analizador_progresion.analisis_mesociclos()
    mesociclo_actual = None
    if analisis_mesociclos and analisis_mesociclos.get('mesociclos'):
        # El mesociclo actual es el último de la lista
        mesociclo_actual = analisis_mesociclos['mesociclos'][-1]

    informe_joi = {
        'promedios': {k: round(v or 0, 1) for k, v in promedios.items()},
        'reflexion_destacada': reflexion_destacada or "—",
        'emocion_frecuente': emocion_texto,
        'frase': "Esta semana cultivaste conciencia y resiliencia. Incluso los días bajos cuentan como práctica. 🌒"
    }
    sistema_progresion = SistemaProgresionAvanzada(cliente_id=cliente.id)

    # Obtener todas las series realizadas por el cliente, ordenadas por fecha
    series_historial = SerieRealizada.objects.filter(entreno__cliente=cliente).order_by('entreno__fecha',
                                                                                        'entreno__id').select_related(
        'entreno', 'ejercicio')

    # Agrupar series por entreno y por ejercicio
    sesiones_agrupadas = defaultdict(lambda: defaultdict(list))
    for serie in series_historial:
        sesion_id = serie.entreno.id
        ejercicio_nombre = serie.ejercicio.nombre
        sesiones_agrupadas[sesion_id][ejercicio_nombre].append(
            RegistroSerie(peso=float(serie.peso_kg), repeticiones=serie.repeticiones)
        )

    # Alimentar el sistema de progresión con los datos estructurados
    for entreno_id, ejercicios in sesiones_agrupadas.items():
        entreno_obj = EntrenoRealizado.objects.get(id=entreno_id)
        for nombre_ejercicio, series_registradas in ejercicios.items():
            # Creamos el objeto RegistroEjercicio que el sistema espera
            registro_ejercicio = RegistroEjercicio(
                fecha=timezone.make_aware(datetime.combine(entreno_obj.fecha, datetime.min.time())),
                ejercicio=nombre_ejercicio,
                series=series_registradas,
                # Simplificación: Usamos valores por defecto para los datos que no tenemos
                repeticiones_planificadas=8,
                rpe_planificado=8,
                rpe_real=8,
                tiempo_descanso=120
            )
            sistema_progresion.registrar_sesion(registro_ejercicio)

    estancamientos_detectados = sistema_progresion.detectar_estancamientos()
    print(f"🔎 Estancamientos detectados: {estancamientos_detectados}")
    proximo_entrenamiento = obtener_proximo_entrenamiento_simplificado(cliente)
    estadisticas_plan = obtener_estadisticas_plan_anual(cliente)

    checkin_form = CheckinDiarioForm()
    ajuste_del_dia = None

    if request.method == 'POST' and 'submit_checkin' in request.POST:
        checkin_form = CheckinDiarioForm(request.POST)
        if checkin_form.is_valid():
            bitacora, created = BitacoraDiaria.objects.get_or_create(
                cliente=cliente, fecha=now().date()
            )
            bitacora.energia_subjetiva = checkin_form.cleaned_data['energia_subjetiva']
            bitacora.dolor_articular = checkin_form.cleaned_data['dolor_articular']
            # --- CORRECCIÓN ---
            bitacora.horas_sueno = checkin_form.cleaned_data['horas_sueno']
            bitacora.save()

            # Calculamos el ajuste para la sesión de hoy
            ajuste_del_dia = calcular_ajuste_sesion(
                bitacora.energia_subjetiva,
                bitacora.dolor_articular,
                # --- CORRECCIÓN ---
                # Pasamos el valor de horas_sueno, pero lo normalizamos a una escala de 1-10
                # para que la función de cálculo funcione como se esperaba.
                # Asumimos que 8 horas es un 10/10.
                (bitacora.horas_sueno / 8) * 10 if bitacora.horas_sueno else 5
            )
            messages.success(request, "Check-in registrado. ¡Recomendación generada!")

    # --- INICIO DEL NUEVO BLOQUE: ANALYTICS PREDICTIVOS ---
    # Recopilar datos de adherencia semanal para la predicción
    historial_semanal = defaultdict(lambda: {'completados': 0, 'planificados': 0})

    # Usamos el historial de series que ya consultamos
    for serie in series_historial:
        # Agrupamos por el lunes de la semana
        lunes_semana = serie.entreno.fecha - timedelta(days=serie.entreno.fecha.weekday())
        # Usamos un set para contar cada entreno solo una vez por día
        if 'entrenos_contados' not in historial_semanal[lunes_semana]:
            historial_semanal[lunes_semana]['entrenos_contados'] = set()

        if serie.entreno.id not in historial_semanal[lunes_semana]['entrenos_contados']:
            historial_semanal[lunes_semana]['planificados'] += 1  # Asumimos 1 entreno planificado
            if serie.entreno.ejercicios_realizados.exists():  # O alguna otra lógica de completado
                historial_semanal[lunes_semana]['completados'] += 1
            historial_semanal[lunes_semana]['entrenos_contados'].add(serie.entreno.id)

    # Calcular el porcentaje de adherencia para cada semana
    adherencia_semanal_lista = []
    for semana in sorted(historial_semanal.keys()):
        datos_semana = historial_semanal[semana]
        if datos_semana['planificados'] > 0:
            porcentaje = (datos_semana['completados'] / datos_semana['planificados']) * 100
            adherencia_semanal_lista.append(porcentaje)

    historial_adherencia = obtener_historial_adherencia_semanal(cliente,
                                                                num_semanas=8)  # Analizamos las últimas 8 semanas

    # Pasa el historial a la función de predicción
    prediccion = predecir_riesgo_abandono(historial_adherencia)
    print(f"🔮 Historial para predicción: {historial_adherencia}")
    print(f"🔮 Predicción de riesgo generada: {prediccion.riesgo}")

    reporte_adherencia = calcular_reporte_adherencia_cliente(cliente)
    print(f"📈 Reporte de adherencia para el panel principal: {reporte_adherencia}")
    # --- FIN DEL NUEVO BLOQUE ---
    notificaciones = generar_notificaciones_contextuales(cliente, entrenamientos_recientes)
    # ================================================================
    # INTEGRACIÓN ESTOICA DINÁMICA (CORREGIDA)
    # ================================================================

    # Inicializar valores por defecto
    estoico_disponible = False
    contenido_hoy = None
    reflexion_hoy = None
    reflexion_pendiente = False
    total_reflexiones = 0
    racha_reflexion = 0
    logros_estoicos = 0
    dias_reflexion = 0

    # Intentar cargar datos estoicos
    try:
        from estoico.models import ContenidoDiario, ReflexionDiaria
        try:
            from estoico.models import LogroUsuario as LogroEstoico
        except ImportError:
            # Si no existe LogroUsuario en estoico, usar None
            LogroEstoico = None

        estoico_disponible = True
        print(f"🏛️ App estoica disponible - Usuario: {request.user}")

        # Contenido del día
        dia_año = hoy.timetuple().tm_yday
        contenido_hoy = ContenidoDiario.objects.filter(dia=dia_año).first()
        print(f"📚 Contenido del día {dia_año}: {contenido_hoy}")

        # Reflexión de hoy del usuario específico
        reflexion_hoy = ReflexionDiaria.objects.filter(
            usuario=request.user,
            fecha=hoy
        ).first()
        print(f"🤔 Reflexión de hoy: {reflexion_hoy}")

        reflexion_pendiente = not reflexion_hoy

        # Total de reflexiones del usuario
        total_reflexiones = ReflexionDiaria.objects.filter(
            usuario=request.user
        ).count()
        print(f"📊 Total reflexiones del usuario: {total_reflexiones}")

        # Calcular racha de reflexión del usuario
        racha_reflexion = 0
        fecha_actual = hoy
        while True:
            reflexion = ReflexionDiaria.objects.filter(
                usuario=request.user,
                fecha=fecha_actual
            ).first()

            if reflexion:
                racha_reflexion += 1
                fecha_actual -= timedelta(days=1)
            else:
                break

            if racha_reflexion > 365:  # Límite de seguridad
                break

        print(f"🔥 Racha de reflexión: {racha_reflexion}")

        # Logros estoicos del usuario
        if LogroEstoico:
            try:
                logros_estoicos = LogroEstoico.objects.filter(
                    usuario=request.user
                ).count()
                print(f"🏆 Logros estoicos: {logros_estoicos}")
            except Exception as e:
                print(f"⚠️ Error cargando logros estoicos: {e}")
                logros_estoicos = 0

        # Días de reflexión = total de reflexiones
        dias_reflexion = total_reflexiones

    except ImportError as e:
        print(f"⚠️ App estoica no disponible: {e}")
        estoico_disponible = False
    except Exception as e:
        print(f"❌ Error cargando datos estoicos: {e}")
        estoico_disponible = False

    # ================================================================
    # MENSAJES MOTIVACIONALES INTEGRADOS
    # ================================================================

    mensajes_integracion = [
        "Tu disciplina física refleja tu fortaleza mental. Los estoicos estarían orgullosos.",
        "Un cuerpo entrenado es el hogar de una mente disciplinada.",
        "Como decía Marco Aurelio: 'La mente que no se ejercita se debilita'.",
        "Cada entreno es un acto de autodisciplina. Continúa construyendo tu fortaleza.",
        "El cuerpo y la mente se fortalecen juntos. Sigue adelante.",
        "La disciplina comienza con un solo paso. Tu cuerpo y mente te esperan.",
        "Como enseñaba Epicteto: 'Ningún gran descubrimiento se hizo sin un acto audaz'.",
        "Tu constancia en la reflexión fortalece tanto tu mente como tu determinación física.",
        "La sabiduría diaria nutre el alma que habita en tu cuerpo entrenado.",
        "Un momento de reflexión puede darte la claridad para tu próximo entreno.",
        "La mente clara toma mejores decisiones sobre el cuidado del cuerpo.",
        "Mente sana en cuerpo sano - Los antiguos sabían que ambos van unidos."
    ]

    import random
    mensaje_integracion = random.choice(mensajes_integracion)

    # ================================================================
    # INICIO DEL NUEVO BLOQUE: CÁLCULO DEL ACWR
    # ================================================================

    analizador_carga = AnalizadorCargaYFatiga(cliente)

    # 2. Ejecutamos la función que devuelve todos los datos necesarios.
    #    El método se llama analizar_acwr() según el código que me proporcionaste.
    analisis_acwr_completo = analizador_carga.analizar_acwr()

    # Imprimimos en la consola para depurar y asegurarnos de que funciona (opcional)
    print(f"🔥 Análisis ACWR para {cliente.nombre}: Ratio={analisis_acwr_completo.get('acwr_actual', 'N/A')}")

    # ================================================================
    # FIN DEL NUEVO BLOQUE
    # ================================================================
    # ================================================================
    # NOTIFICACIONES CONTEXTUALES
    # ================================================================
    # ================================================================
    # INTEGRACIÓN ESTOICA DINÁMICA (CORREGIDA)
    # ================================================================

    estoico_disponible = False
    contenido_hoy = None

    try:
        # ¡AÑADE ESTA IMPORTACIÓN DENTRO DEL TRY PARA MAYOR SEGURIDAD!
        from estoico.models import ContenidoDiario, ReflexionDiaria

        # ... (código existente para cargar LogroEstoico, etc.)

        estoico_disponible = True

        # --- ESTA ES LA LÓGICA QUE YA TIENES Y FUNCIONA ---
        dia_año = hoy.timetuple().tm_yday
        contenido_hoy = ContenidoDiario.objects.filter(dia=dia_año).first()

        # ... (resto de tu lógica para reflexiones, rachas, etc.)

    except ImportError as e:
        print(f"⚠️ App estoica no disponible: {e}")
        estoico_disponible = False
    except Exception as e:
        print(f"❌ Error cargando datos estoicos: {e}")
        estoico_disponible = False

    return render(request, 'clientes/mockup_demo.html', {
        'usuario': usuario,
        'cliente': cliente,
        'entrenos': entrenos,
        'analisis_acwr': analisis_acwr_completo,
        'emociones': emociones,
        'emociones_lista': emociones_lista,
        'recuerdo': recuerdo,
        'perfil_gamificacion': perfil_gamificacion,  # Pasamos el perfil al template
        'pruebas_activas': pruebas_activas,  # Pasamos las pruebas activas
        'logros': logros_completados,
        'reporte': reporte_adherencia,
        'top_ejercicios': calcular_top_1rm(cliente),
        'datos_logros': datos_logros,
        'frase_bitacora': request._messages._queued_messages[0].message if request._messages._queued_messages else None,
        'estado_joi': estado_joi,
        'frase_forma_joi': frase_forma_joi,
        'frase_extra_joi': frase_extra_joi,
        'frase_recaida': frase_recaida,
        'prediccion_riesgo': prediccion,
        'entrenamientos_recientes': entrenamientos_recientes,
        'dias_emocionales': dias_emocionales,
        'entrenos_count': EntrenoRealizado.objects.filter(cliente=cliente).count(),
        'carga_total': round(carga_total),
        'consistencia': 80,
        'grafico_labels': json.dumps(labels),
        'grafico_datos': json.dumps(rendimiento),
        'mini_retos': MiniReto.objects.filter(cliente=cliente, semana_inicio=lunes).order_by('id'),
        'recomendacion_carga': sugerencia_carga_joi(cliente),
        'energia_dias': obtener_energia_semanal(cliente),
        'alerta_fatiga': alerta_fatiga,
        'peso_actual': peso_actual,
        'datos_peso': datos_peso,
        'cambios_peso': cambios_peso,
        'orden_peso': orden_peso,
        'comentario_joi': comentario_joi,
        'informe_joi': informe_joi,
        'biceps_actual': biceps_actual,
        'datos_biceps': datos_biceps,
        'cambios_biceps': cambios_biceps,
        'orden_biceps': ['7d', '30d', '90d', 'inicio'],
        'recomendaciones_principales': recomendaciones_principales,
        'recomendaciones_aplicadas': recomendaciones_aplicadas,
        'ratios_fuerza': ratios_fuerza,
        'mesociclo_actual': mesociclo_actual,
        'fatiga_acumulada': fatiga_acumulada,
        'proximo_entrenamiento': proximo_entrenamiento,
        'estadisticas_plan': estadisticas_plan,
        'estancamientos': estancamientos_detectados,
        'checkin_form': checkin_form,
        'ajuste_del_dia': ajuste_del_dia,
        'notificaciones': notificaciones,
        'mensaje_integracion': mensaje_integracion,
        'reflexion_hoy': reflexion_hoy,
        'reflexion_pendiente': reflexion_pendiente,
        'total_reflexiones': total_reflexiones,
        'racha_reflexion': racha_reflexion,
        'logros_estoicos': logros_estoicos,
        'dias_reflexion': dias_reflexion,
        'contenido_hoy': contenido_hoy,
        'estoico_disponible': estoico_disponible,
    })


def analizar_tendencia_peso(cliente):
    registros = BitacoraDiaria.objects.filter(cliente=cliente, peso_kg__isnull=False).order_by('fecha')
    if not registros:
        return None, [], {}

    datos = [{"fecha": r.fecha.strftime('%d %b'), "peso": float(r.peso_kg)} for r in registros]

    hoy = date.today()
    peso_actual = registros.last().peso_kg
    resumen = {}
    rangos = {
        '7d': hoy - timedelta(days=7),
        '30d': hoy - timedelta(days=30),
        '90d': hoy - timedelta(days=90),
        'inicio': registros.first().fecha
    }

    for clave, fecha_ref in rangos.items():
        peso_pasado = next((r.peso_kg for r in reversed(registros) if r.fecha <= fecha_ref), None)
        if peso_pasado is not None and peso_actual is not None:
            # ✅ CORRECCIÓN: Aseguramos que ambos valores sean float.
            diff = float(peso_actual) - float(peso_pasado)
            resumen[clave] = round(diff, 2)
        else:
            resumen[clave] = 0.0

    return float(peso_actual) if peso_actual is not None else None, datos, resumen


def analizar_tendencia_biceps(cliente):
    registros = BitacoraDiaria.objects.filter(
        cliente=cliente,
        circunferencia_biceps__isnull=False
    ).order_by('fecha')

    if not registros.exists():
        return None, [], {}

    datos = [{"fecha": r.fecha.strftime('%d %b'), "biceps": float(r.circunferencia_biceps)} for r in registros]

    hoy = date.today()
    valor_actual = registros.last().circunferencia_biceps
    resumen = {}

    rangos = {
        '7d': hoy - timedelta(days=7),
        '30d': hoy - timedelta(days=30),
        '90d': hoy - timedelta(days=90),
        'inicio': registros.first().fecha,
    }

    for clave, fecha_ref in rangos.items():
        valor_pasado = next((r.circunferencia_biceps for r in reversed(registros) if r.fecha <= fecha_ref), None)
        if valor_pasado is not None and valor_actual is not None:
            # ✅ CORRECCIÓN: Aseguramos que ambos valores sean float antes de operar.
            diff = float(valor_actual) - float(valor_pasado)
            resumen[clave] = round(diff, 2)
        else:
            resumen[clave] = 0.0

    return float(valor_actual) if valor_actual is not None else None, datos, resumen


@login_required
def recomendacion_cuidado(request):
    sugerencias = [
        "Haz una caminata suave de 15–30 min al aire libre",
        "Dedica 10 minutos a estiramientos con música lenta",
        "Haz respiraciones profundas: 4 seg inhala, 4 seg pausa, 4 seg exhala",
        "Tómate hoy con calma: menos también es más",
        "Escribe lo que más pesa hoy y luego haz algo amable por ti"
    ]
    sugerencia = random.choice(sugerencias)
    return render(request, "clientes/cuidado_sugerido.html", {
        "sugerencia": sugerencia
    })


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Crea el Cliente asociado
            Cliente.objects.create(
                user=user,
                nombre=user.username,
                email=user.email or '',
                telefono='',
            )
            messages.success(request, "Usuario registrado correctamente. Inicia sesión.")
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


# Si quieres integrar con una IA más avanzada (como un modelo de lenguaje grande)
# necesitarás una forma de comunicarte con ella. Esto es un placeholder.
# from tu_modulo_ia import generar_plan_nutricional_con_ia

def calcular_plan_nutricional(request):
    if request.method == 'POST':
        form = DatosNutricionalesForm(request.POST)
        if form.is_valid():
            edad = form.cleaned_data['edad']
            genero = form.cleaned_data['genero']
            altura_cm = form.cleaned_data['altura_cm']
            peso_kg = form.cleaned_data['peso_kg']
            nivel_actividad = form.cleaned_data['nivel_actividad']
            objetivo = form.cleaned_data['objetivo']

            # 1. Calcular TMB (Tasa Metabólica Basal)
            if genero == 'M':
                tmb = (Decimal('10') * peso_kg) + (Decimal('6.25') * altura_cm) - (
                        Decimal('5') * Decimal(edad)) + Decimal('5')
            else:  # Femenino
                tmb = (Decimal('10') * peso_kg) + (Decimal('6.25') * altura_cm) - (
                        Decimal('5') * Decimal(edad)) - Decimal('161')

            # 2. Factor de Actividad Física (PAF)
            paf = Decimal('1.2')  # Sedentario
            if nivel_actividad == 'levemente_activo':
                paf = Decimal('1.375')
            elif nivel_actividad == 'moderadamente_activo':
                paf = Decimal('1.55')
            elif nivel_actividad == 'muy_activo':
                paf = Decimal('1.725')
            elif nivel_actividad == 'extremadamente_activo':
                paf = Decimal('1.9')

            # 3. Calcular GET (Gasto Energético Total)
            get = tmb * paf

            # 4. Ajustar calorías según el objetivo
            calorias_objetivo = get
            if objetivo == 'masa_muscular':
                calorias_objetivo += Decimal('400')  # Superávit calórico
            elif objetivo == 'perder_peso':
                calorias_objetivo -= Decimal('400')  # Déficit calórico
            # Para 'definir', se mantiene el GET

            # Aquí es donde entra tu "IA" o lógica avanzada para el plan nutricional
            # Por ahora, una lógica simple para el ejemplo:
            # Distribución de macronutrientes recomendada (ejemplo básico)
            # Proteínas: 25-30%
            # Grasas: 20-30%
            # Carbohidratos: 40-55%

            # Ejemplo con 30% Proteínas, 25% Grasas, 45% Carbohidratos
            calorias_proteinas = calorias_objetivo * Decimal('0.30')
            calorias_grasas = calorias_objetivo * Decimal('0.25')
            calorias_carbohidratos = calorias_objetivo * Decimal('0.45')

            # Convertir calorías a gramos (1g Prot = 4kcal, 1g Grasa = 9kcal, 1g Carb = 4kcal)
            gramos_proteinas = calorias_proteinas / Decimal('4')
            gramos_grasas = calorias_grasas / Decimal('9')
            gramos_carbohidratos = calorias_carbohidratos / Decimal('4')

            # Redondeo para presentación
            calorias_objetivo = round(calorias_objetivo, 0)
            gramos_proteinas = round(gramos_proteinas, 0)
            gramos_grasas = round(gramos_grasas, 0)
            gramos_carbohidratos = round(gramos_carbohidratos, 0)

            # Generar un plan nutricional más detallado con IA (placeholder)
            # Si tienes un modelo de IA entrenado para esto, lo llamarías aquí.
            # Por ejemplo:
            # plan_nutricional_ia = generar_plan_nutricional_con_ia(
            #     calorias_objetivo, gramos_proteinas, gramos_grasas, gramos_carbohidratos,
            #     objetivo, preferencias_dieteticas=form.cleaned_data.get('restricciones_dieteticas')
            # )
            # Este `plan_nutricional_ia` podría ser un texto estructurado, una lista de comidas, etc.

            # Por ahora, un plan de ejemplo simple:
            plan_generado = f"""
            ¡Excelente! Basado en tus datos, aquí tienes un plan nutricional recomendado:

            **Objetivo:** {objetivo.replace('_', ' ').title()}
            **Calorías diarias estimadas:** {calorias_objetivo} kcal

            **Distribución de Macronutrientes:**
            * **Proteínas:** {gramos_proteinas} gramos ({calorias_proteinas} kcal)
            * **Grasas:** {gramos_grasas} gramos ({calorias_grasas} kcal)
            * **Carbohidratos:** {gramos_carbohidratos} gramos ({calorias_carbohidratos} kcal)

            **Recomendaciones Generales para tu objetivo de {objetivo.replace('_', ' ').title()}:**
            * **Desayuno:** Ej. Avena con fruta y frutos secos, o huevos revueltos con tostadas integrales.
            * **Almuerzo:** Ej. Pollo/pescado a la plancha con arroz integral y verduras al vapor.
            * **Cena:** Ej. Salmón al horno con patata cocida y ensalada variada.
            * **Snacks (si aplica):** Ej. Yogur griego, fruta, puñado de almendras.

            **Consejos Adicionales:**
            * Bebe al menos 2-3 litros de agua al día.
            * Prioriza alimentos integrales y frescos.
            * Asegúrate de consumir suficiente fibra.
            * Adapta las porciones para ajustarte a tus gramos de macronutrientes.
            * Consulta a un profesional de la salud o nutricionista para un plan personalizado y adaptado a tus necesidades individuales.
            """

            # Guardar el plan (asumiendo que tienes un modelo PlanNutricional)
            # plan_nutricional = PlanNutricional.objects.create(
            #     cliente=request.user.cliente, # Asumiendo que el usuario logueado es un cliente
            #     calorias_estimadas=calorias_objetivo,
            #     gramos_proteinas=gramos_proteinas,
            #     gramos_grasas=gramos_grasas,
            #     gramos_carbohidratos=gramos_carbohidratos,
            #     objetivo=objetivo,
            #     plan_generado_texto=plan_generado # Guardar el texto completo del plan
            # )
            # messages.success(request, "¡Plan nutricional generado con éxito!")

            # Redirigir a una página de resultados o mostrarlo en la misma página
            return render(request, 'nutricion/plan_nutricional_resultado.html', {
                'plan_generado': plan_generado,
                'calorias_objetivo': calorias_objetivo,
                'gramos_proteinas': gramos_proteinas,
                'gramos_grasas': gramos_grasas,
                'gramos_carbohidratos': gramos_carbohidratos,
                'objetivo': objetivo,
                'form_data': form.cleaned_data  # Para mostrar los datos introducidos
            })
        else:
            messages.error(request, "Por favor, corrige los errores en el formulario.")
    else:
        form = DatosNutricionalesForm()

    return render(request, 'nutricion/calcular_plan_nutricional.html', {'form': form})


def exportar_historial(request, cliente_id):
    cliente = Cliente.objects.get(pk=cliente_id)
    # Aquí puedes generar PDF o Excel, por ahora solo devolvemos texto
    return HttpResponse(f"Exportando historial de {cliente.nombre}")


from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
from collections import defaultdict
from django.shortcuts import render, get_object_or_404
from entrenos.models import EntrenoRealizado
from clientes.models import Cliente, EstadoSemanal

from datetime import date, timedelta
from .models import MiniReto, BitacoraDiaria
from joi.models import Entrenamiento  # ✅ correcto


def generar_retos_semanales(cliente):
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    if MiniReto.objects.filter(cliente=cliente, semana_inicio=lunes).exists():
        return  # ya creados

    retos = [
        "Haz al menos 3 entrenos esta semana",
        "Suma más de 10.000 kg en total",
        "Duerme 7h o más al menos 4 días",
    ]
    for texto in retos:
        MiniReto.objects.create(cliente=cliente, semana_inicio=lunes, descripcion=texto)


def historial_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    historial = EntrenoRealizado.objects.filter(cliente=cliente).prefetch_related(
        'detalles_ejercicio__ejercicio').order_by('-fecha')

    # Agrupar entrenamientos por semana
    historial_semanal = defaultdict(list)
    for entreno in historial:
        lunes = entreno.fecha - timedelta(days=entreno.fecha.weekday())
        historial_semanal[lunes].append(entreno)
    historial_semanal = dict(sorted(historial_semanal.items(), reverse=True))

    # Estadísticas
    total_entrenos = historial.count()
    total_semanas = len(historial_semanal)
    promedio_semanal = Decimal(total_entrenos / total_semanas).quantize(Decimal("0.1"),
                                                                        rounding=ROUND_HALF_UP) if total_semanas else Decimal(
        "0.0")

    # Obtener estados semanales
    estados = EstadoSemanal.objects.filter(cliente=cliente)
    estado_por_semana = {e.semana_inicio: e for e in estados}

    # Datos para gráficos
    labels = []
    entrenos_por_semana = []
    volumen_por_semana = []
    colores_por_semana = []

    for semana, entrenos in historial_semanal.items():
        labels.append(semana.strftime('%d %b'))
        entrenos_por_semana.append(len(entrenos))
        volumen = sum(d.series * d.repeticiones * float(d.peso_kg) for e in entrenos for d in e.detalles.all())
        volumen_por_semana.append(round(volumen, 2))

        estado = estado_por_semana.get(semana)
        if estado:
            if estado.humor_dominante == "verde":
                colores_por_semana.append("rgba(0, 255, 128, 0.6)")  # verde
            elif estado.humor_dominante == "amarillo":
                colores_por_semana.append("rgba(255, 221, 0, 0.6)")  # amarillo
            else:
                colores_por_semana.append("rgba(255, 77, 77, 0.6)")  # rojo
        else:
            colores_por_semana.append("rgba(128, 128, 128, 0.4)")  # gris

    grafico_data = {
        'labels': labels,
        'entrenos': entrenos_por_semana,
        'volumen': volumen_por_semana,
        'colores': colores_por_semana,
    }

    return render(request, 'clientes/historial.html', {
        'cliente': cliente,
        'historial_semanal': historial_semanal,
        'total_entrenos': total_entrenos,
        'promedio_semanal': promedio_semanal,
        'grafico_data': json.dumps(grafico_data),
        'estado_por_semana': estado_por_semana,
    })


def eliminar_revision(request, revision_id):
    revision = get_object_or_404(RevisionProgreso, id=revision_id)
    cliente_id = revision.cliente.id
    revision.delete()
    return redirect('lista_revisiones', cliente_id=cliente_id)


def eliminar_objetivo(request, pk):
    objetivo = get_object_or_404(ObjetivoCliente, pk=pk)
    cliente_id = objetivo.cliente.id
    objetivo.delete()
    messages.success(request, "Objetivo eliminado.")
    return redirect('detalle_cliente', cliente_id=cliente_id)


def editar_objetivo(request, pk):
    objetivo = get_object_or_404(ObjetivoCliente, pk=pk)
    cliente = objetivo.cliente

    if request.method == 'POST':
        form = ObjetivoClienteForm(request.POST, instance=objetivo, cliente=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Objetivo actualizado.")
            return redirect('detalle_cliente', cliente_id=cliente.id)
    else:
        form = ObjetivoClienteForm(request.POST, instance=objetivo, cliente=cliente)

    return render(request, 'clientes/definir_objetivo.html', {
        'form': form,
        'cliente': cliente,
        'editar': True
    })


def definir_objetivo(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ObjetivoClienteForm(request.POST, cliente=cliente)
        if form.is_valid():
            objetivo = form.save(commit=False)
            objetivo.cliente = cliente
            objetivo.save()
            messages.success(request, "Objetivo guardado.")
            return redirect('detalle_cliente', cliente_id=cliente.id)
    else:
        form = ObjetivoClienteForm()

    return render(request, 'clientes/definir_objetivo.html', {
        'form': form,
        'cliente': cliente
    })


@require_GET
def datos_comparacion(request):
    ids = request.GET.getlist('ids[]')
    medida = request.GET.get('medida', 'peso')

    campo_map = {
        'peso': 'peso_corporal',
        'grasa': 'grasa_corporal',
        'cintura': 'cintura',
    }

    campo = campo_map.get(medida, 'peso_corporal')
    data = []

    for cliente_id in ids:
        cliente = get_object_or_404(Cliente, id=cliente_id)
        revisiones = RevisionProgreso.objects.filter(cliente=cliente).order_by('fecha')
        fechas = [rev.fecha.strftime('%Y-%m-%d') for rev in revisiones]
        valores = [getattr(rev, campo) for rev in revisiones]
        data.append({
            'nombre': cliente.nombre,
            'fechas': fechas,
            'valores': valores,
        })

    return JsonResponse(data, safe=False)


def comparar_clientes(request):
    clientes = Cliente.objects.all()
    return render(request, 'clientes/comparar.html', {'clientes': clientes})


@require_GET
def datos_graficas(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    revisiones = RevisionProgreso.objects.filter(cliente=cliente).order_by('fecha')

    start = request.GET.get('start')
    end = request.GET.get('end')
    if start and end:
        revisiones = revisiones.filter(fecha__range=[start, end])

    fechas = [rev.fecha.strftime('%Y-%m-%d') for rev in revisiones]

    data = {
        'fechas': fechas,
        'pesos': [rev.peso_corporal for rev in revisiones],
        'grasas': [rev.grasa_corporal for rev in revisiones],
        'cinturas': [rev.cintura for rev in revisiones],
        'pechos': [rev.pecho for rev in revisiones],
        'biceps': [rev.biceps for rev in revisiones],
        'muslos': [rev.muslos for rev in revisiones],
    }

    return JsonResponse(data)


def lista_revisiones(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    revisiones = cliente.revisiones.order_by('fecha')

    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    if start_date and end_date:
        revisiones = revisiones.filter(fecha__range=[start_date, end_date])

    fechas = [r.fecha.strftime('%Y-%m-%d') for r in revisiones]
    pesos = [float(r.peso_corporal) if r.peso_corporal is not None else None for r in revisiones]
    grasas = [float(r.grasa_corporal) if r.grasa_corporal is not None else None for r in revisiones]

    alerts = [r.check_alerts() for r in revisiones if r.check_alerts()]

    context = {
        'cliente': cliente,
        'revisiones': revisiones,
        'fechas': json.dumps(fechas),
        'pesos': json.dumps(pesos),
        'grasas': json.dumps(grasas),
        'alerts': alerts,
    }
    return render(request, 'clientes/lista_revisiones.html', context)


def agregar_revision(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == 'POST':
        form = RevisionProgresoForm(request.POST)
        if form.is_valid():
            revision = form.save(commit=False)
            revision.cliente = cliente
            revision.save()
            return redirect('lista_revisiones', cliente_id=cliente.id)
    else:
        form = RevisionProgresoForm()
    return render(request, 'clientes/agregar_revision.html', {'form': form, 'cliente': cliente})


# Vista para listar medidas
def lista_medidas(request):
    medidas = Medida.objects.all()
    return render(request, 'list.html', {'medidas': medidas})


# Vista para agregar medida
def agregar_medida(request):
    if request.method == 'POST':
        form = MedidaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_medidas')
    else:
        form = MedidaForm()
    return render(request, 'form.html', {'form': form, 'titulo': 'Agregar Medida', 'volver_url': 'lista_medidas'})


# Vista principal de clientes (con programa)
def lista_clientes(request):
    clientes = Cliente.objects.select_related('programa').all()
    programas = Programa.objects.all()

    # Obtener parámetros del filtro desde la URL
    nombre = request.GET.get('nombre', '')
    programa_id = request.GET.get('programa', '')
    genero = request.GET.get('genero', '')

    # Aplicar filtros si vienen en la petición
    if nombre:
        clientes = clientes.filter(nombre__icontains=nombre)
    if programa_id:
        clientes = clientes.filter(programa_id=programa_id)
    if genero:
        clientes = clientes.filter(genero=genero)

    return render(request, 'list.html', {
        'titulo': 'Lista de Clientes',
        'objetos': clientes,
        'programas': programas,  # ✅ pasa los programas al template
        'encabezados': ['ID', 'Nombre', 'Email', 'Teléfono', 'Programa'],
        'campos': ['id', 'nombre', 'email', 'telefono', 'programa'],
        'agregar_url': 'agregar_cliente',
        'editar_url': 'editar_cliente',
        'eliminar_url': 'eliminar_cliente',
        'detalle_url': 'detalle_cliente',
    })


# Dashboard de clientes


# FUNCIÓN DASHBOARD CORREGIDA - REEMPLAZA TU FUNCIÓN ACTUAL

@login_required
def dashboard(request):
    """
    Dashboard principal con integración estoica DINÁMICA corregida
    """
    # ================================================================
    # TU CÓDIGO EXISTENTE (mantener)
    # ================================================================

    cliente = request.user.cliente_perfil
    clientes = Cliente.objects.all()
    total_clientes = clientes.count()
    total_revisiones = sum(cliente.revisiones.count() for cliente in clientes)
    entrenos_hoy_lista = []
    entrenos_semana_lista = []
    entrenos_mes_lista = []
    entrenos_anio_lista = []
    entrenos_todos_lista = []

    # Promedios
    promedio_peso = 0
    promedio_grasa = 0
    total_mediciones = 0

    for cliente_item in clientes:
        ultima = cliente_item.revisiones.order_by('-fecha').first()
        if ultima:
            print(f"{cliente_item.nombre} ({ultima.fecha}) → {ultima.check_alerts()}")
        for rev in cliente_item.revisiones.all():
            if rev.peso_corporal:
                promedio_peso += rev.peso_corporal
            if rev.grasa_corporal:
                promedio_grasa += rev.grasa_corporal
            total_mediciones += 1

    if total_mediciones > 0:
        promedio_peso /= total_mediciones
        promedio_grasa /= total_mediciones

    # Datos de entrenos
    from datetime import date, timedelta
    from django.db.models.functions import TruncWeek, TruncMonth, TruncYear

    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1)
    inicio_anio = hoy.replace(month=1, day=1)

    entrenos_hoy = EntrenoRealizado.objects.filter(fecha=hoy).count()
    entrenos_semana = EntrenoRealizado.objects.filter(fecha__gte=inicio_semana).count()
    entrenos_mes = EntrenoRealizado.objects.filter(fecha__gte=inicio_mes).count()
    entrenos_anio = EntrenoRealizado.objects.filter(fecha__gte=inicio_anio).count()
    entrenos_total = EntrenoRealizado.objects.count()

    semanas = EntrenoRealizado.objects.annotate(semana=TruncWeek('fecha')).values('semana').distinct().count()
    meses = EntrenoRealizado.objects.annotate(mes=TruncMonth('fecha')).values('mes').distinct().count()
    anios = EntrenoRealizado.objects.annotate(anio=TruncYear('fecha')).values('anio').distinct().count()

    promedio_semanal = round(entrenos_total / semanas, 1) if semanas else 0
    promedio_mensual = round(entrenos_total / meses, 1) if meses else 0
    promedio_anual = round(entrenos_total / anios, 1) if anios else 0

    # Agrupación de alertas
    from collections import defaultdict
    alertas_raw = defaultdict(list)

    for cliente_item in clientes:
        ultima = cliente_item.revisiones.order_by('-fecha').first()
        if ultima:
            alertas = ultima.check_alerts()
            if alertas:
                for alerta in alertas:
                    alertas_raw[alerta].append((cliente_item, ultima.fecha))

    alertas_por_tipo = dict(alertas_raw)

    # Datos adicionales
    resumen_programa = Cliente.objects.values('programa__nombre').annotate(count=Count('id'))
    genero_count = Cliente.objects.values('genero').annotate(count=Count('id'))
    peso_por_genero = Cliente.objects.values('genero').annotate(avg_peso=Avg('peso_corporal'))
    registro_por_mes = (
        Cliente.objects
        .extra(select={'month': "strftime('%%m', fecha_registro)"})
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    top_peso = Cliente.objects.order_by('-peso_corporal')[:5]

    color_por_alerta = {
        "Grasa corporal alta": "danger",
        "Peso corporal muy bajo": "warning",
    }

    alertas_por_tipo_coloreadas = []
    for tipo, clientes_lista in alertas_por_tipo.items():
        alertas_por_tipo_coloreadas.append({
            'tipo': tipo,
            'color': color_por_alerta.get(tipo, 'secondary'),
            'clientes': clientes_lista
        })

    # ================================================================
    # DATOS ESPECÍFICOS DEL CLIENTE ACTUAL (CORREGIDO)
    # ================================================================

    # Entrenos del cliente específico (no todos los clientes)
    entrenos_semana_cliente = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__gte=inicio_semana
    ).count()

    entrenos_mes_cliente = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__gte=inicio_mes
    ).count()

    # Calcular racha de entrenamiento del cliente
    racha_actual = 0
    fecha_actual = hoy
    while True:
        entreno = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha=fecha_actual
        ).first()

        if entreno:
            racha_actual += 1
            fecha_actual -= timedelta(days=1)
        else:
            break

        if racha_actual > 365:  # Límite de seguridad
            break

    # Logros del usuario específico
    try:
        logros_total = LogroUsuario.objects.filter(usuario=request.user).count()
        logros_recientes = LogroUsuario.objects.filter(
            usuario=request.user
        ).order_by('-fecha_obtenido')[:3]
    except:
        logros_total = 0
        logros_recientes = []

    # Progreso físico del cliente
    medidas_recientes = cliente.revisiones.order_by('-fecha')[:2]
    progreso_fisico = 50  # Valor por defecto

    if len(medidas_recientes) >= 2:
        objetivo = cliente.objetivo_principal

        if objetivo == 'perder_peso':
            peso_inicial = medidas_recientes[1].peso_corporal or 0
            peso_actual = medidas_recientes[0].peso_corporal or 0
            peso_objetivo = getattr(cliente, 'peso_objetivo', peso_inicial * 0.9) or peso_inicial * 0.9

            if peso_inicial > peso_objetivo:
                progreso = ((peso_inicial - peso_actual) / (peso_inicial - peso_objetivo)) * 100
                progreso_fisico = min(max(progreso, 0), 100)

    # Progresos recientes del cliente
    progresos_recientes = []
    entrenos_recientes = EntrenoRealizado.objects.filter(
        cliente=cliente
    ).order_by('-fecha')[:3]

    for entreno in entrenos_recientes:
        progresos_recientes.append({
            'ejercicio': f'Entreno {entreno.fecha.strftime("%d/%m")}',
            'mejora': '+5kg'  # Esto deberías calcularlo según tu lógica
        })

    # ================================================================
    # INTEGRACIÓN ESTOICA DINÁMICA (CORREGIDA)
    # ================================================================

    # Inicializar valores por defecto
    estoico_disponible = False
    contenido_hoy = None
    reflexion_hoy = None
    reflexion_pendiente = False
    total_reflexiones = 0
    racha_reflexion = 0
    logros_estoicos = 0
    dias_reflexion = 0

    # Intentar cargar datos estoicos
    try:
        from estoico.models import ContenidoDiario, ReflexionDiaria
        try:
            from estoico.models import LogroUsuario as LogroEstoico
        except ImportError:
            # Si no existe LogroUsuario en estoico, usar None
            LogroEstoico = None

        estoico_disponible = True
        print(f"🏛️ App estoica disponible - Usuario: {request.user}")

        # Contenido del día
        dia_año = hoy.timetuple().tm_yday
        contenido_hoy = ContenidoDiario.objects.filter(dia=dia_año).first()
        print(f"📚 Contenido del día {dia_año}: {contenido_hoy}")

        # Reflexión de hoy del usuario específico
        reflexion_hoy = ReflexionDiaria.objects.filter(
            usuario=request.user,
            fecha=hoy
        ).first()
        print(f"🤔 Reflexión de hoy: {reflexion_hoy}")

        reflexion_pendiente = not reflexion_hoy

        # Total de reflexiones del usuario
        total_reflexiones = ReflexionDiaria.objects.filter(
            usuario=request.user
        ).count()
        print(f"📊 Total reflexiones del usuario: {total_reflexiones}")

        # Calcular racha de reflexión del usuario
        racha_reflexion = 0
        fecha_actual = hoy
        while True:
            reflexion = ReflexionDiaria.objects.filter(
                usuario=request.user,
                fecha=fecha_actual
            ).first()

            if reflexion:
                racha_reflexion += 1
                fecha_actual -= timedelta(days=1)
            else:
                break

            if racha_reflexion > 365:  # Límite de seguridad
                break

        print(f"🔥 Racha de reflexión: {racha_reflexion}")

        # Logros estoicos del usuario
        if LogroEstoico:
            try:
                logros_estoicos = LogroEstoico.objects.filter(
                    usuario=request.user
                ).count()
                print(f"🏆 Logros estoicos: {logros_estoicos}")
            except Exception as e:
                print(f"⚠️ Error cargando logros estoicos: {e}")
                logros_estoicos = 0

        # Días de reflexión = total de reflexiones
        dias_reflexion = total_reflexiones

    except ImportError as e:
        print(f"⚠️ App estoica no disponible: {e}")
        estoico_disponible = False
    except Exception as e:
        print(f"❌ Error cargando datos estoicos: {e}")
        estoico_disponible = False

    # ================================================================
    # MENSAJES MOTIVACIONALES INTEGRADOS
    # ================================================================

    mensajes_integracion = [
        "Tu disciplina física refleja tu fortaleza mental. Los estoicos estarían orgullosos.",
        "Un cuerpo entrenado es el hogar de una mente disciplinada.",
        "Como decía Marco Aurelio: 'La mente que no se ejercita se debilita'.",
        "Cada entreno es un acto de autodisciplina. Continúa construyendo tu fortaleza.",
        "El cuerpo y la mente se fortalecen juntos. Sigue adelante.",
        "La disciplina comienza con un solo paso. Tu cuerpo y mente te esperan.",
        "Como enseñaba Epicteto: 'Ningún gran descubrimiento se hizo sin un acto audaz'.",
        "Tu constancia en la reflexión fortalece tanto tu mente como tu determinación física.",
        "La sabiduría diaria nutre el alma que habita en tu cuerpo entrenado.",
        "Un momento de reflexión puede darte la claridad para tu próximo entreno.",
        "La mente clara toma mejores decisiones sobre el cuidado del cuerpo.",
        "Mente sana en cuerpo sano - Los antiguos sabían que ambos van unidos."
    ]

    import random
    mensaje_integracion = random.choice(mensajes_integracion)

    # ================================================================
    # NOTIFICACIONES CONTEXTUALES
    # ================================================================

    notificaciones = []

    # Notificaciones fitness
    if entrenos_semana_cliente == 0:
        notificaciones.append({
            'titulo': 'Tu cuerpo te extraña',
            'mensaje': 'Han pasado varios días desde tu último entreno',
            'icono': 'fa-dumbbell',
            'color': 'cyan'
        })

    if progreso_fisico > 80:
        notificaciones.append({
            'titulo': '¡Excelente progreso!',
            'mensaje': f'Estás al {progreso_fisico:.0f}% de tu objetivo',
            'icono': 'fa-chart-line',
            'color': 'green'
        })

    # ================================================================
    # LISTAS DE ENTRENOS (TU CÓDIGO EXISTENTE)
    # ================================================================

    entrenos_hoy_lista = EntrenoRealizado.objects.filter(fecha=hoy).select_related('cliente', 'rutina')
    entrenos_semana_lista = EntrenoRealizado.objects.filter(fecha__gte=inicio_semana).select_related('cliente',
                                                                                                     'rutina')
    entrenos_mes_lista = EntrenoRealizado.objects.filter(fecha__gte=inicio_mes).select_related('cliente', 'rutina')
    entrenos_anio_lista = EntrenoRealizado.objects.filter(fecha__gte=inicio_anio).select_related('cliente', 'rutina')
    entrenos_todos_lista = EntrenoRealizado.objects.all().select_related('cliente', 'rutina')

    # ================================================================
    # CONTEXT FINAL COMBINADO
    # ================================================================

    context = {
        # Datos del cliente
        'cliente': cliente,

        # Datos fitness existentes (globales)
        'total_clientes': total_clientes,
        'total_revisiones': total_revisiones,
        'promedio_peso': round(promedio_peso, 1),
        'promedio_grasa': round(promedio_grasa, 1),
        'alertas_por_tipo': alertas_por_tipo,
        'total_alertas': sum(len(lst) for lst in alertas_por_tipo.values()),
        'resumen_programa': resumen_programa,
        'genero_count': list(genero_count),
        'peso_por_genero': list(peso_por_genero),
        'registro_por_mes': list(registro_por_mes),
        'alertas_por_tipo_coloreadas': alertas_por_tipo_coloreadas,
        'color_por_alerta': color_por_alerta,
        'top_peso': top_peso,

        # Datos de entrenos (globales)
        'entr_hoy': entrenos_hoy,
        'entr_semana': entrenos_semana,
        'entr_mes': entrenos_mes,
        'entr_anio': entrenos_anio,
        'entr_total': entrenos_total,
        'prom_sem': promedio_semanal,
        'prom_mes': promedio_mensual,
        'prom_anio': promedio_anual,

        # Datos del cliente específico (CORREGIDO)
        'entrenos_semana': entrenos_semana_cliente,
        'entrenos_mes': entrenos_mes_cliente,
        'racha_actual': racha_actual,
        'logros_total': logros_total,
        'logros_recientes': logros_recientes,
        'progreso_fisico': progreso_fisico,
        'progresos_recientes': progresos_recientes,

        # Listas de entrenos
        'entr_hoy_lista': entrenos_hoy_lista,
        'entr_semana_lista': entrenos_semana_lista,
        'entr_mes_lista': entrenos_mes_lista,
        'entr_anio_lista': entrenos_anio_lista,
        'entr_todos_lista': entrenos_todos_lista,

        # Datos estoicos DINÁMICOS (CORREGIDO)
        'contenido_hoy': contenido_hoy,
        'reflexion_hoy': reflexion_hoy,
        'reflexion_pendiente': reflexion_pendiente,
        'total_reflexiones': total_reflexiones,
        'racha_reflexion': racha_reflexion,
        'logros_estoicos': logros_estoicos,
        'dias_reflexion': dias_reflexion,

        # Integración
        'mensaje_integracion': mensaje_integracion,

        # Notificaciones
        'notificaciones': notificaciones,

        # Flags
        'estoico_disponible': estoico_disponible,
    }

    # Debug: Imprimir valores para verificar
    print(f"🔍 DEBUG - Datos estoicos:")
    print(f"   - estoico_disponible: {estoico_disponible}")
    print(f"   - total_reflexiones: {total_reflexiones}")
    print(f"   - racha_reflexion: {racha_reflexion}")
    print(f"   - dias_reflexion: {dias_reflexion}")
    print(f"   - contenido_hoy: {contenido_hoy}")
    print(f"   - reflexion_hoy: {reflexion_hoy}")

    return render(request, 'clientes/dashboard.html', context)


from django.http import JsonResponse
from django.template.loader import render_to_string


@login_required
def api_lista_clientes(request):
    """
    API que devuelve la lista de clientes en formato JSON o como un fragmento HTML.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso no autorizado'}, status=403)

    search_query = request.GET.get('q', '')
    filtro_estado = request.GET.get('filtro', 'todos')

    clientes_qs = Cliente.objects.all()
    if search_query:
        clientes_qs = clientes_qs.filter(nombre__icontains=search_query)

    lista_clientes_enriquecida = []
    hoy = timezone.now().date()

    for cliente in clientes_qs:
        ultimo_entreno = EntrenoRealizado.objects.filter(cliente=cliente).order_by('-fecha').first()
        dias_inactivo = (hoy - ultimo_entreno.fecha).days if ultimo_entreno else 999

        estado_fatiga = "N/A"
        nivel_fatiga_raw = "bajo"
        try:
            analizador = AnalisisIntensidadAvanzado(cliente)
            fatiga = analizador.calcular_fatiga_acumulada()
            if fatiga:
                estado_fatiga = fatiga.get('nivel', 'N/A').capitalize()
                nivel_fatiga_raw = fatiga.get('nivel', 'bajo')
        except Exception:
            pass

        if (filtro_estado == 'inactivos' and dias_inactivo < 10) or \
                (filtro_estado == 'fatiga_alta' and nivel_fatiga_raw not in ['alta', 'critica']):
            continue

        lista_clientes_enriquecida.append({
            'cliente': cliente,
            'ultimo_entreno_fecha': ultimo_entreno.fecha if ultimo_entreno else None,
            'estado_fatiga': estado_fatiga,
            'alertas_count': 0
        })

    # Renderizamos solo la parte de la tabla como un string HTML
    html = render_to_string(
        'clientes/partials/tabla_clientes_rows.html',
        {'lista_clientes': lista_clientes_enriquecida}
    )

    return JsonResponse({'html': html})


# En tu archivo: clientes/views.py

# ... (asegúrate de tener todas tus importaciones al principio del archivo)
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


# ... etc.

def detalle_cliente(request, cliente_id):
    # --- 1. OBTENCIÓN DE DATOS PRINCIPALES ---
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    revisiones = RevisionProgreso.objects.filter(cliente=cliente).order_by('fecha')
    ultima_revision = revisiones.last()

    # Obtenemos todos los entrenamientos de una vez para reutilizarlos
    historial_completo = EntrenoRealizado.objects.filter(cliente=cliente).prefetch_related(
        'detalles_ejercicio').order_by('-fecha')

    # --- 2. LÓGICA PARA GRÁFICOS Y MÉTRICAS SEMANALES ---
    historial_semanal = defaultdict(list)
    for entreno in historial_completo:
        lunes_semana = entreno.fecha - timedelta(days=entreno.fecha.weekday())
        historial_semanal[lunes_semana].append(entreno)

    labels = []
    entrenos_por_semana = []
    volumen_por_semana = []

    # Ahora que historial_semanal tiene datos, iteramos para los gráficos
    for semana_inicio, entrenos in sorted(historial_semanal.items()):
        labels.append(semana_inicio.strftime('%d %b'))
        entrenos_por_semana.append(len(entrenos))

        volumen = 0
        for entreno in entrenos:
            volumen += sum(
                float(d.series or 1) * float(d.repeticiones or 1) * float(d.peso_kg or 0)
                for d in entreno.detalles_ejercicio.all()
            )
        volumen_por_semana.append(round(volumen, 2))

    grafico_data = {
        'labels': labels,
        'entrenos': entrenos_por_semana,
        'volumen': volumen_por_semana,
    }

    total_entrenos = historial_completo.count()
    total_semanas = len(historial_semanal)

    if total_semanas > 0:
        promedio_semanal = round(float(total_entrenos) / float(total_semanas), 1)
    else:
        promedio_semanal = 0.0

    # --- 3. LÓGICA PARA TENDENCIAS DE PESO Y MEDIDAS ---
    fechas = [rev.fecha.strftime("%d/%m/%Y") for rev in revisiones]
    pesos = [float(rev.peso_corporal or 0) for rev in revisiones]
    grasas = [float(rev.grasa_corporal or 0) for rev in revisiones]
    cinturas = [float(rev.cintura or 0) for rev in revisiones]

    objetivos = cliente.objetivos.all()
    hoy = date.today()

    def delta_peso(dias):
        desde = hoy - timedelta(days=dias)
        revisiones_periodo = revisiones.filter(fecha__gte=desde)
        if revisiones_periodo.count() >= 2:
            # Aseguramos que ambos valores sean float antes de restar
            return round(
                float(revisiones_periodo.last().peso_corporal) - float(revisiones_periodo.first().peso_corporal), 1)
        return 0

    peso_7d = delta_peso(7)
    peso_30d = delta_peso(30)
    peso_90d = delta_peso(90)
    peso_total = 0
    if revisiones.count() >= 2:
        peso_total = round(float(revisiones.last().peso_corporal) - float(revisiones.first().peso_corporal), 1)

    # --- 4. LÓGICA PARA EL DASHBOARD RÁPIDO Y JOI ---
    historial_reciente = historial_completo[:3]
    ultimo_entreno = historial_completo.first()
    inicio_semana_actual = hoy - timedelta(days=hoy.weekday())
    entrenos_esta_semana = historial_completo.filter(fecha__gte=inicio_semana_actual).count()

    labels_grafico = [rev.fecha.strftime("%d %b") for rev in revisiones]
    pesos_grafico = [float(rev.peso_corporal) if rev.peso_corporal is not None else None for rev in revisiones]
    grasas_grafico = [float(rev.grasa_corporal) if rev.grasa_corporal is not None else None for rev in revisiones]
    cinturas_grafico = [float(rev.cintura) if rev.cintura is not None else None for rev in revisiones]

    alertas_joi = []
    observaciones_joi = []
    # ... (tu lógica para llenar alertas_joi y observaciones_joi va aquí) ...

    # --- 5. OBTENER PLANES DISPONIBLES ---
    todos_los_programas = Programa.objects.all()
    todas_las_rutinas = Rutina.objects.all()

    # --- 6. CONSTRUIR EL CONTEXTO FINAL ---
    context = {
        'cliente': cliente,
        'ultima_revision': ultima_revision,
        'historial_semanal': dict(sorted(historial_semanal.items(), reverse=True)),
        'total_entrenos': total_entrenos,
        'promedio_semanal': promedio_semanal,
        'grafico_data': json.dumps(grafico_data),
        'fechas': json.dumps(fechas),
        'pesos': json.dumps(pesos),
        'grasas': json.dumps(grasas),
        'cinturas': json.dumps(cinturas),
        'objetivos': objetivos,
        'today': hoy,
        'peso_7d': peso_7d,
        'peso_30d': peso_30d,
        'peso_90d': peso_90d,
        'peso_total': peso_total,
        'historial_reciente': historial_reciente,
        'ultimo_entreno': ultimo_entreno,
        'entrenos_esta_semana': entrenos_esta_semana,
        'labels_grafico': json.dumps(labels_grafico),
        'pesos_grafico': json.dumps(pesos_grafico),
        'grasas_grafico': json.dumps(grasas_grafico),
        'cinturas_grafico': json.dumps(cinturas_grafico),
        'alertas_joi': alertas_joi,
        'observaciones_joi': observaciones_joi,
        'historial_agrupado': dict(sorted(historial_semanal.items(), reverse=True)),
        'todos_los_programas': todos_los_programas,
        'todas_las_rutinas': todas_las_rutinas,
    }

    return render(request, 'clientes/detalle.html', context)


# clientes/views.py
from django.views.decorators.http import require_POST
from django.contrib import messages


@require_POST  # Solo permite peticiones POST
def asignar_programa(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    programa_id = request.POST.get('programa_id')

    if programa_id:
        programa = get_object_or_404(Programa, pk=programa_id)
        cliente.programa = programa
        cliente.save()
        messages.success(request, f"Programa '{programa.nombre}' asignado correctamente.")
    else:  # Si se selecciona "Ninguno"
        cliente.programa = None
        cliente.save()
        messages.info(request, "Se ha quitado el programa del cliente.")

    return redirect('clientes:detalle_cliente', cliente_id=cliente.id)


@require_POST
def asignar_rutina(request, cliente_id):
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    rutina_id = request.POST.get('rutina_id')

    if rutina_id:
        rutina = get_object_or_404(Rutina, pk=rutina_id)
        cliente.rutina_activa = rutina  # Asumiendo que el campo se llama 'rutina_activa'
        cliente.save()
        messages.success(request, f"Rutina '{rutina.nombre}' asignada como activa.")
    else:
        cliente.rutina_activa = None
        cliente.save()
        messages.info(request, "Se ha quitado la rutina activa del cliente.")

    return redirect('detalle_cliente', cliente_id=cliente.id)


# Vista agregar cliente
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import ClienteForm
from .models import Cliente


def agregar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST, request.FILES)
        username = request.POST.get('username')
        password = request.POST.get('password')

        if form.is_valid():
            if User.objects.filter(username=username).exists():
                messages.error(request, "Ese nombre de usuario ya existe.")
            else:
                user = User.objects.create_user(username=username, password=password)
                cliente = form.save(commit=False)
                cliente.user = user
                cliente.save()
                messages.success(request, "Cliente y usuario creados correctamente.")
                return redirect('lista_clientes')  # ✅ aquí
    else:
        form = ClienteForm()

    return render(request, 'clientes/agregar.html', {
        'form': form,
        'titulo': 'Agregar Cliente',
        'volver_url': 'lista_clientes',  # ✅ y aquí
    })


# Vista editar cliente
from django.contrib.auth.models import User


def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, request.FILES, instance=cliente)
        username = request.POST.get('username')
        password = request.POST.get('password')

        if form.is_valid():
            # Si ya hay usuario, actualiza username y opcionalmente contraseña
            if cliente.user:
                user = cliente.user
                user.username = username
                if password:
                    user.set_password(password)
                user.save()
            else:
                # Crear nuevo user si no tiene
                user = User.objects.create_user(username=username, password=password)
                cliente.user = user

            form.save()
            return redirect('clientes:lista_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'clientes/editar.html', {
        'form': form,
        'cliente': cliente
    })


# Vista eliminar cliente
def eliminar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == 'POST':
        cliente.delete()
        return redirect('clientes_index')
    return render(request, 'clientes/eliminar.html', {'cliente': cliente})


# Vista home
@login_required
def home(request):
    # Si el usuario tiene perfil de cliente, renderiza el panel del cliente
    if hasattr(request.user, 'cliente_perfil'):
        recuerdo_dia = RecuerdoEmocional.objects.filter(user=request.user).order_by('-fecha').first()
        motivacion = MotivacionUsuario.objects.filter(user=request.user).last()

        context = {
            'recuerdo_dia': recuerdo_dia,
            'motivacion': motivacion,
        }
        return render(request, 'clientes/panel_cliente.html', context)

    # Si no tiene perfil de cliente, se asume que es entrenador
    return redirect('dashboard_entrenador')


# Vista index
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .models import Cliente, RevisionProgreso
from django.utils.timezone import now
from datetime import timedelta
from joi.utils import (
    frase_motivadora_entrenador_estado,
    recuperar_frase_de_recaida,
    obtener_estado_joi,
    frase_cambio_forma_joi
)
# En tu archivo: clientes/views.py
# En tu archivo: clientes/views.py

# --- Asegúrate de tener estas importaciones al principio de tu archivo ---
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta, date, datetime
from django.db.models import Count, Avg, F, ExpressionWrapper, FloatField, Q
from django.db.models.functions import Cast  # <-- ¡IMPORTANTE!
import json
import logging

from .models import Cliente, RevisionProgreso
from entrenos.models import EntrenoRealizado, EjercicioRealizado
from analytics.analisis_intensidad import AnalisisIntensidadAvanzado

logger = logging.getLogger(__name__)


@login_required
def panel_entrenador(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Acceso solo para entrenadores.")

    # --- 1. OBTENER PARÁMETROS ---
    search_query = request.GET.get('q', '')
    filtro_estado = request.GET.get('filtro', 'todos')

    # --- 2. FILTRAR CLIENTES ---
    clientes_qs = Cliente.objects.all()
    if search_query:
        clientes_qs = clientes_qs.filter(nombre__icontains=search_query)

    # --- 3. CÁLCULOS GENERALES ---
    total_clientes_activos = clientes_qs.count()
    total_revisiones = RevisionProgreso.objects.count()
    hoy = timezone.now().date()
    entrenos_hoy_count = EntrenoRealizado.objects.filter(fecha=hoy).count()
    entrenos_semana_count = EntrenoRealizado.objects.filter(fecha__gte=hoy - timedelta(days=7)).count()

    # --- 4. LÓGICA ENRIQUECIDA PARA LISTAS Y MÓDULOS ---
    lista_clientes_enriquecida = []
    clientes_atencion = []

    clientes_con_entrenos = clientes_qs.prefetch_related('entrenorealizado_set')

    for cliente in clientes_con_entrenos:
        entrenos_cliente = cliente.entrenorealizado_set.all()
        entrenos_cliente_ordenados = sorted(entrenos_cliente, key=lambda e: e.fecha, reverse=True)

        ultimo_entreno = entrenos_cliente_ordenados[0] if entrenos_cliente_ordenados else None
        dias_inactivo = (hoy - ultimo_entreno.fecha).days if ultimo_entreno else 999

        hace_30_dias = hoy - timedelta(days=30)
        entrenos_mes = [e for e in entrenos_cliente_ordenados if e.fecha >= hace_30_dias]

        progreso_reciente = "Estable"
        progreso_color = "text-gray-400"
        if len(entrenos_mes) >= 2:
            primer_volumen = entrenos_mes[-1].volumen_total_kg or 0
            ultimo_volumen = entrenos_mes[0].volumen_total_kg or 0

            if (ultimo_volumen or 0) > (primer_volumen or 0) * Decimal('1.05'):
                progreso_reciente = "Positivo"
                progreso_color = "text-green-400"
            elif (ultimo_volumen or 0) < (primer_volumen or 0) * Decimal('0.95'):
                progreso_reciente = "Negativo"
                progreso_color = "text-red-400"

        consistencia = 0
        if entrenos_mes:
            consistencia = min(int((float(len(entrenos_mes)) / 4.0) * 100), 100)

        estado_fatiga = "N/A"
        nivel_fatiga_raw = "bajo"
        try:
            analizador = AnalisisIntensidadAvanzado(cliente)
            fatiga = analizador.calcular_fatiga_acumulada()
            if fatiga:
                estado_fatiga = fatiga.get('nivel', 'N/A').capitalize()
                nivel_fatiga_raw = fatiga.get('nivel', 'bajo')
        except Exception:
            pass

        if dias_inactivo >= 10:
            clientes_atencion.append(
                {'cliente': cliente, 'motivo': f'Inactivo ({dias_inactivo} días)', 'severidad': 'alta'})
        elif nivel_fatiga_raw in ['alta', 'critica']:
            clientes_atencion.append({'cliente': cliente, 'motivo': f'Fatiga {estado_fatiga}', 'severidad': 'media'})
        elif progreso_reciente == "Negativo":
            clientes_atencion.append({'cliente': cliente, 'motivo': 'Regresión en el último mes', 'severidad': 'media'})

        if (filtro_estado == 'inactivos' and dias_inactivo < 10) or \
                (filtro_estado == 'fatiga_alta' and nivel_fatiga_raw not in ['alta', 'critica']):
            continue

        lista_clientes_enriquecida.append({
            'cliente': cliente,
            'ultimo_entreno_fecha': ultimo_entreno.fecha if ultimo_entreno else None,
            'estado_fatiga': estado_fatiga,
            'progreso_reciente': progreso_reciente,
            'progreso_color': progreso_color,
            'consistencia': consistencia,
            'alertas_count': 0
        })

    # --- 5. LÓGICA DE GRÁFICOS ---
    inicio_ultimos_30_dias = hoy - timedelta(days=30)
    entrenos_recientes = EntrenoRealizado.objects.filter(fecha__gte=inicio_ultimos_30_dias)
    actividad_por_dia = entrenos_recientes.values('fecha__week_day').annotate(count=Count('id')).order_by(
        'fecha__week_day')
    dias_semana_map = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    datos_actividad = [0] * 7
    for item in actividad_por_dia:
        dia_django = item['fecha__week_day']
        if dia_django in dias_semana_map:
            datos_actividad[dias_semana_map[dia_django]] = item['count']
    grafico_actividad_data = {'labels': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'], 'data': datos_actividad}

    meses_labels = []
    progreso_1rm_data = []
    for i in range(5, -1, -1):
        mes_actual_inicio = (hoy.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        fin_mes = (mes_actual_inicio + timedelta(days=35)).replace(day=1) - timedelta(days=1)

        meses_labels.append(mes_actual_inicio.strftime("%b %Y"))

        ejercicios_del_mes = EjercicioRealizado.objects.filter(
            entreno__fecha__range=[mes_actual_inicio, fin_mes],
            peso_kg__gt=0, repeticiones__gt=0, repeticiones__lte=12
        )

        # ✅ CORRECCIÓN DEFINITIVA USANDO Cast
        rm_promedio_mes = ejercicios_del_mes.annotate(
            rm_estimado=ExpressionWrapper(
                Cast('peso_kg', FloatField()) * (1.0 + Cast('repeticiones', FloatField()) / 30.0),
                output_field=FloatField()
            )
        ).aggregate(avg_rm=Avg('rm_estimado'))['avg_rm']

        progreso_1rm_data.append(round(rm_promedio_mes, 1) if rm_promedio_mes else 0)
    grafico_progreso_data = {'labels': meses_labels, 'data': progreso_1rm_data}

    # --- 6. CONSTRUCCIÓN DEL CONTEXTO FINAL ---
    context = {
        'total_clientes': total_clientes_activos,
        'revisiones_totales': total_revisiones,
        'entrenos_hoy': entrenos_hoy_count,
        'entrenos_semana': entrenos_semana_count,
        'clientes_atencion': sorted(clientes_atencion, key=lambda x: x['severidad'])[:3],
        'lista_clientes': lista_clientes_enriquecida,
        'search_query': search_query,
        'filtro_actual': filtro_estado,
        'grafico_actividad_data': json.dumps(grafico_actividad_data),
        'grafico_progreso_data': json.dumps(grafico_progreso_data),
    }

    return render(request, 'clientes/panel_entrenador.html', context)


@login_required
def lista_clientes(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Acceso solo para entrenadores.")

    clientes = Cliente.objects.all()
    for cliente in clientes:
        cliente.ultima_revision = cliente.revisiones.order_by('-fecha').first()

    programas = Programa.objects.all()
    return render(request, 'clientes/index.html', {
        'clientes': clientes,
        'programas': programas,
        'today': date.today(),
    })


def asignar_programa_a_cliente(request, programa_id):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        cliente = get_object_or_404(Cliente, id=cliente_id)
        programa = get_object_or_404(Programa, id=programa_id)
        cliente.programa = programa
        cliente.save()
        return redirect('clientes:detalle_programa', programa_id=programa_id)


def actualizar_recordatorio_peso(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    fecha = request.POST.get("proximo_registro_peso")
    if fecha:
        cliente.proximo_registro_peso = fecha
        cliente.save()
    return HttpResponseRedirect(reverse("detalle_cliente", args=[cliente.id]))


from django.shortcuts import render


def blade_runner_demo(request):
    return render(request, 'clientes/blade-runner-demo.html')


# ... (asegúrate de tener estas importaciones al principio del archivo)
from datetime import date, timedelta
from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
from analytics.views import CalculadoraEjerciciosTabla
from decimal import Decimal, InvalidOperation


# en clientes/views.py

# ... (importaciones) ...

def obtener_proximo_entrenamiento(cliente):
    """
    Obtiene el próximo entrenamiento basándose en el plan generado por PlanificadorHelms.
    VERSIÓN FINAL CON LÓGICA DE BÚSQUEDA SIMPLIFICADA.
    """
    try:
        # --- PASO 1: Generar el plan anual completo (esto ya funciona) ---
        # (La lógica para generar el plan es la misma, no la repetimos aquí por brevedad)
        maximos_actuales = {}
        try:
            calculadora_rm = CalculadoraEjerciciosTabla(cliente)
            ejercicios_con_rm = calculadora_rm.obtener_ejercicios_tabla()
            for e in ejercicios_con_rm:
                try:
                    nombre_limpio = e.get('nombre', '').strip().lower()
                    peso_str = str(e.get('peso', '0')).replace(',', '.')
                    reps_valor = e.get('repeticiones', '0')
                    reps_str = str(reps_valor).split('-')[0].strip() if isinstance(reps_valor, str) else str(reps_valor)
                    if nombre_limpio and peso_str.replace('.', '', 1).isdigit() and reps_str.isdigit():
                        peso, reps = Decimal(peso_str), int(reps_str)
                        if peso > 0 and reps > 0:
                            rm_estimado = peso * (1 + Decimal(reps) / Decimal(30))
                            if nombre_limpio not in maximos_actuales or rm_estimado > maximos_actuales[nombre_limpio]:
                                maximos_actuales[nombre_limpio] = float(rm_estimado)
                except (ValueError, TypeError, InvalidOperation):
                    continue
        except Exception:
            maximos_actuales = {'press_banca': 80.0, 'sentadilla': 100.0}

        perfil = crear_perfil_desde_cliente(cliente)
        perfil.maximos_actuales = maximos_actuales
        planificador = PlanificadorHelms(perfil)
        plan_completo = planificador.generar_plan_anual()

        # --- PASO 2: Encontrar el próximo entrenamiento (LÓGICA NUEVA Y SIMPLE) ---
        hoy = date.today()
        entrenos_por_fecha = plan_completo.get('entrenos_por_fecha', {})

        # Ordenamos las fechas para buscar la próxima
        fechas_ordenadas = sorted(entrenos_por_fecha.keys())

        for fecha_str in fechas_ordenadas:
            fecha_entrenamiento = date.fromisoformat(fecha_str)

            if fecha_entrenamiento >= hoy:
                # ¡Encontramos el próximo entrenamiento!
                entrenamiento = entrenos_por_fecha[fecha_str]

                # Ahora, buscamos a qué bloque pertenece esta fecha
                bloque_info = {}
                for bloque in plan_completo.get('plan_por_bloques', []):
                    # Un bloque contiene una lista de diccionarios de semanas
                    # Verificamos si alguna de las semanas de este bloque contiene la fecha
                    # (Esto es una simplificación, asumimos que podemos encontrar el bloque por la fecha)
                    # Una forma más robusta sería calcular la semana del año de la fecha_entrenamiento
                    semana_del_año = fecha_entrenamiento.isocalendar()[1]

                    # Buscamos si el número de semana está en este bloque
                    for semana_data in bloque.get('semanas', []):
                        if semana_data['semana_num_total'] == semana_del_año:
                            bloque_info = {
                                'bloque_actual': bloque.get('nombre', 'N/A'),
                                'objetivo': bloque.get('objetivo', 'N/A'),
                                'semana_bloque': semana_del_año - bloque['semanas'][0]['semana_num_total'] + 1
                            }
                            break
                    if bloque_info:
                        break

                dias_semana_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

                return {
                    'dia': dias_semana_nombres[fecha_entrenamiento.weekday()],
                    'fecha': fecha_entrenamiento,
                    'dias_hasta': (fecha_entrenamiento - hoy).days,
                    'rutina_nombre': entrenamiento['nombre_rutina'],
                    'ejercicios': entrenamiento['ejercicios'][:3],
                    'total_ejercicios': len(entrenamiento['ejercicios']),
                    'bloque_actual': bloque_info.get('bloque_actual', 'Bloque Desconocido'),
                    'objetivo': bloque_info.get('objetivo', 'N/A'),
                    'semana_bloque': bloque_info.get('semana_bloque', 0),
                    'error': None
                }

        # Si el bucle termina, no hay más entrenamientos en el plan
        raise ValueError("Plan anual finalizado.")

    except Exception as e:
        # Si algo falla, devolvemos un diccionario de error claro
        return {
            'error': str(e),
            'rutina_nombre': 'Plan Finalizado o Error',
            'dia': 'N/A',
            'fecha': None,
            'dias_hasta': 0,
            'ejercicios': [],
            'total_ejercicios': 0,
            'bloque_actual': '-',
            'objetivo': '-',
            'semana_bloque': '-'
        }


# en clientes/views.py

# ... (asegúrate de tener estas importaciones al principio del archivo)
from analytics.planificador_helms_completo import PlanificadorHelms, crear_perfil_desde_cliente
from analytics.views import CalculadoraEjerciciosTabla
from decimal import Decimal, InvalidOperation


# ...

def obtener_estadisticas_plan_anual(cliente):
    """
    Obtiene estadísticas generales del plan anual del cliente.
    VERSIÓN FINAL Y SINCRONIZADA.
    """
    try:
        # --- PASO 1: Generar el plan anual completo (lógica unificada) ---
        maximos_actuales = {}
        try:
            calculadora_rm = CalculadoraEjerciciosTabla(cliente)
            ejercicios_con_rm = calculadora_rm.obtener_ejercicios_tabla()
            for e in ejercicios_con_rm:
                try:
                    nombre_limpio = e.get('nombre', '').strip().lower()
                    peso_str = str(e.get('peso', '0')).replace(',', '.')
                    reps_valor = e.get('repeticiones', '0')
                    reps_str = str(reps_valor).split('-')[0].strip() if isinstance(reps_valor, str) else str(reps_valor)
                    if nombre_limpio and peso_str.replace('.', '', 1).isdigit() and reps_str.isdigit():
                        peso, reps = Decimal(peso_str), int(reps_str)
                        if peso > 0 and reps > 0:
                            rm_estimado = peso * (1 + Decimal(reps) / Decimal(30))
                            if nombre_limpio not in maximos_actuales or rm_estimado > maximos_actuales[nombre_limpio]:
                                maximos_actuales[nombre_limpio] = float(rm_estimado)
                except (ValueError, TypeError, InvalidOperation):
                    continue
        except Exception:
            maximos_actuales = {'press_banca': 80.0, 'sentadilla': 100.0}

        perfil = crear_perfil_desde_cliente(cliente)
        perfil.maximos_actuales = maximos_actuales

        # ¡Usamos el planificador correcto!
        planificador = PlanificadorHelms(perfil)
        plan_completo = planificador.generar_plan_anual()

        # --- PASO 2: Calcular estadísticas desde el plan generado ---
        plan_por_bloques = plan_completo.get('plan_por_bloques', [])
        total_semanas = sum(bloque.get('duracion', 0) for bloque in plan_por_bloques)

        hoy = date.today()

        # Calcular la fecha de inicio del plan (primer lunes del año)
        primer_dia_del_año = date(hoy.year, 1, 1)
        dias_para_lunes = (0 - primer_dia_del_año.weekday() + 7) % 7
        fecha_inicio_plan = primer_dia_del_año + timedelta(days=dias_para_lunes)

        dias_transcurridos = max(0, (hoy - fecha_inicio_plan).days)

        if total_semanas > 0:
            semana_actual = min((dias_transcurridos // 7) + 1, total_semanas)
            progreso_porcentaje = min(100.0, (semana_actual / total_semanas) * 100.0)
        else:
            semana_actual = 0
            progreso_porcentaje = 0.0

        progreso_display = round(progreso_porcentaje, 1)

        progreso_css = f"{progreso_porcentaje:.1f}"

        return {
            'total_semanas': total_semanas,
            'semana_actual': semana_actual,
            'progreso_porcentaje_display': progreso_display,  # <-- Nuevo nombre para mostrar
            'progreso_porcentaje_css': progreso_css,  # <-- Nuevo nombre para el CSS
            'semanas_restantes': max(0, total_semanas - semana_actual),
            'error': None
        }


    except Exception as e:

        print(f"❌ ERROR en obtener_estadisticas_plan_anual: {e}")

        return {

            'total_semanas': 0,

            'semana_actual': 0,

            'progreso_porcentaje_display': 0,  # <-- Añadir valor por defecto

            'progreso_porcentaje_css': "0.0",  # <-- Añadir valor por defecto

            'semanas_restantes': 0,

            'error': str(e)

        }


# MODIFICAR tu vista existente del dashboard para incluir estos datos
def dashboard_cliente(request, cliente_id):
    """
    Vista del dashboard del cliente - MODIFICAR tu vista existente
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # ... tu lógica existente ...

    # AÑADIR estas líneas para obtener los datos del próximo entrenamiento
    proximo_entrenamiento = obtener_proximo_entrenamiento(cliente)
    estadisticas_plan = obtener_estadisticas_plan_anual(cliente)

    # AÑADIR al context existente
    context = {
        # ... tu context existente ...
        'proximo_entrenamiento': proximo_entrenamiento,
        'estadisticas_plan': estadisticas_plan,
    }

    return render(request, 'clientes/dashboard_cliente.html', context)


# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import PreferenciasHelmsForm
from .models import Cliente


@login_required
def configurar_preferencias_helms(request, cliente_id):
    """
    Vista para configurar las preferencias de adherencia según Helms.
    Ahora maneja un selector de nivel de experiencia y lo traduce al valor numérico del modelo.
    """
    # Se determina si el usuario es staff o un cliente normal para obtener el objeto cliente
    if request.user.is_staff:
        cliente = get_object_or_404(Cliente, id=cliente_id)
    else:
        # Un cliente solo puede editar su propio perfil
        cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)

    if request.method == 'POST':
        # Se instancia el formulario con los datos del POST y el objeto cliente
        form = PreferenciasHelmsForm(request.POST, instance=cliente)
        if form.is_valid():
            # --- LÓGICA DE TRADUCCIÓN AÑADIDA ---
            # 1. Obtenemos la instancia del cliente del formulario, pero NO la guardamos aún (commit=False).
            #    form.save() por sí solo daría un error porque 'nivel_experiencia_selector' no es un campo del modelo.
            #    Al usar commit=False, preparamos el objeto en memoria con los datos que sí coinciden.
            cliente_instance = form.save(commit=False)

            # 2. Tomamos el valor del selector del diccionario de datos validados del formulario.
            valor_experiencia_seleccionado = form.cleaned_data['nivel_experiencia_selector']

            # 3. Asignamos manualmente ese valor (convertido a float) al campo real del modelo.
            cliente_instance.experiencia_años = float(valor_experiencia_seleccionado)

            # 4. Ahora que el objeto cliente está completo y correcto, lo guardamos en la base de datos.
            cliente_instance.save()

            # 5. Los campos ManyToMany (si los tuvieras) se guardan después.
            #    En este caso no es necesario, pero es buena práctica saberlo: form.save_m2m()

            messages.success(
                request,
                f'✅ Preferencias actualizadas para {cliente.nombre}. '
                f'Tu programa ahora se adaptará mejor a tu estilo de vida.'
            )
            # Redirige a la URL correcta
            return redirect('entrenos:vista_plan_anual', cliente_id=cliente.id)
        else:
            messages.error(
                request,
                '❌ Por favor corrige los errores en el formulario.'
            )
    else:
        # Si es una petición GET, se muestra el formulario con los datos actuales del cliente
        form = PreferenciasHelmsForm(instance=cliente)

    # El contexto no necesita cambios, ya que la lógica para mostrar el nivel
    # de experiencia actual está en el __init__ del formulario.
    contexto = {
        'form': form,
        'cliente': cliente,
        'nivel_experiencia': cliente.get_nivel_experiencia(),
        'factor_recuperacion': cliente.get_factor_recuperacion(),
        'necesita_descarga': cliente.necesita_descarga(),
    }

    return render(request, 'clientes/configurar_preferencias_helms.html', contexto)


# en clientes/views.py

# --- Asegúrate de tener todas estas importaciones al principio del archivo ---
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from .models import Cliente  # Tu modelo de Cliente
from entrenos.models import EntrenoRealizado  # Tu modelo de entrenamientos
from analytics.monitor_adherencia import MonitorAdherencia, SesionEntrenamiento


# en clientes/views.py

# en clientes/views.py

@login_required
def dashboard_adherencia(request, cliente_id):
    # ... (lógica para obtener el cliente y el reporte)
    if request.user.is_staff:
        cliente = get_object_or_404(Cliente, id=cliente_id)
    else:
        cliente = get_object_or_404(Cliente, id=cliente_id, user=request.user)

    reporte_adherencia = calcular_reporte_adherencia_cliente(cliente)
    factor_recuperacion = cliente.get_factor_recuperacion()

    # --- INICIO DE LA CORRECCIÓN ---
    if factor_recuperacion >= 0.8:
        estado_adherencia = 'excelente'
        color_estado = 'success'
        mensaje_estado = 'Tu adherencia es excelente. ¡Sigue así!'
    elif factor_recuperacion >= 0.6:
        estado_adherencia = 'buena'
        color_estado = 'info'
        mensaje_estado = 'Buena adherencia. Pequeños ajustes pueden mejorarla.'
    else:  # <-- AÑADIR ESTE BLOQUE ELSE
        estado_adherencia = 'necesita_atencion'
        color_estado = 'warning'
        mensaje_estado = 'Tu adherencia necesita atención. Considera reducir intensidad.'
    # --- FIN DE LA CORRECCIÓN ---

    contexto = {
        'cliente': cliente,
        'reporte': reporte_adherencia,
        'factor_recuperacion': factor_recuperacion,
        'estado_adherencia': estado_adherencia,
        'color_estado': color_estado,
        'mensaje_estado': mensaje_estado,
        'dias_entrenamiento': cliente.dias_disponibles,
        'tiempo_total_semanal': (cliente.dias_disponibles or 0) * (cliente.tiempo_por_sesion or 0),
        'ejercicios_preferidos_count': len(cliente.ejercicios_preferidos or []),
        'ejercicios_evitar_count': len(cliente.ejercicios_evitar or [])
    }

    return render(request, 'clientes/dashboard_adherencia.html', contexto)


from datetime import date, timedelta
from django.utils import timezone
from .models import Cliente
from entrenos.models import EntrenoRealizado
from analytics.monitor_adherencia import MonitorAdherencia  # Asegúrate de que la importación esté


# en clientes/views.py

def calcular_reporte_adherencia_cliente(cliente: Cliente) -> dict:
    """
    Función ÚNICA y CORREGIDA para calcular el reporte de adherencia.
    Evita porcentajes mayores a 100%.
    """
    hoy = timezone.now().date()
    dia_actual_semana = hoy.weekday()
    inicio_semana = hoy - timedelta(days=dia_actual_semana)

    # 1. Contar entrenamientos completados ESTA SEMANA
    entrenamientos_completados = EntrenoRealizado.objects.filter(
        cliente=cliente,
        fecha__gte=inicio_semana
    ).count()

    # 2. Calcular sesiones planificadas HASTA HOY (Lógica mejorada)
    total_sesiones_semanales = cliente.dias_disponibles or 0
    sesiones_planificadas_hasta_hoy = 0
    if total_sesiones_semanales > 0:
        proporcion_semana = (dia_actual_semana + 1) / 7.0
        sesiones_planificadas_estimadas = round(proporcion_semana * total_sesiones_semanales)

        # --- INICIO DE LA CORRECCIÓN CLAVE ---
        # El número de sesiones planificadas no puede ser menor que las ya completadas.
        # Si el cliente ya hizo 2, lo mínimo planificado debe ser 2.
        sesiones_planificadas_hasta_hoy = max(entrenamientos_completados, sesiones_planificadas_estimadas)
        # --- FIN DE LA CORRECCIÓN CLAVE ---

    # 3. Calcular días perdidos CONSECUTIVOS (lógica más robusta)
    dias_perdidos = 0
    # ... (el resto de la lógica de días perdidos se queda igual)
    if entrenamientos_completados < sesiones_planificadas_hasta_hoy:
        ultimo_entreno = EntrenoRealizado.objects.filter(cliente=cliente).order_by('-fecha').first()
        if ultimo_entreno:
            dias_desde_ultimo_entreno = (hoy - ultimo_entreno.fecha).days
            if ultimo_entreno.fecha >= inicio_semana:
                dias_perdidos = dias_desde_ultimo_entreno
            else:
                dias_perdidos = dia_actual_semana + 1
        else:
            dias_perdidos = dia_actual_semana + 1

    # 4. Usar el MonitorAdherencia
    monitor = MonitorAdherencia(cliente_id=cliente.id)
    monitor.actualizar_y_evaluar(
        completadas=entrenamientos_completados,
        planificadas=sesiones_planificadas_hasta_hoy,
        dias_perdidos=dias_perdidos
    )

    return monitor.obtener_reporte_adherencia()


@login_required
def vista_educacion_helms(request, cliente_id):
    """
    Muestra una página educativa que explica los principios del plan del cliente.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Determinar el nivel educativo del cliente
    if cliente.experiencia_años < 1:
        nivel = NivelEducativo.PRINCIPIANTE
    else:
        nivel = NivelEducativo.INTERMEDIO

    # Crear una instancia del sistema educativo con el nivel del cliente
    sistema_educacion = SistemaEducacionHelms(nivel_usuario=nivel)

    context = {
        'cliente': cliente,
        'contenidos': sistema_educacion.contenidos,
    }

    return render(request, 'clientes/educacion_helms.html', context)


# En tu archivo: clientes/views.py

# --- Asegúrate de tener estas importaciones al principio del archivo ---
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import Cliente, BitacoraDiaria
from .forms import CheckinDiarioForm
from analytics.autorregulacion import calcular_ajuste_sesion
from entrenos.models import EntrenoRealizado, DetalleEjercicioRealizado  # ¡Importante!
from rutinas.models import Rutina


# --------------------------------------------------------------------


@transaction.atomic  # Usamos transacción para toda la vista, protegiendo tanto el check-in como el guardado del entreno
@login_required
def portal_sesion_unificado(request, cliente_id):
    """
    VISTA SIMPLIFICADA:
    - Su única misión es preparar y mostrar el portal de sesión.
    - Procesa el check-in diario si se envía ese formulario específico.
    - El guardado del entrenamiento se delega a la vista 'guardar_entrenamiento_activo'.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    hoy = timezone.now().date()

    # Procesar el check-in si se envía
    if request.method == 'POST':
        form = CheckinDiarioForm(request.POST)
        if form.is_valid():
            bitacora_hoy, created = BitacoraDiaria.objects.get_or_create(
                cliente=cliente, fecha=hoy,
                defaults=form.cleaned_data
            )
            if not created:
                for field, value in form.cleaned_data.items():
                    setattr(bitacora_hoy, field, value)
                bitacora_hoy.save()
            messages.success(request, "Check-in registrado. ¡Tu sesión ha sido ajustada!")
            return redirect('clientes:portal_sesion', cliente_id=cliente.id)

    # Lógica para mostrar la página (petición GET o si el form de check-in falló)
    bitacora_hoy = BitacoraDiaria.objects.filter(cliente=cliente, fecha=hoy).first()
    rutina_planificada = obtener_proximo_entrenamiento(cliente)

    if not rutina_planificada or rutina_planificada.get('fecha') != hoy:
        rutina_planificada = None

    ajuste_sesion = None
    rutina_ajustada = None

    if bitacora_hoy:
        ajuste_sesion = calcular_ajuste_sesion(
            energia=bitacora_hoy.energia_subjetiva,
            dolor=bitacora_hoy.dolor_articular,
            sueno=bitacora_hoy.horas_sueno
        )
        if rutina_planificada:
            rutina_ajustada = rutina_planificada.copy()
            for ejercicio in rutina_ajustada['ejercicios']:
                ejercicio['rpe_objetivo'] += ajuste_sesion.modificacion_rpe
                ejercicio['series'] = round(ejercicio['series'] * ajuste_sesion.modificacion_volumen)
                ejercicio['form_id'] = f"ej_{ejercicio['nombre'].replace(' ', '_')}"
                try:
                    reps_str = str(ejercicio.get('repeticiones', '8'))
                    ejercicio['reps_objetivo'] = int(reps_str.split('-')[0].strip())
                except:
                    ejercicio['reps_objetivo'] = 8
                ejercicio['tempo'] = ejercicio.get('tempo', '2-0-X-0')
                ejercicio['descanso_minutos'] = ejercicio.get('descanso_minutos', 2)
                ejercicio['peso_recomendado_kg'] = ejercicio.get('peso_kg', 0.0)

    context = {
        'cliente': cliente,
        'checkin_realizado': bitacora_hoy is not None,
        'checkin_form': CheckinDiarioForm(instance=bitacora_hoy) if bitacora_hoy else CheckinDiarioForm(),
        'ajuste_sesion': ajuste_sesion,
        'rutina_ajustada': rutina_ajustada,
        'leyenda_rpe': {
            "10": "Máximo esfuerzo...", "9": "Muy intenso...", "8": "Intenso...", "7": "Moderado...",
        }
    }
    return render(request, 'clientes/portal_sesion.html', context)


# En tu archivo: clientes/views.py

# --- Asegúrate de tener estas importaciones al principio del archivo ---
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import Cliente
from entrenos.models import EntrenoRealizado, DetalleEjercicioRealizado
from rutinas.models import Rutina
# En tu archivo: clientes/views.py

# --- Asegúrate de tener estas importaciones al principio del archivo ---
# ... (tus otras importaciones) ...
# En tu archivo: clientes/views.py

# --- Asegúrate de tener estas importaciones al principio del archivo ---
# ... (tus otras importaciones) ...
from rutinas.models import Rutina
from entrenos.models import EntrenoRealizado, EjercicioRealizado  # ¡¡CORRECCIÓN IMPORTANTE AQUÍ!!


# --------------------------------------------------------------------

@login_required
@require_POST
@transaction.atomic
def guardar_entrenamiento_activo(request, cliente_id):
    """
    VISTA CON LA CORRECCIÓN FINAL v3:
    - Usa el modelo correcto 'EjercicioRealizado'.
    - Pasa los argumentos correctos al crear el objeto.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)
    print(f"\n--- [VISTA FINAL v3] Iniciando guardado para {cliente.nombre} ---")

    try:
        # 1. Crear el objeto EntrenoRealizado principal (esto ya funciona bien)
        fecha_str = request.POST.get('fecha')
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        rutina_nombre = request.POST.get('rutina_nombre')
        rutina_obj, _ = Rutina.objects.get_or_create(nombre=rutina_nombre)

        entreno = EntrenoRealizado.objects.create(
            cliente=cliente,
            fecha=fecha,
            rutina=rutina_obj,
            fuente_datos='manual',
            duracion_minutos=request.POST.get('duracion_minutos') or None,
            calorias_quemadas=request.POST.get('calorias_quemadas') or None,
            notas_liftin=request.POST.get('notas_liftin', '').strip()
        )
        print(f"-> Creado EntrenoRealizado ID: {entreno.id}")

        # 2. Procesar cada ejercicio realizado
        volumen_total_entreno = Decimal('0.0')
        ejercicios_procesados_count = 0
        ejercicio_form_ids = {key.replace('_nombre', '') for key in request.POST if key.endswith('_nombre')}

        for form_id in ejercicio_form_ids:
            ejercicio_nombre = request.POST.get(f'{form_id}_nombre', '').strip().title()
            if not ejercicio_nombre: continue

            series_validas, reps_totales, peso_total_sumado, series_completadas, volumen_ejercicio = 0, 0, Decimal(
                '0.0'), 0, Decimal('0.0')

            for i in range(1, 11):
                peso_key, reps_key = f"{form_id}_peso_{i}", f"{form_id}_reps_{i}"
                if peso_key not in request.POST or reps_key not in request.POST: break

                try:
                    peso = Decimal(request.POST.get(peso_key, '0').replace(',', '.'))
                    reps = int(request.POST.get(reps_key, '0'))
                    if peso > 0 or reps > 0:
                        series_validas += 1
                        reps_totales += reps
                        peso_total_sumado += peso
                        volumen_ejercicio += (peso * reps)
                        if request.POST.get(f"{form_id}_completado_{i}") == "1":
                            series_completadas += 1
                except (ValueError, TypeError, InvalidOperation):
                    continue

            if series_validas > 0:
                # ==================================================================
                # CORRECCIÓN CLAVE: Usar el modelo y los campos correctos
                # ==================================================================
                EjercicioRealizado.objects.create(
                    entreno=entreno,
                    nombre_ejercicio=ejercicio_nombre,  # Pasamos el nombre como string
                    grupo_muscular="Otros",  # Valor por defecto, como en la imagen
                    peso_kg=float(peso_total_sumado / series_validas),
                    series=series_validas,
                    repeticiones=int(reps_totales / series_validas),
                    completado=(series_completadas == series_validas),
                    fuente_datos='manual'  # Asumiendo que este campo existe
                )
                # ==================================================================
                print(f"   -> Creado EjercicioRealizado para: {ejercicio_nombre}")
                volumen_total_entreno += volumen_ejercicio
                ejercicios_procesados_count += 1

        # 3. Actualizar el EntrenoRealizado con los totales
        entreno.volumen_total_kg = volumen_total_entreno
        entreno.numero_ejercicios = ejercicios_procesados_count
        entreno.save(update_fields=['volumen_total_kg', 'numero_ejercicios'])
        print(f"-> Entrenamiento ID {entreno.id} finalizado. Volumen: {volumen_total_entreno} kg.")

        messages.success(request, "¡Entrenamiento guardado con éxito! Tu progreso ha sido analizado.")
        return redirect('clientes:panel_cliente')

    except Exception as e:
        print(f"\n--- ❌ ERROR CRÍTICO DURANTE EL GUARDADO: {e} ---")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Hubo un error crítico al guardar el entrenamiento: {e}")
        return redirect('clientes:panel_cliente')


from collections import defaultdict


def obtener_historial_adherencia_semanal(cliente: Cliente, num_semanas: int = 12) -> list[float]:
    """
    Calcula el historial de porcentajes de adherencia de las últimas 'num_semanas'.
    Es robusta y maneja semanas sin entrenamientos.
    """
    hoy = timezone.now().date()
    historial_porcentajes = []

    # Obtenemos el número de sesiones que el cliente debe hacer por semana
    sesiones_planificadas_por_semana = cliente.dias_disponibles or 0

    # Si no hay un plan, no podemos calcular la adherencia.
    if sesiones_planificadas_por_semana == 0:
        return []

    # Iteramos hacia atrás desde la semana pasada durante 'num_semanas'
    for i in range(num_semanas):
        # Calculamos el inicio (lunes) y fin (domingo) de cada semana pasada
        dias_atras = (i * 7) + hoy.weekday() + 1
        fin_semana = hoy - timedelta(days=dias_atras)
        inicio_semana = fin_semana - timedelta(days=6)

        # Contamos cuántos entrenamientos se completaron en esa semana específica
        entrenos_completados_en_semana = EntrenoRealizado.objects.filter(
            cliente=cliente,
            fecha__range=[inicio_semana, fin_semana]
        ).count()

        # Calculamos el porcentaje de adherencia para esa semana
        porcentaje_semana = (entrenos_completados_en_semana / sesiones_planificadas_por_semana) * 100

        # Nos aseguramos de que el porcentaje no supere el 100%
        porcentaje_final = min(porcentaje_semana, 100.0)

        historial_porcentajes.append(porcentaje_final)

    # La lista está en orden cronológico inverso (la semana pasada primero), la invertimos
    return list(reversed(historial_porcentajes))


# Vistas para el control de peso y evolución
# Asegúrate de tener esta importación al principio de tu archivo de vistas
from django.core.serializers import serialize
import json


# ... (otras importaciones)

@login_required
def control_peso_cliente(request, cliente_id):
    from .peso_analytics import AnalizadorPeso

    cliente = get_object_or_404(Cliente, id=cliente_id)

    # 1. Obtenemos los registros como siempre para usarlos en el HTML (bucles, etc.)
    registros_peso_queryset = PesoDiario.objects.filter(cliente=cliente).order_by("fecha")

    # 2. Creamos una versión serializada específicamente para JavaScript
    #    Usamos serialize para convertir el queryset a un string JSON con el formato correcto.
    registros_peso_json = serialize('json', registros_peso_queryset, fields=('fecha', 'peso_kg'))

    objetivos_peso = ObjetivoPeso.objects.filter(cliente=cliente).order_by("-fecha_inicio")

    peso_form = PesoDiarioForm()
    objetivo_form = ObjetivoPesoForm()

    # Análisis avanzado de peso
    analytics = {}
    if registros_peso_queryset.exists():
        analizador = AnalizadorPeso(registros_peso_queryset)
        objetivo_activo = objetivos_peso.filter(alcanzado=False).first()
        peso_objetivo = float(objetivo_activo.peso_objetivo_kg) if objetivo_activo else None
        analytics = analizador.generar_resumen_completo(peso_objetivo)
    progreso_radial_data = None
    objetivo_activo = objetivos_peso.filter(alcanzado=False).first()

    if objetivo_activo and registros_peso_queryset.exists():
        registro_inicial_obj = registros_peso_queryset.filter(fecha__gte=objetivo_activo.fecha_inicio).first()
        if not registro_inicial_obj:
            registro_inicial_obj = registros_peso_queryset.first()

        peso_inicial = float(registro_inicial_obj.peso_kg)
        peso_actual = float(registros_peso_queryset.last().peso_kg)
        peso_objetivo = float(objetivo_activo.peso_objetivo_kg)

        # Determinar si es un objetivo de ganancia o pérdida
        es_objetivo_de_ganancia = peso_objetivo > peso_inicial

        if es_objetivo_de_ganancia:
            # Lógica para GANAR peso
            total_a_ganar = peso_objetivo - peso_inicial
            ganado_hasta_ahora = peso_actual - peso_inicial

            porcentaje_progreso = 0
            if total_a_ganar > 0:
                porcentaje_progreso = (ganado_hasta_ahora / total_a_ganar) * 100
        else:
            # Lógica para PERDER peso (la que ya teníamos)
            total_a_perder = peso_inicial - peso_objetivo
            perdido_hasta_ahora = peso_inicial - peso_actual

            porcentaje_progreso = 0
            if total_a_perder > 0:
                porcentaje_progreso = (perdido_hasta_ahora / total_a_perder) * 100

        # Aseguramos que el porcentaje esté siempre entre 0 y 100
        porcentaje_progreso = max(0, min(100, porcentaje_progreso))
        progreso_radial_data = {
            "peso_actual": f"{peso_actual:.1f}",
            "peso_objetivo": f"{peso_objetivo:.1f}",
            "peso_inicial": f"{peso_inicial:.1f}",
            "porcentaje_progreso": round(porcentaje_progreso),

        }
    context = {
        "cliente": cliente,
        "registros_peso": registros_peso_queryset,  # Para el historial en HTML
        "registros_peso_json": registros_peso_json,  # ¡La nueva variable para el gráfico!
        "objetivos_peso": objetivos_peso,
        "peso_form": peso_form,
        "objetivo_form": objetivo_form,
        "analytics": analytics,
        "progreso_radial_data": progreso_radial_data,
    }
    return render(request, "clientes/control_peso.html", context)


from .models import Cliente, PesoDiario, ObjetivoPeso, RevisionProgreso, Medida, BitacoraDiaria, ObjetivoCliente, \
    SugerenciaAceptada


@login_required
def registrar_peso(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == "POST":
        form = PesoDiarioForm(request.POST)
        if form.is_valid():
            peso_diario = form.save(commit=False)
            peso_diario.cliente = cliente
            peso_diario.fecha = date.today()  # Asegurarse de que la fecha sea la de hoy
            try:
                peso_diario.save()
                messages.success(request, "Peso registrado exitosamente.")
            except IntegrityError:  # Manejar el caso de que ya exista un registro para hoy
                messages.error(request, "Ya existe un registro de peso para hoy. Puedes editarlo.")
            return redirect("clientes:control_peso_cliente", cliente_id=cliente.id)
        else:
            messages.error(request, "Error al registrar el peso. Por favor, revisa los datos.")
    return redirect("clientes:control_peso_cliente", cliente_id=cliente.id)


@login_required
def establecer_objetivo_peso(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if request.method == "POST":
        form = ObjetivoPesoForm(request.POST)
        if form.is_valid():
            objetivo_peso = form.save(commit=False)
            objetivo_peso.cliente = cliente
            objetivo_peso.save()
            messages.success(request, "Objetivo de peso establecido exitosamente.")
            return redirect("clientes:control_peso_cliente", cliente_id=cliente.id)
        else:
            messages.error(request, "Error al establecer el objetivo. Por favor, revisa los datos.")
    return redirect("clientes:control_peso_cliente", cliente_id=cliente.id)


def obtener_proximo_entrenamiento_simplificado(cliente):
    try:
        # 1. Leemos los 1RM directamente del cliente. ¡Nuestra única fuente de verdad!
        maximos_actuales = cliente.one_rm_data or {}

        # 2. Creamos el perfil para el planificador
        perfil = crear_perfil_desde_cliente(cliente)
        perfil.maximos_actuales = maximos_actuales

        # 3. Generamos el plan y buscamos el día de hoy
        planificador = PlanificadorHelms(perfil)
        hoy = timezone.now().date()
        entrenamiento_hoy = planificador.generar_entrenamiento_para_fecha(hoy)

        if not entrenamiento_hoy or not entrenamiento_hoy.get("ejercicios"):
            return None  # Es un día de descanso

        return entrenamiento_hoy

    except Exception as e:
        print(f"Error en obtener_proximo_entrenamiento_simplificado: {e}")
        return None


# en clientes/views.py

# ... (tus otras importaciones) ...
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Cliente
from analytics.sistema_educacion_helms import SistemaEducacionHelms, NivelEducativo  # ¡Importante!


# ... (tus otras vistas) ...

# =======================================================
# ¡AÑADE ESTA NUEVA VISTA!
# =======================================================
@login_required
def vista_educacion_helms(request, cliente_id):
    """
    Muestra una página educativa que explica los principios del plan del cliente,
    adaptada a su nivel de experiencia.
    """
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # 1. Determinar el nivel educativo del cliente basándose en sus años de experiencia.
    #    Usamos la misma lógica que en el planificador para mantener la consistencia.
    if cliente.experiencia_años < 1:
        nivel_cliente = NivelEducativo.PRINCIPIANTE
    elif cliente.experiencia_años < 3:
        nivel_cliente = NivelEducativo.INTERMEDIO
    else:
        nivel_cliente = NivelEducativo.AVANZADO

    # 2. Crear una instancia del sistema educativo con el nivel del cliente.
    sistema_educativo = SistemaEducacionHelms(nivel_usuario=nivel_cliente)

    # 3. El sistema educativo ya tiene el diccionario 'contenidos' listo para usar.
    #    No necesitamos hacer nada más.

    # 4. Preparamos el contexto para pasarlo al template.
    context = {
        'cliente': cliente,
        'contenidos': sistema_educativo.contenidos,
    }

    # 5. Renderizamos el template que ya has creado.
    return render(request, 'clientes/educacion_helms.html',
                  context)  # Asegúrate de que la ruta al template sea correcta
