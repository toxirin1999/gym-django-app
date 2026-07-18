# diario/insights_engine.py

from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg
from .models import ProsocheDiario, SeguimientoVires, Gesto
from django.urls import reverse
from .services import analizador_gestos as az


# ── Fase 5C — lectura principal (presentación y lenguaje) ──────────────────
#
# Traduce la salida canónica del analizador a UNA frase por hábito, sin
# afirmar nada que la métrica de origen tenga prohibido interpretar.
# Criterio de cierre del contrato: cada frase visible debe poder
# justificarse con una métrica concreta.

TIPO_LECTURA_DESCRIPTIVA = 'descriptiva'
TIPO_LECTURA_CUMPLIMIENTO = 'cumplimiento'
TIPO_LECTURA_SEMANA_PARCIAL = 'semana_parcial'
TIPO_LECTURA_NO_EVALUABLE = 'no_evaluable'
TIPO_LECTURA_INSUFICIENTE = 'insuficiente'

_ETIQUETA_POR_TIPO_LECTURA = {
    TIPO_LECTURA_DESCRIPTIVA: 'Descriptivo',
    TIPO_LECTURA_CUMPLIMIENTO: 'Cumplimiento',
    TIPO_LECTURA_SEMANA_PARCIAL: 'Semana parcial',
    TIPO_LECTURA_NO_EVALUABLE: 'No evaluable',
    TIPO_LECTURA_INSUFICIENTE: 'Datos insuficientes',
}


def _lectura_ok(texto, tipo_lectura, periodo_desde, periodo_hasta, dias_excluidos=None):
    dias_excluidos = dias_excluidos or {}
    return {
        'estado': 'ok',
        'texto': texto,
        'tipo_lectura': tipo_lectura,
        'etiqueta': _ETIQUETA_POR_TIPO_LECTURA[tipo_lectura],
        'trazabilidad': {
            'periodo_desde': periodo_desde,
            'periodo_hasta': periodo_hasta,
            'dias_excluidos': dias_excluidos,
            'total_dias_excluidos': sum(len(v) for v in dias_excluidos.values()),
        },
        'nota_secundaria': None,
    }


def _lectura_insuficiente():
    return {
        'estado': 'insuficiente',
        'texto': 'Datos insuficientes todavía.',
        'tipo_lectura': TIPO_LECTURA_INSUFICIENTE,
        'etiqueta': _ETIQUETA_POR_TIPO_LECTURA[TIPO_LECTURA_INSUFICIENTE],
        'trazabilidad': None,
        'nota_secundaria': None,
    }


def _nota_semana_actual(valor_m11):
    """Nota aparte sobre la semana en curso/parcial más reciente — nunca
    se mezcla con la lectura principal de semanas completas."""
    en_curso = valor_m11.get('semana_en_curso')
    if en_curso:
        return {
            'texto': f'Semana en curso: {en_curso["cumplidos_hasta_ahora"]} de {en_curso["objetivo"]} hasta ahora.',
            'tipo': TIPO_LECTURA_SEMANA_PARCIAL,
            'etiqueta': _ETIQUETA_POR_TIPO_LECTURA[TIPO_LECTURA_SEMANA_PARCIAL],
        }

    parciales = valor_m11.get('semanas_parciales_alcanzables') or []
    if parciales:
        ultima = max(parciales, key=lambda s: s['lunes'])
        estado = 'alcanzó' if ultima['cumplida'] else 'no alcanzó'
        return {
            'texto': f'Semana parcial más reciente ({ultima["lunes"]}–{ultima["domingo"]}): {estado} el objetivo dentro de los días activos.',
            'tipo': TIPO_LECTURA_SEMANA_PARCIAL,
            'etiqueta': _ETIQUETA_POR_TIPO_LECTURA[TIPO_LECTURA_SEMANA_PARCIAL],
        }

    no_evaluables = valor_m11.get('semanas_no_evaluables') or []
    if no_evaluables:
        ultima = max(no_evaluables, key=lambda s: s['lunes'])
        return {
            'texto': f'Semana no evaluable más reciente ({ultima["lunes"]}–{ultima["domingo"]}): el objetivo no era alcanzable con los días activos disponibles.',
            'tipo': TIPO_LECTURA_NO_EVALUABLE,
            'etiqueta': _ETIQUETA_POR_TIPO_LECTURA[TIPO_LECTURA_NO_EVALUABLE],
        }

    return None


