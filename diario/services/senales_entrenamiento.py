from datetime import timedelta

from django.utils import timezone

from clientes.utils import get_cliente_actual
from diario.models import SeguimientoVires

# ── helpers internos para computar señal desde listas en memoria ─────────────

def _clasificar_senal(vires_ventana):
    """
    Aplica las mismas reglas de intensidad sobre una lista de SeguimientoVires ya filtrada.
    Devuelve dict con hay_senal, intensidad, etc. — o {'hay_senal': False}.
    """
    if not vires_ventana:
        return {'hay_senal': False}

    n_dolorido = sum(1 for v in vires_ventana if v.cuerpo_cierre == 'dolorido')
    n_cargado_apagado = sum(1 for v in vires_ventana if v.cuerpo_cierre in ('cargado', 'apagado'))
    n_energia_baja = sum(1 for v in vires_ventana if v.nivel_energia is not None and v.nivel_energia <= 2)
    tiene_molestia_zona = any(
        v.molestia_zona and v.molestia_zona != 'ninguna'
        for v in vires_ventana
    )

    if n_dolorido >= 2 or (n_dolorido >= 1 and tiene_molestia_zona):
        return {'hay_senal': True, 'intensidad': 'alta'}
    if n_cargado_apagado >= 3 or (n_energia_baja >= 2 and n_cargado_apagado >= 1):
        return {'hay_senal': True, 'intensidad': 'moderada'}
    if n_cargado_apagado >= 2:
        return {'hay_senal': True, 'intensidad': 'suave'}
    return {'hay_senal': False}


def _tipo_contraste(senal, ejercicios):
    """
    Dado un dict de señal y una lista de EjercicioRealizado, devuelve el tipo de contraste.
    Returns 'alineado', 'no_limitante', 'observacion' o None.
    """
    intensidad = senal.get('intensidad')
    rpes = [e.rpe for e in ejercicios if e.rpe is not None]
    rpe_promedio = sum(rpes) / len(rpes) if rpes else None
    hay_recovery = any(getattr(e, 'is_recovery_load', False) for e in ejercicios)

    if intensidad == 'suave':
        return 'observacion' if (rpe_promedio and rpe_promedio >= 8.5) else None

    if hay_recovery or (rpe_promedio and rpe_promedio >= 8):
        return 'alineado'
    return 'no_limitante'


def obtener_senal_corporal_diario(usuario, n_dias=5, fecha_ref=None):
    """
    Lee las últimas n_dias entradas de SeguimientoVires y devuelve una señal
    informativa sobre el estado corporal reciente.

    Esta señal NO bloquea progresión ni cambia cargas. Es solo contexto.

    Reglas de intensidad (por prioridad, de alta a baja):
      alta     — dolorido x2, o dolorido + molestia_zona registrada
      moderada — cargado/apagado x3+, o 2 días energía baja (≤2) + al menos 1 cargado
      suave    — cargado/apagado x2
      (sin señal si <2 días pesados)

    fecha_ref: fecha de referencia (default = hoy). Permite anclar la ventana a una fecha pasada.

    Returns dict con hay_senal=True|False.
    """
    hoy = fecha_ref or timezone.now().date()
    inicio = hoy - timedelta(days=n_dias - 1)
    vires = list(
        SeguimientoVires.objects
        .filter(usuario=usuario, fecha__range=[inicio, hoy])
        .order_by('-fecha')
    )

    if not vires:
        return {'hay_senal': False}

    n_dolorido = sum(1 for v in vires if v.cuerpo_cierre == 'dolorido')
    n_cargado_apagado = sum(1 for v in vires if v.cuerpo_cierre in ('cargado', 'apagado'))
    n_energia_baja = sum(1 for v in vires if v.nivel_energia is not None and v.nivel_energia <= 2)
    tiene_molestia_zona = any(
        v.molestia_zona and v.molestia_zona != 'ninguna'
        for v in vires
    )

    # — Alta
    if n_dolorido >= 2 or (n_dolorido >= 1 and tiene_molestia_zona):
        return {
            'hay_senal': True,
            'intensidad': 'alta',
            'accion': 'revisar_carga',
            'texto': 'El cuerpo ha registrado dolor en los últimos días. Vale la pena revisar la carga de hoy.',
            'sugerencia': 'Si la molestia aparece al calentar, usa versión esencial o revisa los ejercicios sensibles.',
            'n_dias': n_dias,
            'dias_con_datos': len(vires),
        }

    # — Moderada
    if n_cargado_apagado >= 3 or (n_energia_baja >= 2 and n_cargado_apagado >= 1):
        return {
            'hay_senal': True,
            'intensidad': 'moderada',
            'accion': 'version_esencial',
            'texto': 'Varios cierres recientes con cuerpo cargado o apagado. Una versión esencial de la sesión es válida.',
            'sugerencia': 'Hoy conviene empezar con margen: primera serie controlada, sin perseguir récords.',
            'n_dias': n_dias,
            'dias_con_datos': len(vires),
        }

    # — Suave
    if n_cargado_apagado >= 2:
        return {
            'hay_senal': True,
            'intensidad': 'suave',
            'accion': 'observar',
            'texto': 'Algo de carga corporal en los últimos días. Observar cómo responde el cuerpo hoy.',
            'n_dias': n_dias,
            'dias_con_datos': len(vires),
        }

    return {'hay_senal': False}


