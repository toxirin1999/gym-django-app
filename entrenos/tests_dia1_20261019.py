"""Revisión del Día 1 de David (19-oct-2026)."""

import importlib
import json
from datetime import date, timedelta
from pathlib import Path

from django.apps import apps
from django.contrib.auth.models import User
from django.test import Client as DjangoClient, SimpleTestCase, TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    EjercicioRealizado, EntrenoRealizado, GymDecisionLog, SerieRealizada, TopeMaquinaGym,
)
from entrenos.services.maquina_service import salto_fisico, tipo_equipo_carga
from rutinas.models import EjercicioBase, Rutina

PLANTILLA = Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html'


class RangoRealEntreSeries(TestCase):
    """Entre series se subía el peso al llegar al "a por 13": el rango era 13-13."""

    def setUp(self):
        user = User.objects.create_user(username='dia1_rango', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'D', 'dias_disponibles': 5})
        self.http = DjangoClient()
        self.http.force_login(user)

    def test_el_ejercicio_lleva_el_rango_de_la_rutina(self):
        ejercicio = {
            'nombre': 'Elevación de Gemelos Sentado (Máquina)', 'series': 2, 'repeticiones': '15-20',
            'peso_kg': 60, 'reps_objetivo_hoy': 16, 'tipo_progresion': 'peso_reps',
            'tipo_ejercicio': 'accesorio', '_autoridad_gym_materializada': True,
        }
        r = self.http.get(
            reverse('entrenos:entrenamiento_activo', args=[self.cliente.id]),
            {'fecha': date.today().isoformat(), 'rutina_nombre': 'Dia 1 - Test',
             'ejercicios': json.dumps([ejercicio])},
        )
        self.assertEqual(r.status_code, 200)
        ej = r.context['ejercicios_planificados'][0]
        self.assertEqual((ej['reps_min'], ej['reps_max']), (15, 20))
        self.assertContains(r, 'data-reps-max="20"')


class PantallaEjercicio(SimpleTestCase):
    def setUp(self):
        self.src = PLANTILLA.read_text(encoding='utf-8')

    def test_el_peso_se_puede_teclear(self):
        self.assertIn('type="text" inputmode="decimal"', self.src)
        self.assertNotIn("inp.addEventListener('focus',function(){this.blur();});", self.src)

    def test_la_cabecera_no_tapa_la_barra_de_progreso(self):
        self.assertIn('.tb-progress-wrap{top:46px;', self.src)

    def test_titulo_de_la_tarjeta_segun_hacia_donde_se_sale(self):
        self.assertIn("t:'Alguna serie por encima del rango'", self.src)

    def test_sin_barra_vacia_con_todas_las_series_hechas(self):
        self.assertIn("fila.style.display=(comp>=total && total>0)?'none':''", self.src)


class BarraZ(SimpleTestCase):
    def test_discos_de_2_5_se_cargan_de_dos_en_dos(self):
        self.assertEqual(tipo_equipo_carga('Press Francés con Barra Z'), 'barra_z')
        self.assertEqual(salto_fisico('Curl con Barra Z'), 5)


class DecisionConPesoConcreto(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='dia1_ext', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'E'})
        self.base = EjercicioBase.objects.create(nombre='Extensiones de Tríceps con Polea Alta', grupo_muscular='triceps')
        self.rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Test')

    def test_subir_por_encima_del_rango_dice_el_peso(self):
        from entrenos.models import GymDecisionVersion
        from entrenos.services.cierre_entrenamiento_service import _efecto_visible
        from entrenos.services.cierre_porque_service import porque_decision
        e = EntrenoRealizado.objects.create(cliente=self.cliente, rutina=self.rutina, fecha=date(2026, 10, 19))
        e.gym_decision_version = GymDecisionVersion.objects.create(
            cliente=self.cliente, fecha=e.fecha, version=1, decision_id='d-ext',
            origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64,
            postura='empujar',
            snapshot={'entrenamiento': {'ejercicios': [{'nombre': self.base.nombre, 'repeticiones': '15-20'}]}},
        )
        e.save(update_fields=['gym_decision_version'])
        for i, (peso, reps, rpe) in enumerate([(20, 16, 6), (25, 25, 9)], start=1):
            SerieRealizada.objects.create(entreno=e, ejercicio=self.base, serie_numero=i, repeticiones=reps,
                                          peso_kg=peso, rpe_real=rpe, completado=True)
        log = GymDecisionLog.objects.create(
            cliente=self.cliente, ejercicio=self.base.nombre, entreno_origen=e, accion='subir_peso',
            valor_cambio=5, peso_anterior=25, motivo='Media 25 frente al objetivo 20 — objetivo superado con esfuerzo controlado',
        )
        self.assertEqual(
            porque_decision(log, None, None, 'peso_reps'),
            '25 reps con 25 kg, por encima de 20: subo a 30 kg y vuelvo a 15 reps.',
        )
        self.assertEqual(_efecto_visible(log, 'peso_reps'), 'Subirá a 30 kg')