def lectura_principal_cultivo(gesto, fecha_referencia):
    """
    Fase 5C: la única lectura visible por hábito tipo='cultivo'. Elige
    la métrica según cadencia, nunca mezcla más de una en el mismo
    texto, y devuelve trazabilidad mínima (periodo + días excluidos)
    junto al texto. 'libre' nunca dice "cumplimiento"; ninguna cadencia
    distinta de 'diaria' habla de racha; nunca se interpreta una
    comparación de dos ventanas como mejora/empeoramiento; nunca se
    infiere causa.
    """
    ventana_desde = fecha_referencia - timedelta(days=13)

    if gesto.tipo_cadencia == Gesto.CADENCIA_LIBRE:
        densidad = az.densidad_sobre_dias_observados_activos(gesto, ventana_desde, fecha_referencia)
        if densidad['confianza'] == 'insuficiente' or densidad['valor'] is None:
            return _lectura_insuficiente()
        apariciones = az.apariciones(gesto, ventana_desde, fecha_referencia)
        porcentaje = round(densidad['valor'] * 100)
        texto = (
            f'Apareció {apariciones["valor"]} veces en los últimos 14 días observados '
            f'({porcentaje}% de esos días).'
        )
        return _lectura_ok(
            texto, TIPO_LECTURA_DESCRIPTIVA, ventana_desde, fecha_referencia,
            apariciones['explicacion'].get('dias_excluidos'),
        )

    if gesto.tipo_cadencia in (Gesto.CADENCIA_DIARIA, Gesto.CADENCIA_DIAS_CONCRETOS):
        resultado = az.adherencia(gesto, fecha_referencia)
        if resultado['confianza'] == 'insuficiente' or resultado['valor'] is None:
            return _lectura_insuficiente()
        m8 = az.oportunidades_previstas(gesto, fecha_referencia)
        m9 = az.oportunidades_cumplidas(gesto, fecha_referencia)
        porcentaje = round(resultado['valor'] * 100)
        texto = (
            f'Adherencia del {porcentaje}% en el periodo evaluado '
            f'({m9["valor"]} de {m8["valor"]} oportunidades).'
        )
        fechas = m8['explicacion'].get('fechas_usadas') or []
        periodo_desde = min(fechas) if fechas else None
        periodo_hasta = max(fechas) if fechas else fecha_referencia
        return _lectura_ok(
            texto, TIPO_LECTURA_CUMPLIMIENTO, periodo_desde, periodo_hasta,
            m8['explicacion'].get('dias_excluidos'),
        )

    if gesto.tipo_cadencia == Gesto.CADENCIA_SEMANAL:
        resultado = az.evaluacion_semanal(gesto, fecha_referencia)
        ventana = az.ventana_cumplimiento(gesto, fecha_referencia)
        periodo_desde, periodo_hasta = ventana if ventana else (None, fecha_referencia)

        if resultado['confianza'] == 'insuficiente' or resultado['valor']['tasa_principal'] is None:
            principal = _lectura_insuficiente()
        else:
            completas = resultado['valor']['semanas_completas']
            cumplidas = resultado['valor']['semanas_cumplidas']
            texto = f'{cumplidas} de {completas} semanas completas cumplieron el objetivo.'
            principal = _lectura_ok(texto, TIPO_LECTURA_CUMPLIMIENTO, periodo_desde, periodo_hasta)

        principal['nota_secundaria'] = _nota_semana_actual(resultado['valor'])
        return principal

    return _lectura_insuficiente()


def _insight_progreso_cultivo(gesto, hoy):
    """Adapta lectura_principal_cultivo() al formato de tarjeta del feed
    de insights_engine — sin tarjeta si no hay lectura útil (silencio,
    no relleno genérico; el "datos insuficientes" explícito es para el
    hueco permanente del dashboard, no para este feed transitorio)."""
    lectura = lectura_principal_cultivo(gesto, hoy)
    if lectura['estado'] != 'ok':
        return None

    return {
        'titulo': f'"{gesto.nombre}"',
        'mensaje': lectura['texto'],
        'tipo': 'info',
        'sugerencia_accion': {
            'texto': 'Ver Dashboard de Gestos',
            'url': reverse('diario:habitos_dashboard'),
        },
    }