def contrastar_senal_vs_entreno(usuario, fecha):
    """
    Contrasta la señal corporal activa en `fecha` contra el resultado del entrenamiento de ese día.

    No predice, no juzga, no culpa. Solo observa si la señal y el resultado se alinean.

    Returns dict con 'texto' y 'tipo', o None si no hay suficientes datos para contrastar.
    """
    senal = obtener_senal_corporal_diario(usuario, n_dias=5, fecha_ref=fecha)
    if not senal.get('hay_senal'):
        return None

    try:
        from entrenos.models import EntrenoRealizado
        cliente = get_cliente_actual(usuario)
        entreno = EntrenoRealizado.objects.filter(cliente=cliente, fecha=fecha).first()
    except Exception:
        return None

    if not entreno:
        return None

    ejercicios = list(entreno.ejercicios_realizados.all())
    rpes = [e.rpe for e in ejercicios if e.rpe is not None]
    rpe_promedio = sum(rpes) / len(rpes) if rpes else None
    hay_recovery = any(getattr(e, 'is_recovery_load', False) for e in ejercicios)

    intensidad = senal['intensidad']

    # Suave: solo anota si el RPE fue muy alto (la señal quizás avisaba algo real)
    if intensidad == 'suave':
        if rpe_promedio and rpe_promedio >= 8.5:
            return {
                'tipo': 'observacion',
                'texto': 'El diario registraba algo de carga corporal. El entreno salió con RPE alto; la señal queda anotada.',
            }
        return None  # suave + entreno fluido = sin contraste relevante

    # Moderada/alta: siempre hay algo que observar
    if hay_recovery or (rpe_promedio and rpe_promedio >= 8):
        return {
            'tipo': 'alineado',
            'texto': 'El diario avisaba de carga corporal y el entreno terminó con margen justo. La señal queda reforzada provisionalmente.',
        }
    return {
        'tipo': 'no_limitante',
        'texto': 'El diario señalaba carga, pero el entreno salió con margen. No se descarta la señal; hoy no limitó la sesión.',
    }


def calcular_tendencia_senal(usuario, n_semanas=4, n_dias_senal=5):
    """
    Detecta si hay una tendencia de señales corporales repetidas en las últimas n_semanas.

    Usa dos queries (prefetch de vires y entrenos) para no iterar con N queries.

    Reglas:
      score = n_alineados - n_no_limitante // 2   (cada 2 no_limitante atenúan 1)
      0-1  → sin tendencia
      2-3  → tendencia suave  (a vigilar)
      4+   → tendencia notable (requiere más atención)

    No modifica cargas ni progresión.
    """
    hoy = timezone.now().date()
    inicio = hoy - timedelta(days=n_semanas * 7 - 1)
    inicio_vires = inicio - timedelta(days=n_dias_senal - 1)

    # ── Prefetch todo en dos queries ────────────────────────────────────────
    todos_vires = list(
        SeguimientoVires.objects
        .filter(usuario=usuario, fecha__range=[inicio_vires, hoy])
        .order_by('fecha')
    )

    try:
        from entrenos.models import EntrenoRealizado
        cliente = get_cliente_actual(usuario)
        entrenos_map = {
            e.fecha: list(e.ejercicios_realizados.all())
            for e in EntrenoRealizado.objects
            .filter(cliente=cliente, fecha__range=[inicio, hoy])
            .prefetch_related('ejercicios_realizados')
        }
    except Exception:
        return {'hay_tendencia': False}

    if not entrenos_map:
        return {'hay_tendencia': False}

    # ── Iterar días ─────────────────────────────────────────────────────────
    n_alineados = 0
    n_no_limitante = 0

    fecha_iter = inicio
    while fecha_iter <= hoy:
        if fecha_iter in entrenos_map:
            ventana_inicio = fecha_iter - timedelta(days=n_dias_senal - 1)
            vires_ventana = [v for v in todos_vires if ventana_inicio <= v.fecha <= fecha_iter]
            senal = _clasificar_senal(vires_ventana)
            if senal.get('hay_senal') and senal.get('intensidad') in ('moderada', 'alta'):
                tipo = _tipo_contraste(senal, entrenos_map[fecha_iter])
                if tipo == 'alineado':
                    n_alineados += 1
                elif tipo == 'no_limitante':
                    n_no_limitante += 1
        fecha_iter += timedelta(days=1)

    # ── Calcular score ───────────────────────────────────────────────────────
    score = max(0, n_alineados - n_no_limitante // 2)

    if score <= 1:
        return {'hay_tendencia': False}

    if score <= 3:
        return {
            'hay_tendencia': True,
            'nivel': 'suave',
            'n_alineados': n_alineados,
            'n_semanas': n_semanas,
            'texto': (
                f'En las últimas {n_semanas} semanas, la señal del diario coincidió '
                f'{n_alineados} veces con entrenos de margen justo. '
                'Queda como tendencia a vigilar, no como diagnóstico.'
            ),
        }

    return {
        'hay_tendencia': True,
        'nivel': 'notable',
        'n_alineados': n_alineados,
        'n_semanas': n_semanas,
        'texto': (
            f'La señal del diario y los entrenos exigentes coinciden de forma repetida '
            f'en las últimas {n_semanas} semanas ({n_alineados} veces). '
            'No cambia el plan. Merece atención continuada.'
        ),
    }
