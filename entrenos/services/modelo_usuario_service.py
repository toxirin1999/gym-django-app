"""
Modelo del Usuario — Capa 3 del sistema proactivo.

Construye un perfil progresivo del atleta desde todos los datos disponibles:
- Umbral técnico: en qué % del RM y en qué serie número falla la técnica
- Patrón semanal: qué días son de mayor energía/rendimiento
- Ventana de recuperación: 48h vs 72h entre sesiones
- Grupos rápidos/lentos: qué grupos musculares progresan y cuáles se estancan
- Calibración RPE: sesgo detectado vs frecuencia cardíaca real

Solo se reportan observaciones con datos suficientes (umbral de confianza).
"""
from datetime import date, timedelta
from collections import defaultdict

_DIA_NOMBRES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_MIN_SESIONES_CONFIANZA = 5   # mínimo para reportar un patrón


def get_modelo_usuario(cliente, hoy=None):
    """
    Retorna un dict con todas las observaciones aprendidas del atleta.
    Cada sección incluye 'confianza' (alta/media/baja) y 'n_datos'.
    """
    if hoy is None:
        hoy = date.today()

    modelo = {
        'rpe_calibracion':       _get_rpe_calibracion(cliente),
        'umbral_tecnico':        _get_umbral_tecnico(cliente, hoy),
        'serie_critica_global':  _get_serie_critica_global(cliente, hoy),
        'patron_semanal':        _get_patron_semanal(cliente, hoy),
        'ventana_recuperacion':  _get_ventana_recuperacion(cliente, hoy),
        'grupos_musculares':     _get_grupos_musculares(cliente, hoy),
        'ejercicios_emblema':    _get_ejercicios_emblema(cliente, hoy),
        'hrv_patron':            _get_hrv_patron(cliente, hoy),
        'tiene_datos':           False,
    }

    modelo['tiene_datos'] = any([
        modelo['rpe_calibracion'],
        modelo['umbral_tecnico'],
        modelo['serie_critica_global'],
        modelo['patron_semanal'],
        modelo['ventana_recuperacion'],
        modelo['grupos_musculares']['rapidos'] or modelo['grupos_musculares']['lentos'],
        modelo['ejercicios_emblema'],
        modelo['hrv_patron'],
    ])

    return modelo


# ── Helpers privados ──────────────────────────────────────────────────────────

def _get_rpe_calibracion(cliente):
    try:
        from hyrox.models import HyroxObjective
        from hyrox.training_engine import RPECalibrator
        obj = HyroxObjective.objects.filter(cliente=cliente, estado='activo').first()
        if not obj:
            return None
        info = RPECalibrator.get_bias(obj)
        if info['nivel'] == 'insuficiente':
            return None
        return {
            'bias': round(info['bias'], 1),
            'nivel': info['nivel'],
            'direccion': 'sobreestima' if info['bias'] > 0 else 'subestima',
            'descripcion': (
                f"{'Sobreestimas' if info['bias'] > 0 else 'Subestimas'} el esfuerzo "
                f"en ~{abs(info['bias']):.1f} puntos. El plan ajusta los umbrales automáticamente."
            ),
        }
    except Exception:
        return None


def _get_umbral_tecnico(cliente, hoy):
    """
    Para cada ejercicio con ≥3 fallos de técnica, calcula el % de RM medio
    en que aparece la técnica comprometida y en qué serie.
    """
    try:
        from entrenos.models import SerieRealizada
        from django.db.models import Avg
        hace_90 = hoy - timedelta(days=90)

        series_malas = list(
            SerieRealizada.objects
            .filter(entreno__cliente=cliente, tecnica_calidad='comprometida',
                    entreno__fecha__gte=hace_90, peso_kg__isnull=False)
            .select_related('ejercicio', 'entreno')
        )

        if not series_malas:
            return []

        # Agrupar por ejercicio
        por_ejercicio = defaultdict(list)
        for s in series_malas:
            por_ejercicio[s.ejercicio.nombre].append(s)

        umbral_tecnico = []
        for nombre, series in por_ejercicio.items():
            if len(series) < 3:
                continue
            # Peso medio en que falla la técnica
            pesos = [float(s.peso_kg) for s in series if s.peso_kg]
            serie_nums = [s.serie_numero for s in series if s.serie_numero]
            if not pesos:
                continue
            peso_fallo_medio = sum(pesos) / len(pesos)
            serie_critica = round(sum(serie_nums) / len(serie_nums)) if serie_nums else None

            # RM conocido para calcular el %
            rm = _get_rm_ejercicio(cliente, nombre)
            pct_rm = round(peso_fallo_medio / rm * 100) if rm else None

            umbral_tecnico.append({
                'ejercicio': nombre,
                'peso_fallo_medio': round(peso_fallo_medio, 1),
                'pct_rm': pct_rm,
                'serie_critica': serie_critica,
                'n_datos': len(series),
                'descripcion': _describir_umbral(nombre, pct_rm, serie_critica),
            })

        umbral_tecnico.sort(key=lambda x: -x['n_datos'])
        return umbral_tecnico[:4]
    except Exception:
        return []


