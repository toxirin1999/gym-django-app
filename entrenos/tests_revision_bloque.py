"""Revisión de bloque sobre la periodización (14-oct-2026)."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym, EntrenoRealizado, EstrategiaSemanalGym, GymDecisionLog, SemanaPlanGym,
)
from entrenos.services.revision_bloque_service import estado_bloques, revision_ultimo_bloque
from rutinas.models import Rutina

LUNES = date(2026, 1, 5)  # lunes


def grupo(zona, nombre, pct, estado):
    return {'zona': zona, 'nombre': nombre, 'pct': pct, 'estado': estado}


def evolucion_falsa(cliente, hoy=None, dias=90):
    """Isquios caía antes del bloque y se recupera; gemelos sube durante el bloque."""
    if dias == 90 and hoy < LUNES:
        grupos = [grupo('isquios', 'Isquios', -17.0, 'retrocede'), grupo('gemelos', 'Gemelos', 20.0, 'progresa')]
    elif dias == 90:
        grupos = [grupo('isquios', 'Isquios', 3.0, 'estable'), grupo('gemelos', 'Gemelos', 25.0, 'progresa')]
    else:
        grupos = [grupo('gemelos', 'Gemelos', 12.0, 'progresa'), grupo('triceps', 'Tríceps', -6.0, 'retrocede')]
    con = [g['pct'] for g in grupos]
    return {'grupos': grupos, 'media_pct': round(sum(con) / len(con), 1)}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='revbloque', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'R'})
        self.cliente.dias_disponibles = 4
        self.cliente.save(update_fields=['dias_disponibles'])
        self.addCleanup(cache.clear)

    def semanas(self, numeros, descargas=()):
        for i, n in enumerate(numeros):
            SemanaPlanGym.objects.create(
                cliente=self.cliente, lunes=LUNES + timedelta(weeks=i), semana_plan=n,
                descarga=n in descargas, origen=SemanaPlanGym.ORIGEN_AVANCE,
            )


class EstadoDeBloques(Base):
    def test_bloque_en_curso(self):
        self.semanas([1, 2, 3])
        estado = estado_bloques(self.cliente, hoy=LUNES + timedelta(weeks=2, days=2))
        self.assertIsNone(estado['ultimo_cerrado'])
        self.assertEqual(estado['en_curso']['nombre'], 'Hipertrofia — Acumulación')
        self.assertEqual((estado['en_curso']['semana'], estado['en_curso']['de']), (3, 7))

    def test_se_cierra_al_entrar_en_la_descarga(self):
        self.semanas([1, 2, 3, 4, 5, 6, 7, 8], descargas=(8,))
        estado = estado_bloques(self.cliente, hoy=LUNES + timedelta(weeks=7, days=1))
        self.assertEqual(estado['ultimo_cerrado']['bloque']['nombre'], 'Hipertrofia — Acumulación')
        self.assertEqual(estado['ultimo_cerrado']['semanas_reales'], 7)
        self.assertIsNone(estado['en_curso'])

    def test_una_descarga_intercalada_no_parte_el_bloque(self):
        self.semanas([1, 2, 3, 3, 4], descargas=())
        SemanaPlanGym.objects.filter(cliente=self.cliente, lunes=LUNES + timedelta(weeks=3)).update(descarga=True)
        estado = estado_bloques(self.cliente, hoy=LUNES + timedelta(weeks=4, days=1))
        self.assertIsNone(estado['ultimo_cerrado'])
        self.assertEqual(estado['en_curso']['nombre'], 'Hipertrofia — Acumulación')


class Revision(Base):
    def test_revision_con_el_dato(self):
        self.semanas([1, 2, 3, 4, 5, 6, 7, 8], descargas=(8,))
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        for i in range(20):  # 20 de 28 previstas
            EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=LUNES + timedelta(days=i))
        from datetime import datetime
        from django.utils import timezone as tz
        evaluada = tz.make_aware(datetime(2026, 1, 20, 12, 0))
        for i, res in enumerate(('validada', 'validada', 'fallida')):
            GymDecisionLog.objects.create(
                cliente=self.cliente, ejercicio=f'x{i}', ejercicio_normalizado=f'x{i}', accion='subir_peso',
                motivo='x', resultado=res, fecha_evaluacion=evaluada,
            )
        hoy = LUNES + timedelta(weeks=7, days=1)
        with patch('entrenos.services.evolucion_muscular_service.calcular_evolucion_por_grupo',
                   side_effect=evolucion_falsa):
            r = revision_ultimo_bloque(self.cliente, hoy=hoy)['revision']
        self.assertEqual(r['nombre'], 'Hipertrofia — Acumulación')
        self.assertEqual(r['sesiones'], {'hechas': 20, 'previstas': 28, 'pct': 71})
        self.assertEqual(r['suben'], ['Gemelos +12 %'])
        self.assertEqual(r['bajan'], ['Tríceps -6 %'])
        self.assertEqual(r['equilibrar'][0]['texto'], 'Isquios: -17 % al empezar → +3 % al acabar · recuperada')
        self.assertIn('tríceps', r['cambia'])
        self.assertEqual(r['decisiones'], {'funcionaron': 2, 'total': 3})


class AcuerdosVencidos(Base):
    def contrato(self, fin, version):
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=version, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=fin - timedelta(days=27),
        )
        return ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=version, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            estrategia=estrategia, limites_snapshot={}, fingerprint=str(version) * 64,
            semana_inicio=fin - timedelta(days=27), semanas_previstas=4,
            semana_fin_prevista=fin, objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='hipertrofia', objetivos_secundarios=['gemelos'],
            motor_nombre='Helms', motor_version='x',
        )

    def test_se_cierra_un_acuerdo_vencido_hace_semanas(self):
        from entrenos.services.contrato_bloque_gym_service import finalizar_bloques_vencidos
        hoy = date(2026, 10, 14)
        viejo = self.contrato(date(2026, 9, 20), 1)
        self.assertEqual(finalizar_bloques_vencidos(self.cliente, hoy=hoy), 1)
        viejo.refresh_from_db()
        self.assertEqual(viejo.estado, ContratoBloqueGym.ESTADO_FINALIZADO)

    def test_respeta_la_semana_de_gracia(self):
        from entrenos.services.contrato_bloque_gym_service import finalizar_bloques_vencidos
        reciente = self.contrato(date(2026, 10, 10), 2)
        self.assertEqual(finalizar_bloques_vencidos(self.cliente, hoy=date(2026, 10, 14)), 0)
        reciente.refresh_from_db()
        self.assertEqual(reciente.estado, ContratoBloqueGym.ESTADO_ACTIVO)


class CentroProximaSesion(Base):
    def test_sin_sesiones_programadas_usa_la_cola(self):
        from entrenos.services.centro_decisiones_service import _proxima_desde_cola
        hoy = date(2026, 10, 14)
        siguiente = {'nombre': 'Dia 2 - Hipertrofia', 'fecha': hoy - timedelta(days=1)}
        with patch('entrenos.services.sesion_recomendada._siguiente_de_cola', return_value=siguiente):
            p = _proxima_desde_cola(self.cliente, hoy)
        self.assertEqual(p, {'estado': 'disponible', 'nombre': 'Dia 2 - Hipertrofia', 'fecha': hoy, 'es_pospuesta': True})


class MemoriaMuestraElBloque(Base):
    def test_bloque_en_curso_en_memoria(self):
        from django.urls import reverse
        from django.utils import timezone
        from entrenos.services.periodizacion_dinamica_service import lunes_de
        SemanaPlanGym.objects.create(
            cliente=self.cliente, lunes=lunes_de(timezone.localdate()), semana_plan=2,
            origen=SemanaPlanGym.ORIGEN_CALENDARIO,
        )
        self.client.force_login(self.cliente.user)
        r = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertContains(r, 'Bloque en curso: <strong>Hipertrofia — Acumulación</strong> · semana 2 de 7')


class CierreAlGuardarSesion(Base):
    def test_cerrar_aprendizaje_cierra_acuerdos_vencidos(self):
        from django.utils import timezone
        from entrenos.services.decision_log_service import cerrar_aprendizaje_gym
        hoy = timezone.localdate()
        estrategia = EstrategiaSemanalGym.objects.create(
            cliente=self.cliente, version=1, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=hoy - timedelta(days=60),
        )
        bloque = ContratoBloqueGym.objects.create(
            cliente=self.cliente, version=1, estado=ContratoBloqueGym.ESTADO_ACTIVO,
            estrategia=estrategia, limites_snapshot={}, fingerprint='v' * 64,
            semana_inicio=hoy - timedelta(days=60), semanas_previstas=4,
            semana_fin_prevista=hoy - timedelta(days=33), objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal='hipertrofia', objetivos_secundarios=[], motor_nombre='Helms', motor_version='x',
        )
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        cerrar_aprendizaje_gym(EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=hoy))
        bloque.refresh_from_db()
        self.assertEqual(bloque.estado, ContratoBloqueGym.ESTADO_FINALIZADO)


class CentroSigueLaPeriodizacion(Base):
    """El Centro dice lo mismo que la Memoria: bloque, semana y balance."""

    def test_resumen_operativo_sin_acuerdos(self):
        from entrenos.services.centro_decisiones_service import construir_resumen_operativo_centro
        self.semanas([1, 2, 3])
        hoy = LUNES + timedelta(weeks=2, days=2)
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=hoy - timedelta(days=1))
        r = construir_resumen_operativo_centro(self.cliente, {'bloque': None}, None, hoy)
        self.assertEqual(r['bloque']['estado'], 'periodizacion')
        self.assertEqual((r['bloque']['semana_actual'], r['bloque']['semanas_total']), (3, 7))
        self.assertEqual(r['bloque']['nombre'], 'Hipertrofia — Acumulación')
        self.assertEqual(r['semana'], {
            'estado': 'periodizacion', 'completadas': 1, 'sesiones_completadas': 1,
            'sesiones_parciales': None, 'sesiones_realizadas': 1, 'objetivo': 4, 'minimo': None,
        })

    def test_sin_periodizacion_sigue_desconocido(self):
        from entrenos.services.centro_decisiones_service import construir_resumen_operativo_centro
        r = construir_resumen_operativo_centro(self.cliente, {'bloque': None}, None, LUNES)
        self.assertIsNone(r['bloque']['semana_actual'])
        self.assertEqual(r['semana']['estado'], 'desconocido')

    def test_balance_de_la_semana_pasada(self):
        from entrenos.models import EjercicioRealizado, SerieRealizada
        from entrenos.services.revision_bloque_service import balance_semana_pasada
        from rutinas.models import EjercicioBase
        self.semanas([1, 2])
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        base = EjercicioBase.objects.create(nombre='Prensa', grupo_muscular='otros')
        for dia, vol, minutos, energia, rpe in ((0, 10000, 60, 6, 8), (2, 12500, 70, 8, 9), (2, 500, 10, None, None)):
            e = EntrenoRealizado.objects.create(
                cliente=self.cliente, rutina=rutina, fecha=LUNES + timedelta(days=dia),
                duracion_minutos=minutos, energia_pre_sesion=energia,
            )
            EntrenoRealizado.objects.filter(pk=e.pk).update(volumen_total_kg=vol)
            if rpe:
                SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=1, repeticiones=10,
                                              peso_kg=100, rpe_real=rpe, completado=True)
        b = balance_semana_pasada(self.cliente, hoy=LUNES + timedelta(days=9))
        self.assertEqual((b['lunes'], b['hechas'], b['previstas'], b['cumplida']), (LUNES, 2, 4, False))
        self.assertEqual((b['volumen_kg'], b['minutos'], b['rpe_medio'], b['energia_media']),
                         ('23.000', 140, '8,5', '7,0'))

    def test_sin_periodizacion_no_hay_balance(self):
        from entrenos.services.revision_bloque_service import balance_semana_pasada
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=LUNES)
        self.assertIsNone(balance_semana_pasada(self.cliente, hoy=LUNES + timedelta(days=9)))

    def test_pantalla_del_centro(self):
        from django.urls import reverse
        from django.utils import timezone
        from entrenos.services.periodizacion_dinamica_service import lunes_de
        este_lunes = lunes_de(timezone.localdate())
        for i, n in enumerate((1, 2)):
            SemanaPlanGym.objects.create(cliente=self.cliente, lunes=este_lunes - timedelta(weeks=1 - i),
                                         semana_plan=n, origen=SemanaPlanGym.ORIGEN_AVANCE)
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1')
        EntrenoRealizado.objects.create(cliente=self.cliente, rutina=rutina, fecha=este_lunes - timedelta(days=5))
        self.client.force_login(self.cliente.user)
        r = self.client.get(reverse('clientes:plan_decisiones'))
        html = r.content.decode()
        self.assertIn('Semana 2 de 7', html)
        self.assertIn('Hipertrofia — Acumulación', html)
        self.assertNotIn('Bloque sin semana actual', html)
        self.assertNotIn('Semana pendiente de programar', html)
        self.assertIn('1 de 4 sesiones', html)
        self.assertIn('El bloque lo lleva la periodización', html)
        self.assertIn('Ver rutina', html)
        self.assertNotIn('aria-label="Preparar bloque Gym"', html)