class MigracionGemelos100(TestCase):
    def test_100_5_pasa_a_100(self):
        user = User.objects.create_user(username='dia1_gem', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'G'})
        base = EjercicioBase.objects.create(nombre='Elevación de Gemelos de Pie (Máquina)', grupo_muscular='gemelos')
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Test')
        e = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=date(2026, 10, 19))
        EjercicioRealizado.objects.create(entreno=e, nombre_ejercicio=base.nombre, peso_kg=100.5, series=3,
                                          repeticiones=16, completado=True)
        SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=1, repeticiones=16, peso_kg=100.5, completado=True)
        SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=2, repeticiones=16, peso_kg=100, completado=True)
        TopeMaquinaGym.objects.create(cliente=cliente, ejercicio_normalizado='x', ejercicio=base.nombre, peso_max_kg=100.5)
        mig = importlib.import_module('entrenos.migrations.0067_gemelos_pie_100_kg')
        mig.CLIENTE = cliente.id
        mig.corregir(apps, None)
        self.assertEqual(
            sorted(float(p) for p in SerieRealizada.objects.filter(entreno=e).values_list('peso_kg', flat=True)),
            [100.0, 100.0],
        )
        self.assertEqual(float(TopeMaquinaGym.objects.get(cliente=cliente).peso_max_kg), 100.0)


class EjecucionConPiramideAnterior(TestCase):
    def test_extensiones_salen_en_ejecucion_de_hoy(self):
        from entrenos.models import GymDecisionVersion
        from entrenos.services.cierre_entrenamiento_service import _cambios_relevantes
        user = User.objects.create_user(username='dia1_ejec', password='x')
        cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'X'})
        base = EjercicioBase.objects.create(nombre='Extensiones de Tríceps con Polea Alta', grupo_muscular='triceps')
        rutina, _ = Rutina.objects.get_or_create(nombre='Dia 1 - Test')

        def sesion(fecha, series):
            e = EntrenoRealizado.objects.create(cliente=cliente, rutina=rutina, fecha=fecha)
            e.gym_decision_version = GymDecisionVersion.objects.create(
                cliente=cliente, fecha=fecha, version=1, decision_id=f'd-{fecha}',
                origen=GymDecisionVersion.ORIGEN_MOTOR, fingerprint='a' * 64, base_fingerprint='b' * 64,
                postura='empujar',
                snapshot={'entrenamiento': {'ejercicios': [{'nombre': base.nombre, 'repeticiones': '15-20'}]}},
            )
            e.save(update_fields=['gym_decision_version'])
            pesos = [p for p, _, _ in series]
            ej = EjercicioRealizado.objects.create(
                entreno=e, nombre_ejercicio=base.nombre, peso_kg=max(pesos), series=len(series),
                repeticiones=series[-1][1], completado=True,
            )
            for i, (p, r, rpe) in enumerate(series, start=1):
                SerieRealizada.objects.create(entreno=e, ejercicio=base, serie_numero=i, repeticiones=r,
                                              peso_kg=p, rpe_real=rpe, completado=True)
            return e, ej

        sesion(date(2026, 10, 8), [(40, 10, 9), (35, 10, 8), (30, 11, 8), (25, 12, 8), (20, 15, 7)])
        hoy, ej_hoy = sesion(date(2026, 10, 19), [(20, 16, 6), (25, 25, 9)])
        cambios = _cambios_relevantes(cliente, hoy, [ej_hoy])
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0]['detalle'], '20 × 15 → 25 × 25 (+5 kg)')
