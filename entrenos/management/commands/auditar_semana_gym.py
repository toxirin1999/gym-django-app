import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from clientes.models import BitacoraDiaria, Cliente
from entrenos.models import ActividadRealizada, GymDecisionVersion
from hyrox.models import StravaActivityRaw


class Command(BaseCommand):
    help = (
        'Audita una ventana semanal Gym en JSON Lines. '
        'Es estrictamente de solo lectura.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cliente', type=int, required=True)
        parser.add_argument('--desde', required=True, help='Fecha inicial inclusiva, YYYY-MM-DD')
        parser.add_argument('--hasta', required=True, help='Fecha final inclusiva, YYYY-MM-DD')

    def handle(self, *args, **options):
        cliente_id = options['cliente']
        desde = self._fecha(options['desde'], '--desde')
        hasta = self._fecha(options['hasta'], '--hasta')
        if desde > hasta:
            raise CommandError('--desde no puede ser posterior a --hasta')
        if (hasta - desde).days > 62:
            raise CommandError('La ventana máxima de auditoría es de 63 días')
        if not Cliente.objects.filter(pk=cliente_id).exists():
            raise CommandError(f'No existe Cliente con id={cliente_id}')

        decisiones = list(
            GymDecisionVersion.objects
            .filter(cliente_id=cliente_id, fecha__range=(desde, hasta))
            .order_by('fecha', 'version')
        )
        actividades = list(
            ActividadRealizada.objects
            .filter(cliente_id=cliente_id)
            .filter(
                Q(fecha__range=(desde, hasta))
                | Q(fecha_realizado__range=(desde, hasta))
            )
            .order_by('fecha', 'id')
        )
        checkins = list(
            BitacoraDiaria.objects
            .filter(cliente_id=cliente_id, fecha__range=(desde, hasta))
            .order_by('fecha', 'id')
        )
        strava = list(
            StravaActivityRaw.objects
            .filter(cliente_id=cliente_id, fecha_actividad__range=(desde, hasta))
            .order_by('fecha_actividad', 'id')
        )

        self._emitir(
            'ventana',
            schema_version=1,
            cliente_id=cliente_id,
            desde=desde,
            hasta=hasta,
            dias=(hasta - desde).days + 1,
            solo_lectura=True,
        )

        for decision in decisiones:
            self._emitir(
                'decision',
                fecha=decision.fecha,
                version=decision.version,
                decision_id=decision.decision_id,
                origen=decision.origen,
                vigente=decision.vigente,
                postura=decision.postura,
                causa_principal=decision.causa_principal or None,
                motivo_correccion=decision.motivo_correccion or None,
                reemplaza_version=(decision.reemplaza.version if decision.reemplaza_id else None),
            )

        sesiones_gym = [actividad for actividad in actividades if actividad.tipo == 'gym']
        externas = [actividad for actividad in actividades if actividad.tipo != 'gym']
        for sesion in sesiones_gym:
            self._emitir(
                'sesion_gym',
                id=sesion.id,
                fecha_planificada=sesion.fecha,
                fecha_realizada=sesion.fecha_realizado or sesion.fecha,
                titulo=sesion.titulo or None,
                fuente=sesion.fuente,
                duracion_minutos=sesion.duracion_minutos,
                rpe=sesion.rpe_medio,
                carga_ua=sesion.carga_ua,
                volumen_kg=sesion.volumen_kg,
                tiene_entreno_enlazado=bool(sesion.entreno_gym_id),
            )

        for checkin in checkins:
            self._emitir(
                'checkin',
                id=checkin.id,
                fecha=checkin.fecha,
                horas_sueno=checkin.horas_sueno,
                calidad_sueno=checkin.calidad_sueno,
                hrv_ms=checkin.hrv_ms,
                fc_reposo=checkin.fc_reposo,
                energia=checkin.energia_subjetiva,
                dolor_articular=checkin.dolor_articular,
            )

        for actividad in externas:
            self._emitir(
                'carga_externa',
                id=actividad.id,
                fecha=actividad.fecha_realizado or actividad.fecha,
                tipo=actividad.tipo,
                titulo=actividad.titulo or None,
                fuente=actividad.fuente,
                duracion_minutos=actividad.duracion_minutos,
                rpe=actividad.rpe_medio,
                carga_ua=actividad.carga_ua,
                hr_media=actividad.hr_media,
                hr_maxima=actividad.hr_maxima,
            )

        for evidencia in strava:
            self._emitir(
                'evidencia_strava',
                id=evidencia.id,
                fecha=evidencia.fecha_actividad,
                tipo_strava=evidencia.tipo_strava,
                estado=evidencia.estado,
                duracion_minutos=evidencia.duracion_minutos(),
                hr_media=evidencia.hr_media,
                hr_maxima=evidencia.hr_maxima,
                fusionada_gym=bool(evidencia.entreno_gym_id),
                fusionada_hyrox=bool(evidencia.hyrox_session_id),
            )

        dias_con_datos = {d.fecha for d in decisiones}
        dias_con_datos.update(c.fecha for c in checkins)
        for actividad in actividades:
            dias_con_datos.add(actividad.fecha)
            if actividad.fecha_realizado:
                dias_con_datos.add(actividad.fecha_realizado)
        dias_con_datos.update(e.fecha_actividad for e in strava)

        self._emitir(
            'resumen',
            cliente_id=cliente_id,
            desde=desde,
            hasta=hasta,
            dias_con_datos=len(dias_con_datos),
            versiones_decision=len(decisiones),
            dias_con_decision=len({d.fecha for d in decisiones}),
            correcciones=sum(d.origen == GymDecisionVersion.ORIGEN_CORRECCION for d in decisiones),
            reversiones=sum(d.origen == GymDecisionVersion.ORIGEN_REVERSION for d in decisiones),
            sesiones_gym=len(sesiones_gym),
            sesiones_gym_sin_rpe=sum(s.rpe_medio is None for s in sesiones_gym),
            sesiones_gym_sin_duracion=sum(s.duracion_minutos is None for s in sesiones_gym),
            actividades_externas=len(externas),
            carga_externa_ua=round(sum(float(a.carga_ua or 0) for a in externas), 1),
            checkins=len(checkins),
            checkins_con_hrv=sum(c.hrv_ms is not None for c in checkins),
            checkins_con_fc_reposo=sum(c.fc_reposo is not None for c in checkins),
            checkins_con_sueno=sum(c.horas_sueno is not None for c in checkins),
            evidencias_strava=len(strava),
            solo_lectura=True,
        )

    @staticmethod
    def _fecha(valor, nombre):
        try:
            return date.fromisoformat(valor)
        except (TypeError, ValueError) as exc:
            raise CommandError(f'{nombre} debe usar el formato YYYY-MM-DD') from exc

    def _emitir(self, tipo_registro, **datos):
        payload = {'tipo_registro': tipo_registro, **datos}
        self.stdout.write(json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            default=self._json_default,
        ))

    @staticmethod
    def _json_default(valor):
        if isinstance(valor, date):
            return valor.isoformat()
        return float(valor)
