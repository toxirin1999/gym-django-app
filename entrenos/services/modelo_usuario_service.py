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
              .filter(cliente=cliente, ejercicio_nombre__iexact=nombre,
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
    Posición de serie en la que la técnica cede con más frecuencia (90 días).

    Se compara la TASA de series comprometidas en cada posición (comprometidas
    en la serie N / series hechas en la posición N), no el recuento bruto: casi
    todos los ejercicios tienen serie 1, así que contar apariciones señalaba
    siempre la S1. Las aproximaciones no son series de trabajo y se excluyen.
    """
    try:
        from collections import Counter
        from entrenos.models import SerieRealizada
        hace_90 = hoy - timedelta(days=90)

        filas = list(
            SerieRealizada.objects
            .filter(entreno__cliente=cliente, entreno__fecha__gte=hace_90, es_aproximacion=False)
            .exclude(tecnica_calidad__isnull=True).exclude(tecnica_calidad='')
            .values_list('serie_numero', 'tecnica_calidad')
        )
        total = Counter(n for n, _ in filas)
        malas = Counter(n for n, calidad in filas if calidad == 'comprometida')
        n_malas = sum(malas.values())
        if n_malas < 6:
            return None

        tasa_global = n_malas / len(filas)
        candidatas = {
            n: malas[n] / total[n]
            for n in malas
            if malas[n] >= 3 and total[n] >= 5
        }
        if not candidatas:
            return None
        serie, tasa = max(candidatas.items(), key=lambda kv: (kv[1], kv[0]))
        # Solo es "crítica" si destaca sobre el resto de posiciones.
        if tasa < tasa_global * 1.3:
            return None

        pct = round(tasa * 100)
        pct_global = round(tasa_global * 100)
        return {
            'serie': serie,
            'pct': pct,
            'pct_global': pct_global,
            'n_datos': n_malas,
            'descripcion': (
                f"La técnica cede en el {pct} % de tus series {serie}, "
                f"frente al {pct_global} % de media. El plan lo usa para limitar el volumen."
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
                f"(media {str(round(medias[dia_pico], 1)).replace('.', ',')}/10) y más baja los "
                f"{_DIA_NOMBRES[dia_valle]} ({str(round(medias[dia_valle], 1)).replace('.', ',')}/10). "
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
        etiqueta_dia = 'día' if dias_optimo == 1 else 'días'

        return {
            'dias_optimos': dias_optimo,
            'rpe_con_optimo': round(medias[dias_optimo], 1),
            'n_datos': sum(len(v) for v in intervalos_rpe.values()),
            'descripcion': (
                f"Rindes mejor con {dias_optimo} {etiqueta_dia} de descanso entre sesiones "
                f"(RPE medio {str(round(medias[dias_optimo], 1)).replace('.', ',')} vs días adyacentes). "
                f"El plan respeta esta ventana cuando puede."
            ),
        }
    except Exception:
        return None


def _get_grupos_musculares(cliente, hoy):
    """
    Qué grupos musculares progresan más rápido (>=5 % en 90 días)
    y cuáles retroceden. Se apoya en ``calcular_evolucion_por_grupo``
    (todos los ejercicios, e1RM, grupo registrado normalizado).
    """
    resultado = {'rapidos': [], 'lentos': [], 'descripcion': ''}

    try:
        from entrenos.services.evolucion_muscular_service import calcular_evolucion_por_grupo
        evolucion = calcular_evolucion_por_grupo(cliente, hoy=hoy, dias=90)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('No se pudo calcular la evolución por grupo')
        return resultado

    for g in evolucion['grupos']:
        if g['pct'] is None:
            continue
        if g['pct'] >= 5:
            resultado['rapidos'].append({'grupo': g['nombre'], 'pct': g['pct']})
        elif g['pct'] < 0:
            resultado['lentos'].append({'grupo': g['nombre'], 'pct': g['pct']})

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

    return resultado


def _get_ejercicios_emblema(cliente, hoy):
    """
    Top 3 ejercicios con más progreso en 90 días frente a los 90 anteriores.

    Usa la misma comparación que el mapa de evolución muscular: e1RM de la
    mejor serie de trabajo real, sin aproximaciones, y fuera los datos dudosos
    (> ±60 %) y los accesorios ligeros, que daban "+200 %" sin sentido.
    """
    try:
        from entrenos.services.evolucion_muscular_service import comparar_ejercicios

        mejoras = []
        for e in comparar_ejercicios(cliente, hoy, dias=90):
            if e['pct'] is None or e['dudoso'] or e['ligero'] or e['pct'] < 3:
                continue
            mejoras.append({
                'ejercicio': e['ejercicio'],
                'peso_antes': e['antes']['peso_kg'],
                'reps_antes': e['antes']['reps'],
                'peso_ahora': e['ahora']['peso_kg'],
                'reps_ahora': e['ahora']['reps'],
                'pct': round(e['pct'], 1),
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

        # Umbral personalizado: media del propio usuario (no fijo a 50ms)
        hrv_alto = [p for p in pares if p[0] >= hrv_medio]
        hrv_bajo  = [p for p in pares if p[0] < hrv_medio]

        if not hrv_alto or not hrv_bajo:
            return None

        rpe_hrv_alto = sum(p[1] for p in hrv_alto) / len(hrv_alto)
        rpe_hrv_bajo  = sum(p[1] for p in hrv_bajo)  / len(hrv_bajo)

        return {
            'hrv_medio': hrv_medio,
            'rpe_hrv_alto': round(rpe_hrv_alto, 1),
            'rpe_hrv_bajo': round(rpe_hrv_bajo, 1),
            'n_datos': len(pares),
            'descripcion': (
                f"Con HRV ≥{hrv_medio}ms (tu media) el RPE post-sesión baja a {str(round(rpe_hrv_alto, 1)).replace('.', ',')}. "
                f"Con HRV bajo sube a {str(round(rpe_hrv_bajo, 1)).replace('.', ',')}. "
                f"Tu HRV medio es {hrv_medio}ms."
            ),
        }
    except Exception:
        return None
