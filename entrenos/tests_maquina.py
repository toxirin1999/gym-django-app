"""Bloque A2 (13-oct-2026): tope de máquina que se recuerda y saltos reales.

Caso real: gemelos de pie en una máquina que llega a 100 kg. "Tope kg" se
marcaba en cada sesión pero se olvidaba, y el plan proponía 102,5 kg.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.template import Context, Template
from django.test import TestCase
from django.utils import translation

from clientes.models import Cliente
from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada, TopeMaquinaGym
from entrenos.services.decision_log_service import _decidir_accion
from entrenos.services.maquina_service import (
    aplicar_tope, incremento_real, registrar_topes_de_entreno, tope_de,
)
from entrenos.services.ultima_sesion_service import aplicar_techo
from rutinas.models import EjercicioBase, Rutina

D = date(2026, 10, 13)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user(username='maquina', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'M'})
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Hipertrofia')
        self.gemelos = EjercicioBase.objects.create(
            nombre='Elevación de Gemelos de Pie (Máquina)', grupo_muscular='gemelos',
            tipo_progresion='peso_reps',
        )
        self.addCleanup(cache.clear)

    def sesion(self, fecha, base, series, tope=False):
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=fecha)
        EjercicioRealizado.objects.create(
            entreno=e, nombre_ejercicio=base.nombre, peso_kg=series[0][0], series=len(series),
            repeticiones=series[0][1], rpe=8, completado=True, es_tope_maquina=tope,
        )
        for i, (peso, reps) in enumerate(series, start=1):
            SerieRealizada.objects.create(
                entreno=e, ejercicio=base, serie_numero=i, repeticiones=reps,
                peso_kg=peso, rpe_real=8, completado=True,
            )
        return e


class TopeGuardado(Base):
    def test_marcar_tope_lo_guarda_con_el_peso_de_las_series(self):
        e = self.sesion(D, self.gemelos, [(100, 15), (100, 15), (100, 15)], tope=True)
        registrar_topes_de_entreno(e)
        self.assertEqual(tope_de(self.cliente, self.gemelos.nombre), 100.0)

    def test_corregir_el_tope_lo_actualiza(self):
        registrar_topes_de_entreno(self.sesion(D, self.gemelos, [(100.5, 15)], tope=True))
        registrar_topes_de_entreno(self.sesion(D + timedelta(days=3), self.gemelos, [(100, 16)], tope=True))
        self.assertEqual(tope_de(self.cliente, self.gemelos.nombre), 100.0)

    def test_levantar_mas_sin_marcar_lo_retira(self):
        registrar_topes_de_entreno(self.sesion(D, self.gemelos, [(100, 15)], tope=True))
        registrar_topes_de_entreno(self.sesion(D + timedelta(days=3), self.gemelos, [(105, 12)]))
        self.assertIsNone(tope_de(self.cliente, self.gemelos.nombre))

    def test_levantar_menos_sin_marcar_lo_conserva(self):
        registrar_topes_de_entreno(self.sesion(D, self.gemelos, [(100, 15)], tope=True))
        registrar_topes_de_entreno(self.sesion(D + timedelta(days=3), self.gemelos, [(90, 15)]))
        self.assertEqual(tope_de(self.cliente, self.gemelos.nombre), 100.0)

    def test_solo_afecta_a_esa_maquina(self):
        otra = EjercicioBase.objects.create(nombre='Prensa de Piernas', grupo_muscular='cuadriceps')
        registrar_topes_de_entreno(self.sesion(D, self.gemelos, [(100, 15)], tope=True))
        self.assertIsNone(tope_de(self.cliente, otra.nombre))

    def test_el_plan_nunca_propone_por_encima(self):
        TopeMaquinaGym.objects.create(
            cliente=self.cliente, ejercicio_normalizado=self.gemelos.nombre.lower(),
            ejercicio=self.gemelos.nombre, peso_max_kg=100,
        )
        ej = {'nombre': self.gemelos.nombre, 'peso_kg': 102.5, 'peso_recomendado_kg': 102.5}
        cambio = aplicar_tope(self.cliente, ej)
        self.assertEqual((ej['peso_kg'], ej['peso_recomendado_kg']), (100.0, 100.0))
        self.assertTrue(ej['sugerencia_tope'])
        self.assertEqual(ej['progresion_motivo'], '100 kg es el máximo de esta máquina: progreso por repeticiones.')
        self.assertEqual(cambio['peso_sugerido'], 100.0)

    def test_tope_marcado_la_ultima_vez_limita_aunque_no_este_guardado(self):
        self.sesion(D, self.gemelos, [(100.5, 15), (100.5, 15)], tope=True)
        ej = {'nombre': self.gemelos.nombre, 'repeticiones': '15-20', 'peso_kg': 102.5,
              'rpe_objetivo': 9, 'tipo_progresion': 'peso_reps'}
        aplicar_techo(self.cliente, ej, D + timedelta(days=4))
        self.assertEqual(ej['peso_kg'], 100.5)
        self.assertIn('marcaste tope en 100,5 kg', ej['progresion_motivo'])


class SaltoReal(Base):
    def test_aprende_el_salto_de_los_pesos_registrados(self):
        conv = EjercicioBase.objects.create(nombre='Convergent Machine Press', grupo_muscular='pecho')
        self.sesion(D - timedelta(days=7), conv, [(57.5, 12), (60, 12)])
        self.sesion(D, conv, [(62.5, 12), (60, 12)])
        self.assertEqual(incremento_real(self.cliente, conv.nombre, 2), 2.5)

    def test_sin_historial_usa_el_de_por_defecto(self):
        self.assertEqual(incremento_real(self.cliente, 'Nada', 5), 5.0)

    def test_ignora_diferencias_de_ruido(self):
        hack = EjercicioBase.objects.create(nombre='Sentadilla Hack', grupo_muscular='cuadriceps')
        self.sesion(D, hack, [(20, 12), (20.5, 12), (21, 12), (22, 8)])
        self.assertEqual(incremento_real(self.cliente, hack.nombre, 2), 1.0)

    def test_el_salto_llega_al_navegador_con_punto(self):
        # Con la app en español, "2.5" se pintaba "2,5" y el JS leía 2.
        with translation.override('es'):
            html = Template("{{ x|default:2.5|stringformat:'s' }}").render(Context({'x': 2.5}))
        self.assertEqual(html, '2.5')


class FarmerMasUnMetro(Base):
    def test_el_cierre_progresa_un_metro_como_el_entrenamiento(self):
        class Perfil:
            reduccion_peso_pct = 5
            incremento_peso_pct = 5
        accion, valor, motivo = _decidir_accion(
            object(), [], Perfil(), 7, False, True, 'progresion_distancia',
        )
        self.assertEqual((accion, valor), ('subir_reps', 1))
        self.assertIn('+1 m', motivo)
