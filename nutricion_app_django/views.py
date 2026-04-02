from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
import json

from .models import (
    UserProfile, CalculoNivel1, CalculoNivel2, ProgresoNivel,
    SeguimientoPeso, ConfiguracionNivel3,
    PerfilNutricional, TargetNutricionalDiario, CheckNutricionalDiario,
    AjusteNutricional, RegistroBloques,
)
from .forms import UserProfileForm, Nivel1Form, Nivel2Form, SeguimientoPesoForm, PerfilNutricionalForm, CheckNutricionalForm
from .utils import CalculadoraNutricion, ValidadorNutricion
from .services import generar_target_diario
from .bloques_alimentos import PROTEINAS, CARBOS, GRASAS, VERDURAS, TODOS_LOS_ALIMENTOS, DOBLE_SESION_BONUS


@login_required
def recalcular_perfil(request):
    """Fuerza el recálculo de composición corporal y target del día."""
    try:
        cliente = request.user.cliente_perfil
        perfil = cliente.perfil_nutricional
        perfil.save()
        generar_target_diario(cliente)
        messages.success(request, f"Recalculado: {perfil.masa_magra_kg:.1f} kg masa magra, {perfil.grasa_corporal_pct:.1f}% grasa.")
    except Exception as e:
        messages.error(request, f"Error: {e}")
    return redirect('nutricion_app_django:dashboard_nutricional')


@login_required
def onboarding_nutricional(request):
    """
    Configuración inicial del perfil nutricional.
    Recoge altura + medidas para el cálculo Navy Method.
    """
    try:
        cliente = request.user.cliente_perfil
    except Exception:
        messages.error(request, "No tienes un perfil de cliente asociado.")
        return redirect('/')

    # Si ya tiene perfil, redirigir al dashboard
    if hasattr(cliente, 'perfil_nutricional'):
        return redirect('nutricion_app_django:dashboard_nutricional')

    initial = {
        'cintura_cm': cliente.cintura,
        'cuello_cm':  cliente.cuello,
        'caderas_cm': cliente.caderas,
        'altura_cm':  cliente.altura_cm,
    }

    if request.method == 'POST':
        form = PerfilNutricionalForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            # Validar caderas para mujeres
            if cliente.genero == 'F' and not data.get('caderas_cm'):
                form.add_error('caderas_cm', 'Las caderas son necesarias para calcular tu composición corporal.')
            else:
                # Actualizar medidas en Cliente
                cliente.altura_cm  = data['altura_cm']
                cliente.cintura    = data['cintura_cm']
                cliente.cuello     = data['cuello_cm']
                if data.get('caderas_cm'):
                    cliente.caderas = data['caderas_cm']
                cliente.save(update_fields=['altura_cm', 'cintura', 'cuello', 'caderas'])

                # Crear PerfilNutricional
                PerfilNutricional.objects.create(
                    cliente=cliente,
                    altura_cm=data['altura_cm'],
                )

                # Generar target del día de hoy
                generar_target_diario(cliente)

                messages.success(request, "Perfil nutricional configurado correctamente.")
                return redirect('nutricion_app_django:dashboard_nutricional')
    else:
        form = PerfilNutricionalForm(initial=initial)

    return render(request, 'nutricion_app_django/onboarding_nutricional.html', {
        'form': form,
        'cliente': cliente,
    })