def _get_rm_ejercicio(cliente, nombre):
    """Obtiene el RM conocido de un ejercicio desde one_rm_data o RecordPersonal."""
    try:
        one_rm = cliente.one_rm_data or {}
        nl = nombre.lower()
        for k, v in one_rm.items():
            if k.lower() in nl or nl in k.lower():
                return float(v)
    except Exception:
        pass
    try:
        from entrenos.models import RecordPersonal
        pr = (RecordPersonal.objects
              .filter(cliente=cliente, ejercicio_nombre__icontains=nombre,
                      tipo_record='peso_maximo', superado=False)
              .order_by('-valor').first())
        if pr:
            return float(pr.valor)
    except Exception:
        pass
    return None


def _describir_umbral(nombre, pct_rm, serie_critica):
    parts = []
    if pct_rm:
        parts.append(f"la técnica cede a partir del {pct_rm}% del RM")
    if serie_critica:
        parts.append(f"suele ocurrir en la serie {serie_critica}")
    return f"{nombre}: {', '.join(parts)}." if parts else f"{nombre}: patrón de fallo detectado."


def _get_serie_critica_global(cliente, hoy):
    """
    Serie número más común en la que aparece técnica comprometida (global, todos los ejercicios).
    """
    try:
        from entrenos.models import SerieRealizada
        from collections import Counter
        hace_90 = hoy - timedelta(days=90)

        series_nums = list(
            SerieRealizada.objects
            .filter(entreno__cliente=cliente, tecnica_calidad='comprometida',
                    entreno__fecha__gte=hace_90)
            .values_list('serie_numero', flat=True)
        )

        if len(series_nums) < 6:
            return None

        counter = Counter(series_nums)
        serie_mas_comun, frecuencia = counter.most_common(1)[0]
        pct = round(frecuencia / len(series_nums) * 100)

        if pct < 30:
            return None

        return {
            'serie': serie_mas_comun,
            'pct': pct,
            'n_datos': len(series_nums),
            'descripcion': (
                f"La técnica falla más frecuentemente en la serie {serie_mas_comun} "
                f"({pct}% de los casos). El plan lo usa para limitar el volumen."
            ),
        }
    except Exception:
        return None


def _get_patron_semanal(cliente, hoy):
    """
    Qué día de la semana tiene mayor energía media (BitacoraDiaria).
    Qué día tiene menor RPE medio (EntrenoRealizado).
    """
    try:
        from clientes.models import BitacoraDiaria
        from entrenos.models import EntrenoRealizado
        hace_90 = hoy - timedelta(days=90)

        # Energía por día de la semana
        bitacoras = list(BitacoraDiaria.objects.filter(
            cliente=cliente, fecha__gte=hace_90, nivel_energia__isnull=False
        ).values('fecha', 'nivel_energia'))

        energia_por_dia = defaultdict(list)
        for b in bitacoras:
            dia = b['fecha'].weekday()
            energia_por_dia[dia].append(b['nivel_energia'])

        if not energia_por_dia:
            return None

        # Al menos 3 muestras por día para ser significativo
        medias = {
            dia: sum(vals) / len(vals)
            for dia, vals in energia_por_dia.items()
            if len(vals) >= 3
        }

        if len(medias) < 3:
            return None

        dia_pico = max(medias, key=medias.get)
        dia_valle = min(medias, key=medias.get)

        return {
            'dia_pico': _DIA_NOMBRES[dia_pico],
            'energia_pico': round(medias[dia_pico], 1),
            'dia_valle': _DIA_NOMBRES[dia_valle],
            'energia_valle': round(medias[dia_valle], 1),
            'n_datos': len(bitacoras),
            'descripcion': (
                f"Tu energía es más alta los {_DIA_NOMBRES[dia_pico]} "
                f"(media {round(medias[dia_pico], 1)}/10) y más baja los "
                f"{_DIA_NOMBRES[dia_valle]} ({round(medias[dia_valle], 1)}/10). "
                f"El plan puede priorizar sesiones pesadas los {_DIA_NOMBRES[dia_pico]}."
            ),
        }
    except Exception:
        return None


