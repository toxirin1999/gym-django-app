"""26-oct-2026 · Semana adaptativa, paso 2: marcador semanal por músculo."""

from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse

from entrenos.models import SerieRealizada
from entrenos.services.marcador_semanal_service import _frase, marcador_semanal, series_hechas
from entrenos.tests_cola_semanal import LUNES, ColaSemanalBase
from rutinas.models import EjercicioBase


class Marcador(ColaSemanalBase):
    def series(self, entreno, nombre, grupo, n):
        base, _ = EjercicioBase.objects.get_or_create(
            nombre=nombre, defaults={'grupo_muscular': grupo, 'tipo_progresion': 'peso_reps'},
        )
        for i in range(1, n + 1):
            SerieRealizada.objects.create(entreno=entreno, ejercicio=base, serie_numero=i,
                                          repeticiones=12, peso_kg=50, rpe_real=8, completado=True)

    def test_hechas_con_indirectas_a_la_mitad(self):
        e = self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        self.series(e, 'Convergent Machine Press', 'Pecho', 4)
        self.series(e, 'Press Francés con Barra Z', 'Tríceps', 3)
        self.series(e, 'Remo en Polea Baja', 'Espalda', 2)
        h = series_hechas(self.cliente, LUNES)
        self.assertEqual(h['pecho'], 4)
        self.assertEqual(h['tríceps'], 3 + 2)  # 3 directas + 4 de press a la mitad
        self.assertEqual(h['bíceps'], 1)

    def test_filas_con_margen_y_quien_lo_cubre(self):
        # Plan de la semana de prueba: cuádriceps y pecho en dos días (4 + 4 series).
        e = self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        self.series(e, 'Sentadilla Hack', 'Cuádriceps', 4)
        m = marcador_semanal(self.cliente, LUNES)
        filas = {f['clave']: f for f in m['filas']}
        self.assertEqual((filas['cuádriceps']['minimo'], filas['cuádriceps']['maximo']), (8, 14))
        self.assertEqual(filas['cuádriceps']['estado'], 'bajo')
        self.assertEqual(filas['cuádriceps']['cubren'], ['Día 3'])
        self.assertEqual(filas['pecho']['cubren'], ['Día 4'])
        self.assertEqual(m['frase'], 'Te faltan 8 series de pecho para el mínimo: el Día 4 las cubre.')

    def test_frase_sin_dias_que_lo_cubran_y_por_encima(self):
        fila = {'grupo': 'Bíceps', 'hechas': 4, 'minimo': 9, 'maximo': 13, 'estado': 'bajo', 'cubren': []}
        self.assertIn('no quedan días esta semana', _frase([fila]))
        alto = {'grupo': 'Pecho', 'hechas': 19, 'minimo': 10, 'maximo': 17, 'estado': 'alto', 'cubren': []}
        self.assertIn('va por encima (19 de 10–17)', _frase([alto]))
        ok = {'grupo': 'Pecho', 'hechas': 12, 'minimo': 10, 'maximo': 17, 'estado': 'ok', 'cubren': []}
        self.assertIsNone(_frase([ok]))

    def test_se_ve_en_plan_y_en_el_panel(self):
        self.client.force_login(self.cliente.user)
        datos = {'filas': [{'grupo': 'Pecho', 'clave': 'pecho', 'hechas': 7, 'minimo': 10, 'maximo': 17,
                            'plan': 13, 'estado': 'bajo', 'cubren': ['Día 5'], 'pct': 41, 'pct_min': 59}],
                 'frase': 'Te faltan 3 series de pecho para el mínimo: el Día 5 las cubre.'}
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value=datos):
            r = self.client.get(reverse('clientes:trayectoria_plan'))
            self.assertContains(r, 'Tu semana por músculo')
            self.assertContains(r, '<strong>7</strong> de 10–17', html=False)
            self.assertContains(r, 'Lo cubre el Día 5')
            r = self.client.get(reverse('clientes:cuerpo'))
            self.assertContains(r, 'Te faltan 3 series de pecho')
