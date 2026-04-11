"""
management command: recalcular_carga_ua
========================================
Recalcula carga_ua y duracion_minutos en ActividadRealizada para todas las
sesiones que los tengan a null, usando la mejor fuente disponible.

Fuentes de duración (en orden de prioridad):
  1. EntrenoRealizado.duracion_minutos
  2. SesionEntrenamiento (sesion_detalle).duracion_minutos
  3. EntrenoRealizado.tiempo_total_formateado  (parseo "H:MM:SS" o "Xh Ym")
  4. Default configurable (--default-duracion, por defecto 60 min)

Fuentes de RPE (en orden de prioridad):
  1. ActividadRealizada.rpe_medio (ya calculado desde ejercicios)
  2. SesionEntrenamiento.rpe_medio
  3. Default configurable (--default-rpe, por defecto 5.0 = moderado)

Carga UA:
  carga_ua = rpe × duracion

Uso:
  python manage.py recalcular_carga_ua
  python manage.py recalcular_carga_ua --dry-run
  python manage.py recalcular_carga_ua --solo-null          # solo las que tienen carga_ua null
  python manage.py recalcular_carga_ua --default-duracion 60 --default-rpe 5
"""

from django.core.management.base import BaseCommand
from entrenos.models import ActividadRealizada


def _parse_tiempo_formateado(valor):
    """
    Parsea strings tipo "1:10:23", "70:00", "1h 10m", "90m" → minutos (int).
    Devuelve None si no puede parsear.
    """
    if not valor:
        return None
    valor = str(valor).strip()
    try:
        # Formato "Xh Ym" o "Xh"
        if 'h' in valor or 'm' in valor:
            total = 0
            import re
            h = re.search(r'(\d+)\s*h', valor)
            m = re.search(r'(\d+)\s*m', valor)
            if h:
                total += int(h.group(1)) * 60
            if m:
                total += int(m.group(1))
            return total if total > 0 else None

        # Formato "HH:MM:SS" o "MM:SS"
        partes = [int(p) for p in valor.split(':') if p.strip().isdigit()]
        if len(partes) == 3:
            return partes[0] * 60 + partes[1]   # horas → min, ignorar segundos
        if len(partes) == 2:
            # Puede ser MM:SS o HH:MM — si la primera parte > 9, probablemente MM:SS
            if partes[0] > 9:
                return partes[0]   # ya son minutos
            return partes[0] * 60 + partes[1]
        if len(partes) == 1:
            return partes[0]
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = 'Recalcula carga_ua y duracion_minutos en ActividadRealizada'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra cambios sin guardar nada')
        parser.add_argument('--solo-null', action='store_true',
                            help='Solo procesa registros con carga_ua null')
        parser.add_argument('--default-duracion', type=int, default=60,
                            help='Duración en min a usar si no se encuentra (default: 60)')
        parser.add_argument('--default-rpe', type=float, default=5.0,
                            help='RPE a usar si no se encuentra (default: 5.0)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        solo_null = options['solo_null']
        default_dur = options['default_duracion']
        default_rpe = options['default_rpe']

        qs = ActividadRealizada.objects.select_related(
            'entreno_gym', 'entreno_gym__sesion_detalle'
        ).order_by('fecha')

        if solo_null:
            qs = qs.filter(carga_ua__isnull=True)

        stats = {'procesados': 0, 'actualizados': 0, 'sin_cambio': 0, 'errores': 0}

        for act in qs:
            stats['procesados'] += 1
            try:
                # ── 1. Duración ────────────────────────────────────────────
                duracion = act.duracion_minutos

                if not duracion and act.entreno_gym:
                    gym = act.entreno_gym
                    duracion = gym.duracion_minutos

                if not duracion and act.entreno_gym:
                    det = getattr(act.entreno_gym, 'sesion_detalle', None)
                    if det:
                        duracion = det.duracion_minutos or None

                if not duracion and act.entreno_gym:
                    duracion = _parse_tiempo_formateado(
                        act.entreno_gym.tiempo_total_formateado
                    )

                duracion_usada = duracion or default_dur
                fuente_dur = 'real' if duracion else f'default({default_dur})'

                # ── 2. RPE ─────────────────────────────────────────────────
                rpe = act.rpe_medio

                if not rpe and act.entreno_gym:
                    det = getattr(act.entreno_gym, 'sesion_detalle', None)
                    if det:
                        rpe = det.rpe_medio or None

                rpe_usado = rpe or default_rpe
                fuente_rpe = 'real' if rpe else f'default({default_rpe})'

                # ── 3. Calcular carga UA ───────────────────────────────────
                nueva_carga = round(float(rpe_usado) * duracion_usada, 1)
                nueva_dur = duracion_usada if not act.duracion_minutos else act.duracion_minutos

                cambio = (
                    act.carga_ua != nueva_carga
                    or act.duracion_minutos != nueva_dur
                )

                if not cambio:
                    stats['sin_cambio'] += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f'  [DRY] #{act.id} {act.tipo} {act.fecha} | '
                        f'dur={act.duracion_minutos}→{nueva_dur}({fuente_dur}) '
                        f'rpe={act.rpe_medio}→{rpe_usado}({fuente_rpe}) '
                        f'carga={act.carga_ua}→{nueva_carga}'
                    )
                else:
                    act.carga_ua = nueva_carga
                    if not act.duracion_minutos:
                        act.duracion_minutos = nueva_dur
                    act.save(update_fields=['carga_ua', 'duracion_minutos'])

                stats['actualizados'] += 1

            except Exception as e:
                stats['errores'] += 1
                self.stdout.write(self.style.ERROR(f'  Error #{act.id}: {e}'))

        prefijo = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{prefijo}Procesados: {stats["procesados"]} | '
            f'Actualizados: {stats["actualizados"]} | '
            f'Sin cambio: {stats["sin_cambio"]} | '
            f'Errores: {stats["errores"]}'
        ))