def generar_insights_semanales(user):
    """
    Genera una lista de insights y sugerencias de acción basadas en los datos de la última semana.
    """
    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=hoy.weekday() + 7)
    fin_semana = inicio_semana + timedelta(days=6)

    insights = []

    # Obtener datos de la semana
    entradas = ProsocheDiario.objects.filter(
        prosoche_mes__usuario=user,
        fecha__range=[inicio_semana, fin_semana]
    )
    seguimientos = SeguimientoVires.objects.filter(
        usuario=user,
        fecha__range=[inicio_semana, fin_semana]
    )

    if not entradas.exists() and not seguimientos.exists():
        insights.append({
            'titulo': 'Una Semana de Datos',
            'mensaje': 'Has completado otra semana de seguimiento. Cada dato que registras es un paso más hacia el autoconocimiento. Sigue así, el camino del filósofo se construye día a día.',
            'tipo': 'info',
            'sugerencia_accion': {
                'texto': 'Hacer Revisión Semanal',
                'url': reverse('diario:prosoche_revision_semanal')
            }
        })
        return insights

    # --- Insight 1: Correlación Sueño y Energía ---
    if seguimientos.count() >= 3:
        # Días con buen sueño vs mal sueño
        buen_sueno = seguimientos.filter(horas_sueno__gte=7).aggregate(avg_energia=Avg('nivel_energia'))
        mal_sueno = seguimientos.filter(horas_sueno__lt=7).aggregate(avg_energia=Avg('nivel_energia'))

        if buen_sueno['avg_energia'] and mal_sueno['avg_energia'] and buen_sueno['avg_energia'] > mal_sueno[
            'avg_energia']:
            mejora = round(((buen_sueno['avg_energia'] / mal_sueno['avg_energia']) - 1) * 100)
            insights.append({
                'titulo': 'El Descanso es tu Poder',
                'mensaje': f"Análisis de la semana: los días que duermes 7 horas o más, tu nivel de energía promedio es un {mejora}% más alto. El descanso no es tiempo perdido, es una inversión.",
                'tipo': 'success',
                'sugerencia_accion': {
                    'texto': 'Planificar Descanso',
                    'url': reverse('diario:prosoche_revision_semanal')
                }
            })

    # --- Insight 2: Correlación Ánimo y Estrés ---
    if seguimientos.count() >= 3 and entradas.count() >= 3:
        dias_alto_estres = seguimientos.filter(nivel_estres__gte=4).values_list('fecha', flat=True)
        animo_alto_estres = entradas.filter(fecha__in=dias_alto_estres).aggregate(avg_animo=Avg('estado_animo'))
        animo_bajo_estres = entradas.exclude(fecha__in=dias_alto_estres).aggregate(avg_animo=Avg('estado_animo'))

        if animo_alto_estres['avg_animo'] and animo_bajo_estres['avg_animo'] and animo_alto_estres['avg_animo'] < \
                animo_bajo_estres['avg_animo']:
            insights.append({
                'titulo': 'La Fortaleza ante la Tensión',
                'mensaje': 'Hemos observado que en tus días de mayor estrés, tu estado de ánimo tiende a bajar. Recuerda las herramientas estoicas: enfócate en lo que puedes controlar y acepta lo demás.',
                'tipo': 'warning',
                'sugerencia_accion': {
                    'texto': 'Reflexionar sobre el Estrés',
                    'url': reverse('diario:analiticas_personales')
                }
            })

    # --- Insight 3: Progreso de Gestos (Phase 2.0D: Gesto/RegistroGesto) ---
    gestos_activos = Gesto.objects.filter(usuario=user, estado='activo')
    gestos_cultivo = gestos_activos.filter(tipo='cultivo')
    gestos_suelto = gestos_activos.filter(tipo='suelto')

    # Insight para gestos que se cultivan — Fase 5A del
    # CONTRATO_ANALIZADOR_GESTOS.md: fuente única, AnalizadorGestosService.
    # Ya no se calcula nada por cuenta propia. Sin insight si la métrica
    # relevante para la cadencia del gesto tiene confianza insuficiente
    # — mejor ausente que una cifra sin respaldo suficiente.
    for gesto in gestos_cultivo:
        insight = _insight_progreso_cultivo(gesto, hoy)
        if insight:
            insights.append(insight)

    # Insight para gestos que se sueltan con buena racha
    for gesto in gestos_suelto:
        racha = gesto.get_racha_actual()
        if racha >= 7:
            insights.append({
                'titulo': f'¡{racha} Días sin {gesto.nombre}!',
                'mensaje': 'Has demostrado gran fortaleza. Cada día sin este gesto es una victoria.',
                'tipo': 'success',
                'sugerencia_accion': {
                    'texto': 'Ver Dashboard de Gestos',
                    'url': reverse('diario:habitos_dashboard')
                }
            })

    # Si no se generó ningún insight específico, añadir uno genérico
    if not insights:
        insights.append({
            'titulo': 'El Viaje Continúa',
            'mensaje': 'Sigue registrando tus datos para descubrir patrones más profundos. La constancia es la clave de la sabiduría.',
            'tipo': 'info',
            'sugerencia_accion': {
                'texto': 'Ver mi Progreso',
                'url': reverse('diario:analiticas_personales')
            }
        })

    return insights