def _get_ventana_recuperacion(cliente, hoy):
    """
    ¿Con cuántos días de descanso llega el usuario con mejor RPE?
    Usa el RPE medio por sesión calculado desde EjercicioRealizado.
    """
    try:
        from entrenos.models import EntrenoRealizado, EjercicioRealizado
        from django.db.models import Avg
        hace_120 = hoy - timedelta(days=120)

        entrenos = list(
            EntrenoRealizado.objects
            .filter(cliente=cliente, fecha__gte=hace_120)
            .order_by('fecha')
            .values('id', 'fecha')
        )

        if len(entrenos) < _MIN_SESIONES_CONFIANZA:
            return None

        # Calcular RPE medio por sesión desde EjercicioRealizado
        rpe_por_sesion = {}
        for e in entrenos:
            agg = EjercicioRealizado.objects.filter(
                entreno_id=e['id'], rpe__isnull=False
            ).aggregate(media=Avg('rpe'))
            if agg['media']:
                rpe_por_sesion[e['id']] = (e['fecha'], round(agg['media'], 1))

        sesiones_con_rpe = sorted(rpe_por_sesion.values(), key=lambda x: x[0])

        if len(sesiones_con_rpe) < _MIN_SESIONES_CONFIANZA:
            return None

        intervalos_rpe = defaultdict(list)
        for i in range(1, len(sesiones_con_rpe)):
            dias = (sesiones_con_rpe[i][0] - sesiones_con_rpe[i-1][0]).days
            if 1 <= dias <= 5:
                intervalos_rpe[dias].append(sesiones_con_rpe[i][1])

        if len(intervalos_rpe) < 2:
            return None

        medias = {dias: sum(v)/len(v) for dias, v in intervalos_rpe.items() if len(v) >= 2}
        if len(medias) < 2:
            return None

        dias_optimo = min(medias, key=medias.get)

        return {
            'dias_optimos': dias_optimo,
            'rpe_con_optimo': round(medias[dias_optimo], 1),
            'n_datos': sum(len(v) for v in intervalos_rpe.values()),
            'descripcion': (
                f"Rindes mejor con {dias_optimo} días de descanso entre sesiones "
                f"(RPE medio {round(medias[dias_optimo], 1)} vs días adyacentes). "
                f"El plan respeta esta ventana cuando puede."
            ),
        }
    except Exception:
        return None


def _get_grupos_musculares(cliente, hoy):
    """
    Qué grupos musculares progresan más rápido (>5% en 90 días)
    y cuáles se estancan (GymDecisionLog cambiar_variante / Sin progresión).
    """
    resultado = {'rapidos': [], 'lentos': [], 'descripcion': ''}

    try:
        from entrenos.models import EjercicioRealizado, GymDecisionLog
        from django.db.models import Max
        hace_90 = hoy - timedelta(days=90)
        hace_180 = hoy - timedelta(days=180)

        # Grupos con progresión en peso
        nombres = list(
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, entreno__fecha__gte=hace_90, peso_kg__gt=0)
            .values_list('nombre_ejercicio', flat=True).distinct()
        )

        progresion_por_grupo = defaultdict(list)
        for nombre in nombres[:20]:
            qs = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente, nombre_ejercicio=nombre, peso_kg__gt=0)
            ahora = qs.filter(entreno__fecha__range=(hace_90, hoy)).aggregate(mx=Max('peso_kg'))['mx']
            antes  = qs.filter(entreno__fecha__range=(hace_180, hace_90)).aggregate(mx=Max('peso_kg'))['mx']
            if ahora and antes and float(antes) > 0:
                pct = (float(ahora) - float(antes)) / float(antes) * 100
                grupo = _inferir_grupo(nombre)
                if grupo:
                    progresion_por_grupo[grupo].append(pct)

        for grupo, pcts in progresion_por_grupo.items():
            media = sum(pcts) / len(pcts)
            if media >= 5:
                resultado['rapidos'].append({'grupo': grupo, 'pct': round(media, 1)})
            elif media < 0:
                resultado['lentos'].append({'grupo': grupo, 'pct': round(media, 1)})

        resultado['rapidos'].sort(key=lambda x: -x['pct'])
        resultado['lentos'].sort(key=lambda x: x['pct'])

        partes = []
        if resultado['rapidos']:
            gs = ', '.join(g['grupo'] for g in resultado['rapidos'][:2])
            partes.append(f"{gs} en progresión")
        if resultado['lentos']:
            gs = ', '.join(g['grupo'] for g in resultado['lentos'][:2])
            partes.append(f"{gs} estancado")
        resultado['descripcion'] = '. '.join(partes) + '.' if partes else ''

    except Exception:
        pass

    return resultado