@login_required
def dashboard_nutricional(request):
    """
    Panel principal del módulo nutricional.
    Muestra el target del día + check-in + tendencia de peso + últimos ajustes.
    """
    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return redirect('/')

    # Sin perfil → onboarding
    if not hasattr(cliente, 'perfil_nutricional'):
        return redirect('nutricion_app_django:onboarding_nutricional')

    cliente.refresh_from_db()

    hoy = date.today()

    # Target del día (generarlo si no existe)
    target = TargetNutricionalDiario.objects.filter(cliente=cliente, fecha=hoy).first()
    if not target:
        target = generar_target_diario(cliente)

    # Check de hoy
    check_hoy, _ = CheckNutricionalDiario.objects.get_or_create(cliente=cliente, fecha=hoy)
    check_completado = any([
        check_hoy.bloques_proteina_cumplidos is not None,
        check_hoy.bloques_carbos_cumplidos is not None,
        check_hoy.verduras_cumplidas is not None,
        check_hoy.hidratacion_ok is not None,
        check_hoy.fatiga_percibida is not None,
    ])

    if request.method == 'POST':
        form = CheckNutricionalForm(request.POST, instance=check_hoy)
        if form.is_valid():
            form.save()
            messages.success(request, "Check-in guardado.")
            return redirect('nutricion_app_django:dashboard_nutricional')
    else:
        form = CheckNutricionalForm(instance=check_hoy)

    # Tendencia de peso últimos 14 días
    from clientes.models import PesoDiario
    pesos = list(
        PesoDiario.objects
        .filter(cliente=cliente, fecha__gte=hoy - timedelta(days=13))
        .order_by('fecha')
        .values('fecha', 'peso_kg')
    )

    # Últimos ajustes del algoritmo
    ajustes = AjusteNutricional.objects.filter(cliente=cliente).order_by('-fecha')[:3]

    # Urgencia informe: escenario B/C pendiente de revisar
    from .models import InformeOptimizacion
    _ultimo_inf = InformeOptimizacion.objects.filter(cliente=cliente).order_by('-semana').first()
    informe_urgente = bool(
        _ultimo_inf and
        _ultimo_inf.escenario in ('B', 'C') and
        _ultimo_inf.estado == 'pendiente'
    )

    perfil = cliente.perfil_nutricional

    # Peso real: último PesoDiario o peso_corporal del cliente
    from clientes.models import PesoDiario
    ultimo_peso = (
        PesoDiario.objects
        .filter(cliente=cliente)
        .order_by('-fecha')
        .values_list('peso_kg', flat=True)
        .first()
    )
    peso_actual = ultimo_peso or cliente.peso_corporal

    # Bloques registrados hoy por comida
    registros_hoy = (
        RegistroBloques.objects
        .filter(cliente=cliente, fecha=hoy)
        .order_by('comida')
    )
    totales_hoy = {'P': 0.0, 'C': 0.0, 'G': 0.0}
    for r in registros_hoy:
        totales_hoy['P'] += r.bloques_proteina
        totales_hoy['C'] += r.bloques_carbos
        totales_hoy['G'] += r.bloques_grasas

    return render(request, 'nutricion_app_django/dashboard_nutricional.html', {
        'cliente':          cliente,
        'perfil':           perfil,
        'target':           target,
        'form':             form,
        'check_completado': check_completado,
        'pesos':            pesos,
        'ajustes':          ajustes,
        'hoy':              hoy,
        'peso_actual':      peso_actual,
        'registros_hoy':    registros_hoy,
        'totales_hoy':      totales_hoy,
        'informe_urgente':  informe_urgente,
    })


