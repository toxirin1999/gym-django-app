"""Paso 3 (13-oct-2026): la semana como cola de sesiones.

El día que entrenas toca la siguiente sesión de la semana que aún no has
hecho; lo que no hiciste entre semana pasa al fin de semana; la semana se
cierra el domingo y el lunes se dice qué se quedó fuera.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from clientes.models import Cliente
from entrenos.models import EntrenoRealizado, SesionProgramada
from entrenos.services.porque_decision_service import construir_porque
from entrenos.services.sesion_recomendada import (
    MOTIVO_OMISION_SEMANA_CERRADA, cola_semana, obtener_sesion_recomendada_hoy,
)
from rutinas.models import Rutina

LUNES = date(2026, 10, 19)
DESCANSO = {'rutina_nombre': 'Día de Descanso', 'ejercicios': []}


def _sesion(n, grupos):
    nombre = f'Dia {n} - Hipertrofia'
    return {
        'rutina_nombre': nombre,
        'nombre_rutina': nombre,
        'ejercicios': [
            {'nombre': f'Ejercicio {g}', 'grupo_muscular': g, 'series': 4, 'repeticiones': '8-12'}
            for g in grupos
        ],
    }


# Semana de 5 días; consecutivos sin músculos repetidos, como el reparto real.
PLAN = {
    LUNES: _sesion(1, ['cuadriceps', 'pecho']),
    LUNES + timedelta(days=1): _sesion(2, ['espalda', 'gluteos']),
    LUNES + timedelta(days=2): _sesion(3, ['biceps', 'cuadriceps']),
    LUNES + timedelta(days=3): _sesion(4, ['isquios', 'pecho']),
    LUNES + timedelta(days=4): _sesion(5, ['hombros', 'triceps']),
}


def _plan(fecha):
    base = PLAN.get(fecha - timedelta(days=7 * ((fecha - LUNES).days // 7)))
    return dict(base) if base else dict(DESCANSO)


class ColaSemanalBase(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='cola', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'Cola'})
        Cliente.objects.filter(pk=self.cliente.pk).update(fecha_registro=date(2026, 1, 1))
        self.cliente.refresh_from_db()
        planificador = MagicMock()
        planificador.generar_entrenamiento_para_fecha.side_effect = _plan
        self._p = patch(
            'entrenos.services.sesion_recomendada._build_planificador', return_value=planificador,
        )
        self._p.start()
        self.addCleanup(self._p.stop)
        self.addCleanup(cache.clear)

    def entrenar(self, fecha, nombre):
        rutina, _ = Rutina.objects.get_or_create(nombre=nombre)
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=rutina, fecha=fecha, fecha_ejecucion=fecha,
        )

    def hoy(self, fecha):
        cache.clear()
        return obtener_sesion_recomendada_hoy(self.cliente, fecha)

    @staticmethod
    def nombre(decision):
        return (decision.get('entrenamiento') or {}).get('rutina_nombre')


class SaltarseUnDiaNoPierdeSesiones(ColaSemanalBase):
    def test_saltarse_el_martes_no_borra_el_dia_3(self):
        self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        miercoles = LUNES + timedelta(days=2)
        d = self.hoy(miercoles)
        self.assertEqual(d['tipo'], 'pendiente')
        self.assertEqual(self.nombre(d), 'Dia 2 - Hipertrofia')
        self.entrenar(miercoles, 'Dia 2 - Hipertrofia')

        jueves = LUNES + timedelta(days=3)
        d = self.hoy(jueves)
        self.assertEqual(d['tipo'], 'pendiente')
        self.assertEqual(self.nombre(d), 'Dia 3 - Hipertrofia')
        self.assertEqual(d['sesion_programada'].fecha_prevista, miercoles)

    def test_lo_que_falta_pasa_al_fin_de_semana(self):
        for i in range(4):
            self.entrenar(LUNES + timedelta(days=i), f'Dia {i + 1} - Hipertrofia')
        sabado = LUNES + timedelta(days=5)
        d = self.hoy(sabado)
        self.assertEqual(d['tipo'], 'pendiente')
        self.assertEqual(self.nombre(d), 'Dia 5 - Hipertrofia')

    def test_semana_completa_el_fin_de_semana_descansa(self):
        for i in range(5):
            self.entrenar(LUNES + timedelta(days=i), f'Dia {i + 1} - Hipertrofia')
        d = self.hoy(LUNES + timedelta(days=5))
        self.assertEqual(d['tipo'], 'descanso')

    def test_una_sesion_al_dia(self):
        martes = LUNES + timedelta(days=1)
        self.entrenar(martes, 'Dia 2 - Hipertrofia')  # el lunes no entrenó
        d = self.hoy(martes)
        self.assertNotEqual(d['tipo'], 'pendiente')

    def test_la_cola_marca_que_esta_hecho(self):
        self.entrenar(LUNES + timedelta(days=2), 'Dia 2 - Hipertrofia')
        cola = cola_semana(self.cliente, LUNES + timedelta(days=2))
        hechas = {s['nombre']: s['hecha'] for s in cola}
        self.assertEqual(hechas, {
            'Dia 1 - Hipertrofia': False, 'Dia 2 - Hipertrofia': True, 'Dia 3 - Hipertrofia': False,
        })


class NoRepetirMusculoDosDiasSeguidos(ColaSemanalBase):
    def test_salta_a_la_siguiente_si_la_primera_repite_musculo_de_ayer(self):
        # El lunes no entrena. El martes hace el Día 3 (bíceps, cuádriceps).
        # El miércoles la primera pendiente es el Día 1 (cuádriceps, pecho):
        # repite cuádriceps → se adelanta el Día 2 (espalda, glúteos).
        martes = LUNES + timedelta(days=1)
        self.entrenar(martes, 'Dia 3 - Hipertrofia')
        d = self.hoy(LUNES + timedelta(days=2))
        self.assertEqual(self.nombre(d), 'Dia 2 - Hipertrofia')


class SemanaCerrada(ColaSemanalBase):
    def test_lo_no_hecho_no_se_arrastra_y_el_lunes_se_dice(self):
        for i in range(3):
            self.entrenar(LUNES + timedelta(days=i), f'Dia {i + 1} - Hipertrofia')
        self.hoy(LUNES + timedelta(days=6))  # domingo: se registran las pendientes
        lunes_siguiente = LUNES + timedelta(days=7)
        d = self.hoy(lunes_siguiente)

        self.assertEqual(d['tipo'], 'programada_hoy')
        self.assertEqual(self.nombre(d), 'Dia 1 - Hipertrofia')
        cerradas = SesionProgramada.objects.filter(
            cliente=self.cliente, motivo_estado=MOTIVO_OMISION_SEMANA_CERRADA,
            fecha_prevista__gte=LUNES,
        )
        self.assertEqual(
            sorted(cerradas.values_list('fecha_prevista', flat=True)),
            [LUNES + timedelta(days=3), LUNES + timedelta(days=4)],
        )
        self.assertEqual(
            d['nota_semana'],
            'La semana pasada se quedaron sin hacer el Día 4 y el Día 5. '
            'No lo arrastro: la semana empieza limpia.',
        )
        self.assertEqual(construir_porque(d), d['nota_semana'])


class ElPorQueDeLaCola(ColaSemanalBase):
    def test_dice_de_que_dia_era_la_sesion(self):
        self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        d = self.hoy(LUNES + timedelta(days=2))
        self.assertEqual(
            construir_porque(d), 'El Día 2 era del martes: no se pierde, lo haces hoy.',
        )