_GRUPO_KEYWORDS = {
    'Pecho':    ['pecho', 'banca', 'press inclinado', 'aperturas', 'dips'],
    'Espalda':  ['espalda', 'jalón', 'remo', 'dominada', 'pull'],
    'Piernas':  ['sentadilla', 'prensa', 'peso muerto', 'femoral', 'zancada', 'hip thrust'],
    'Hombros':  ['press militar', 'elevacion', 'elevación', 'hombro', 'arnold'],
    'Bíceps':   ['curl'],
    'Tríceps':  ['trícep', 'tricep', 'fondos', 'extensión de trícep'],
}


def _inferir_grupo(nombre):
    nl = nombre.lower()
    for grupo, kws in _GRUPO_KEYWORDS.items():
        if any(kw in nl for kw in kws):
            return grupo
    return None


def _get_ejercicios_emblema(cliente, hoy):
    """
    Top 3 ejercicios donde el usuario ha progresado más en los últimos 90 días.
    """
    try:
        from entrenos.models import EjercicioRealizado
        from django.db.models import Max
        hace_90 = hoy - timedelta(days=90)
        hace_180 = hoy - timedelta(days=180)

        nombres = list(
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, entreno__fecha__gte=hace_90, peso_kg__gt=0)
            .values_list('nombre_ejercicio', flat=True).distinct()
        )

        mejoras = []
        for nombre in nombres[:20]:
            qs = EjercicioRealizado.objects.filter(
                entreno__cliente=cliente, nombre_ejercicio=nombre, peso_kg__gt=0)
            ahora = qs.filter(entreno__fecha__range=(hace_90, hoy)).aggregate(mx=Max('peso_kg'))['mx']
            antes  = qs.filter(entreno__fecha__range=(hace_180, hace_90)).aggregate(mx=Max('peso_kg'))['mx']
            if ahora and antes and float(antes) > 0:
                pct = (float(ahora) - float(antes)) / float(antes) * 100
                if pct >= 3:
                    mejoras.append({
                        'ejercicio': nombre,
                        'peso_antes': float(antes),
                        'peso_ahora': float(ahora),
                        'pct': round(pct, 1),
                    })

        mejoras.sort(key=lambda x: -x['pct'])
        return mejoras[:3]
    except Exception:
        return []


def _get_hrv_patron(cliente, hoy):
    """
    Si hay datos HRV: qué HRV correlaciona con buen rendimiento (RPE bajo post-sesión).
    """
    try:
        from clientes.models import BitacoraDiaria
        from entrenos.models import EntrenoRealizado
        hace_60 = hoy - timedelta(days=60)

        bitacoras = {
            b.fecha: b.hrv_ms
            for b in BitacoraDiaria.objects.filter(
                cliente=cliente, fecha__gte=hace_60, hrv_ms__isnull=False
            )
        }

        if len(bitacoras) < 7:
            return None

        from entrenos.models import EntrenoRealizado, EjercicioRealizado
        from django.db.models import Avg

        entrenos = list(
            EntrenoRealizado.objects
            .filter(cliente=cliente, fecha__gte=hace_60)
            .values('id', 'fecha')
        )

        pares = []
        for e in entrenos:
            hrv = bitacoras.get(e['fecha'])
            if not hrv:
                continue
            agg = EjercicioRealizado.objects.filter(
                entreno_id=e['id'], rpe__isnull=False
            ).aggregate(media=Avg('rpe'))
            if agg['media']:
                pares.append((hrv, round(agg['media'], 1)))

        if len(pares) < 5:
            return None

        hrv_alto = [p for p in pares if p[0] >= 50]
        hrv_bajo  = [p for p in pares if p[0] < 50]

        if not hrv_alto or not hrv_bajo:
            return None

        rpe_hrv_alto = sum(p[1] for p in hrv_alto) / len(hrv_alto)
        rpe_hrv_bajo  = sum(p[1] for p in hrv_bajo)  / len(hrv_bajo)
        hrv_medio = round(sum(b for b in bitacoras.values()) / len(bitacoras))

        return {
            'hrv_medio': hrv_medio,
            'rpe_hrv_alto': round(rpe_hrv_alto, 1),
            'rpe_hrv_bajo': round(rpe_hrv_bajo, 1),
            'n_datos': len(pares),
            'descripcion': (
                f"Con HRV ≥50ms tu RPE post-sesión baja a {round(rpe_hrv_alto, 1)} de media. "
                f"Con HRV bajo sube a {round(rpe_hrv_bajo, 1)}. "
                f"Tu HRV medio es {hrv_medio}ms."
            ),
        }
    except Exception:
        return None