@login_required
def calculadora_bloques(request):
    """
    Calculadora visual de bloques por comida.
    Permite al usuario registrar qué alimentos come sin escribir gramos.
    """
    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return redirect('/')

    if not hasattr(cliente, 'perfil_nutricional'):
        return redirect('nutricion_app_django:onboarding_nutricional')

    hoy = date.today()

    target = TargetNutricionalDiario.objects.filter(cliente=cliente, fecha=hoy).first()
    if not target:
        target = generar_target_diario(cliente)

    registros_hoy = list(
        RegistroBloques.objects
        .filter(cliente=cliente, fecha=hoy)
        .order_by('comida', 'id')
        .values('id', 'comida', 'bloques_proteina', 'bloques_carbos', 'bloques_grasas',
                'es_comodin', 'nota_comodin', 'alimentos_json')
    )

    totales_hoy = {'P': 0.0, 'C': 0.0, 'G': 0.0}
    for r in registros_hoy:
        totales_hoy['P'] += r['bloques_proteina']
        totales_hoy['C'] += r['bloques_carbos']
        totales_hoy['G'] += r['bloques_grasas']

    # Distribución sugerida por comida desde el target
    distribucion = target.distribucion_comidas or {}

    # Detección de doble sesión (Hyrox + Gym el mismo día)
    from entrenos.models import EntrenoRealizado
    entrenos_hoy = EntrenoRealizado.objects.filter(cliente=cliente, fecha=hoy).count()
    doble_sesion = entrenos_hoy >= 2

    # Calcular calidad de bloques del día (% verde)
    calidad_bloques = _calcular_calidad_bloques(registros_hoy)

    return render(request, 'nutricion_app_django/calculadora_bloques.html', {
        'cliente':         cliente,
        'target':          target,
        'hoy':             hoy,
        'proteinas':       PROTEINAS,
        'carbos':          CARBOS,
        'grasas':          GRASAS,
        'verduras':        VERDURAS,
        'registros_hoy':   json.dumps(registros_hoy, default=str),
        'totales_hoy':     totales_hoy,
        'totales_hoy_json': json.dumps(totales_hoy),
        'distribucion':    json.dumps(distribucion),
        'alimentos_acn':   json.dumps(list(TODOS_LOS_ALIMENTOS.values()), default=str),
        'doble_sesion':    doble_sesion,
        'calidad_bloques': calidad_bloques,
    })


def _calcular_calidad_bloques(registros_hoy: list) -> dict:
    """
    Calcula el % de bloques 'verdes' del día a partir de los registros guardados.
    Lee alimentos_json de cada registro y cruza con TODOS_LOS_ALIMENTOS.
    """
    verdes = 0.0
    totales = 0.0
    for r in registros_hoy:
        if r.get('es_comodin'):
            continue
        alimentos_json = r.get('alimentos_json') or []
        if isinstance(alimentos_json, str):
            try:
                alimentos_json = json.loads(alimentos_json)
            except Exception:
                alimentos_json = []
        for item in alimentos_json:
            alimento_id = item.get('id') or item.get('alimento_id')
            cantidad = float(item.get('cantidad', 1))
            alimento = TODOS_LOS_ALIMENTOS.get(alimento_id)
            if not alimento:
                continue
            bloques = cantidad * (alimento.get('P', 0) + alimento.get('C', 0) + alimento.get('G', 0))
            totales += bloques
            if alimento.get('calidad') == 'verde':
                verdes += bloques
    pct = round(verdes / totales * 100) if totales > 0 else None
    return {'verde': verdes, 'total': totales, 'pct': pct}


@login_required
def manifiesto_atleta(request):
    """Manifiesto del atleta híbrido — onboarding 3 pantallas."""
    return render(request, 'nutricion_app_django/manifiesto_atleta.html')


@login_required
def ajax_guardar_bloques(request):
    """
    Endpoint AJAX para guardar un registro de bloques de una comida.
    Acepta POST con JSON body.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Sin perfil de cliente'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    comida = data.get('comida')
    COMIDAS_VALIDAS = {'desayuno', 'almuerzo', 'cena', 'snack', 'pre', 'post'}
    if comida not in COMIDAS_VALIDAS:
        return JsonResponse({'ok': False, 'error': 'Comida no válida'}, status=400)

    hoy = date.today()
    es_comodin = bool(data.get('es_comodin', False))
    alimentos_json = data.get('alimentos', [])

    # Calcular bloques desde alimentos seleccionados
    bloques_p = bloques_c = bloques_g = 0.0
    if not es_comodin:
        for item in alimentos_json:
            alimento_id = item.get('id')
            cantidad = float(item.get('cantidad', 1))
            alimento = TODOS_LOS_ALIMENTOS.get(alimento_id)
            if alimento:
                bloques_p += alimento.get('P', 0) * cantidad
                bloques_c += alimento.get('C', 0) * cantidad
                bloques_g += alimento.get('G', 0) * cantidad
    else:
        # Comodín: el usuario declara los bloques directamente
        bloques_p = float(data.get('bloques_proteina', 0))
        bloques_c = float(data.get('bloques_carbos', 0))
        bloques_g = float(data.get('bloques_grasas', 0))

    registro_id = data.get('id')
    if registro_id:
        # Actualizar registro existente
        try:
            registro = RegistroBloques.objects.get(id=registro_id, cliente=cliente)
            registro.comida = comida
            registro.bloques_proteina = round(bloques_p, 2)
            registro.bloques_carbos = round(bloques_c, 2)
            registro.bloques_grasas = round(bloques_g, 2)
            registro.es_comodin = es_comodin
            registro.nota_comodin = data.get('nota_comodin', '')
            registro.alimentos_json = alimentos_json if not es_comodin else None
            registro.save()
        except RegistroBloques.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Registro no encontrado'}, status=404)
    else:
        registro = RegistroBloques.objects.create(
            cliente=cliente,
            fecha=hoy,
            comida=comida,
            bloques_proteina=round(bloques_p, 2),
            bloques_carbos=round(bloques_c, 2),
            bloques_grasas=round(bloques_g, 2),
            es_comodin=es_comodin,
            nota_comodin=data.get('nota_comodin', ''),
            alimentos_json=alimentos_json if not es_comodin else None,
        )

    # Recalcular totales del día
    todos = RegistroBloques.objects.filter(cliente=cliente, fecha=hoy)
    totales = {'P': 0.0, 'C': 0.0, 'G': 0.0}
    for r in todos:
        totales['P'] += r.bloques_proteina
        totales['C'] += r.bloques_carbos
        totales['G'] += r.bloques_grasas

    return JsonResponse({
        'ok': True,
        'registro_id': registro.id,
        'totales': {k: round(v, 2) for k, v in totales.items()},
    })


@login_required
def informe_semanal(request):
    """
    Muestra el InformeOptimizacion de la semana más reciente.
    El entrenador/usuario puede aceptar o rechazar el ajuste propuesto.
    """
    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return redirect('/')

    if not hasattr(cliente, 'perfil_nutricional'):
        return redirect('nutricion_app_django:onboarding_nutricional')

    from .models import InformeOptimizacion
    from .services import analisis_semanal_pas

    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())

    # Obtener o generar el informe de esta semana
    informe = InformeOptimizacion.objects.filter(cliente=cliente, semana=lunes).first()
    if not informe:
        informe = analisis_semanal_pas(cliente, lunes=lunes)

    # Historial de informes anteriores (sin el actual)
    historial = (
        InformeOptimizacion.objects
        .filter(cliente=cliente)
        .exclude(semana=lunes)
        .order_by('-semana')[:8]
    )

    # Bloques del último target para mostrar comparativa antes/después
    target_actual = (
        TargetNutricionalDiario.objects
        .filter(cliente=cliente)
        .order_by('-fecha')
        .first()
    )
    target_p = target_actual.bloques_proteina if target_actual else 0
    target_c = target_actual.bloques_carbos   if target_actual else 0
    target_g = target_actual.bloques_grasas   if target_actual else 0

    return render(request, 'nutricion_app_django/informe_semanal.html', {
        'cliente':   cliente,
        'informe':   informe,
        'historial': historial,
        'hoy':       hoy,
        'lunes':     lunes,
        'target_p':  target_p,
        'target_c':  target_c,
        'target_g':  target_g,
    })


@login_required
def ajax_accion_informe(request):
    """
    Acepta o rechaza el ajuste propuesto en el InformeOptimizacion.
    POST JSON: { "informe_id": int, "accion": "aceptar"|"rechazar", "razon": str }
    Si se acepta, crea un AjusteNutricional y marca el informe como 'aceptado'.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Sin perfil'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    from .models import InformeOptimizacion, AjusteNutricional, TargetNutricionalDiario

    try:
        informe = InformeOptimizacion.objects.get(id=data['informe_id'], cliente=cliente)
    except InformeOptimizacion.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Informe no encontrado'}, status=404)

    if informe.estado != 'pendiente':
        return JsonResponse({'ok': False, 'error': 'El informe ya fue procesado'}, status=400)

    accion = data.get('accion')

    if accion == 'rechazar':
        informe.estado = 'rechazado'
        informe.razon_rechazo = data.get('razon', 'Semana atípica — sin ajuste')[:200]
        informe.save(update_fields=['estado', 'razon_rechazo'])
        return JsonResponse({'ok': True, 'estado': 'rechazado'})

    if accion == 'aceptar':
        # Obtener el último target para saber los bloques actuales
        hoy = date.today()
        target = (
            TargetNutricionalDiario.objects
            .filter(cliente=cliente)
            .order_by('-fecha')
            .first()
        )

        p_ant = target.bloques_proteina if target else 0
        c_ant = target.bloques_carbos   if target else 0
        g_ant = target.bloques_grasas   if target else 0

        # Crear registro de ajuste
        AjusteNutricional.objects.create(
            cliente=cliente,
            motivo=_motivo_desde_escenario(informe.escenario, informe.diet_break_sugerido),
            proteina_anterior=p_ant,
            proteina_nuevo=max(1, p_ant + informe.ajuste_bloques_proteina),
            carbos_anterior=c_ant,
            carbos_nuevo=max(1, c_ant + informe.ajuste_bloques_carbos),
            grasas_anterior=g_ant,
            grasas_nuevo=max(1, g_ant + informe.ajuste_bloques_grasas),
            aplica_a=informe.ajuste_aplica_a,
            mensaje_usuario=informe.justificacion[:500],
        )

        informe.estado = 'aceptado'
        informe.save(update_fields=['estado'])

        return JsonResponse({'ok': True, 'estado': 'aceptado'})

    return JsonResponse({'ok': False, 'error': 'Acción no válida'}, status=400)


def _motivo_desde_escenario(escenario, diet_break):
    if diet_break:
        return 'diet_break'
    mapping = {
        'A': 'inicio',
        'B': 'sin_progreso',
        'C': 'fatiga_alta',
        'D': 'progreso_rapido',
        'X': 'inicio',
    }
    return mapping.get(escenario, 'inicio')


@login_required
def monitor_progreso(request):
    """
    Sprint 7 + 8 — Monitor de Progreso + Estado de Recuperación.
    Muestra evolución de peso (media móvil 7d), cumplimiento semanal
    y panel de recuperación (fatiga, sueño, energía, alerta refeed).
    """
    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return redirect('/')

    if not hasattr(cliente, 'perfil_nutricional'):
        return redirect('nutricion_app_django:onboarding_nutricional')

    from clientes.models import PesoDiario
    from .models import CheckNutricionalDiario, InformeOptimizacion

    hoy = date.today()
    perfil = cliente.perfil_nutricional

    # ── Datos de peso (últimos 60 días) ──────────────────────────────
    pesos_qs = list(
        PesoDiario.objects
        .filter(cliente=cliente, fecha__gte=hoy - timedelta(days=59))
        .order_by('fecha')
        .values('fecha', 'peso_kg')
    )

    # Media móvil de 7 días
    def media_movil(datos, ventana=7):
        result = []
        for i, d in enumerate(datos):
            inicio = max(0, i - ventana + 1)
            ventana_vals = [x['peso_kg'] for x in datos[inicio:i+1]]
            result.append({
                'fecha': d['fecha'].isoformat(),
                'peso':  round(d['peso_kg'], 2),
                'mm7':   round(sum(ventana_vals) / len(ventana_vals), 2),
            })
        return result

    peso_data = media_movil(pesos_qs)

    # Tendencia lineal (regresión simple sobre mm7)
    tendencia_slope = None
    if len(peso_data) >= 7:
        vals = [d['mm7'] for d in peso_data]
        n = len(vals)
        x_mean = (n - 1) / 2
        y_mean = sum(vals) / n
        num = sum((i - x_mean) * (vals[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den:
            tendencia_slope = round(num / den, 4)  # kg/día

    # ── Cumplimiento semanal (últimas 8 semanas) ──────────────────────
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    cumplimiento_semanas = []
    for i in range(7, -1, -1):  # 8 semanas, más antigua primero
        lun = lunes_actual - timedelta(weeks=i)
        dom = lun + timedelta(days=6)
        checks = CheckNutricionalDiario.objects.filter(
            cliente=cliente, fecha__range=(lun, dom)
        )
        if checks.exists():
            media = round(sum(c.cumplimiento_pct for c in checks) / checks.count(), 1)
        else:
            media = None
        cumplimiento_semanas.append({
            'semana': lun.isoformat(),
            'label':  lun.strftime('%d/%m'),
            'pct':    media,
        })

    # ── Biofeedback últimos 7 días ────────────────────────────────────
    hace7 = hoy - timedelta(days=6)
    checks_recientes = list(
        CheckNutricionalDiario.objects
        .filter(cliente=cliente, fecha__gte=hace7)
        .order_by('fecha')
    )

    fatiga_vals  = [c.fatiga_percibida for c in checks_recientes if c.fatiga_percibida is not None]
    sueno_vals   = [c.calidad_sueno    for c in checks_recientes if c.calidad_sueno    is not None]
    energia_vals = [c.energia_entreno  for c in checks_recientes if c.energia_entreno  is not None]

    fatiga_media  = round(sum(fatiga_vals)  / len(fatiga_vals),  1) if fatiga_vals  else None
    sueno_media   = round(sum(sueno_vals)   / len(sueno_vals),   1) if sueno_vals   else None
    energia_media = round(sum(energia_vals) / len(energia_vals), 1) if energia_vals else None

    # Alerta de refeed: fatiga ≥ 7 en 3+ de los últimos 7 días
    dias_fatiga_alta = sum(1 for v in fatiga_vals if v >= 7)
    alerta_refeed = dias_fatiga_alta >= 3

    # Detalle diario biofeedback para gráfico
    bio_data = []
    for d_offset in range(6, -1, -1):
        dia = hoy - timedelta(days=d_offset)
        check = next((c for c in checks_recientes if c.fecha == dia), None)
        bio_data.append({
            'fecha':   dia.isoformat(),
            'label':   dia.strftime('%a %d'),
            'fatiga':  check.fatiga_percibida if check else None,
            'sueno':   check.calidad_sueno    if check else None,
            'energia': check.energia_entreno  if check else None,
            'cumpl':   round(check.cumplimiento_pct) if check and check.cumplimiento_pct is not None else None,
        })

    # ── Últimos informes para contexto ───────────────────────────────
    ultimo_informe = (
        InformeOptimizacion.objects
        .filter(cliente=cliente)
        .order_by('-semana')
        .first()
    )

    return render(request, 'nutricion_app_django/monitor_progreso.html', {
        'cliente':             cliente,
        'perfil':              perfil,
        'hoy':                 hoy,
        'peso_data':           json.dumps(peso_data),
        'tendencia_slope':     tendencia_slope,
        'cumplimiento_semanas': json.dumps(cumplimiento_semanas),
        'fatiga_media':        fatiga_media,
        'sueno_media':         sueno_media,
        'energia_media':       energia_media,
        'dias_fatiga_alta':    dias_fatiga_alta,
        'alerta_refeed':       alerta_refeed,
        'bio_data':            json.dumps(bio_data),
        'ultimo_informe':      ultimo_informe,
    })


@login_required
def ajax_eliminar_bloque(request):
    """Elimina un registro de bloques por id."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        cliente = request.user.cliente_perfil
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Sin perfil'}, status=403)

    try:
        data = json.loads(request.body)
        registro_id = data.get('id')
        RegistroBloques.objects.get(id=registro_id, cliente=cliente).delete()
    except (RegistroBloques.DoesNotExist, Exception):
        return JsonResponse({'ok': False, 'error': 'No encontrado'}, status=404)

    hoy = date.today()
    todos = RegistroBloques.objects.filter(cliente=cliente, fecha=hoy)
    totales = {'P': 0.0, 'C': 0.0, 'G': 0.0}
    for r in todos:
        totales['P'] += r.bloques_proteina
        totales['C'] += r.bloques_carbos
        totales['G'] += r.bloques_grasas

    return JsonResponse({'ok': True, 'totales': {k: round(v, 2) for k, v in totales.items()}})


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
