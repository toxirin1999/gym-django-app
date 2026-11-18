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

    def test_filas_con_plan_pendientes_y_quien_las_aporta(self):
        # 18-nov-2026: sin rangos mínimo/máximo; el plan de la semana es la referencia.
        e = self.entrenar(LUNES, 'Dia 1 - Hipertrofia')
        self.series(e, 'Sentadilla Hack', 'Cuádriceps', 4)
        m = marcador_semanal(self.cliente, LUNES)
        filas = {f['clave']: f for f in m['filas']}
        cuad = filas['cuádriceps']
        self.assertEqual(cuad['hechas'], 4)
        self.assertEqual(cuad['proyectadas'], cuad['hechas'] + cuad['pendientes'])
        self.assertEqual(cuad['estado'], 'cubierto' if cuad['proyectadas'] >= cuad['plan'] else 'falta')
        self.assertEqual(cuad['cubren'], ['Día 3'])
        self.assertEqual(filas['pecho']['cubren'], ['Día 4'])
        self.assertNotIn('minimo', cuad)
        self.assertIn('Plan de la semana', m['referencia']['texto'])
        self.assertIn('pecho', m['frase'].lower())
        self.assertNotIn('solo cansan', m['frase'])

    def test_frase_solo_hechos_sin_juicio(self):
        fila = {'grupo': 'Bíceps', 'hechas': 4, 'plan': 9, 'pendientes': 0, 'proyectadas': 4,
                'estado': 'falta', 'cubren': []}
        self.assertIn('ninguna sesión pendiente lo trabaja', _frase([fila]))
        alto = {'grupo': 'Pecho', 'hechas': 19, 'plan': 10, 'pendientes': 0, 'proyectadas': 19,
                'estado': 'supera', 'cubren': []}
        f = _frase([alto])
        self.assertIn('llevas 19', f)
        self.assertIn('el plan de la semana pide 10', f)
        self.assertNotIn('cansan', f)
        ok = {'grupo': 'Pecho', 'hechas': 12, 'plan': 10, 'pendientes': 0, 'proyectadas': 12,
              'estado': 'completo', 'cubren': []}
        self.assertIsNone(_frase([ok]))

    def test_se_ve_en_plan_y_en_el_panel(self):
        self.client.force_login(self.cliente.user)
        datos = {'filas': [{'grupo': 'Pecho', 'clave': 'pecho', 'hechas': 7, 'plan': 13, 'pendientes': 4,
                            'proyectadas': 11, 'directas': 7, 'indirectas': 0, 'estado': 'falta',
                            'cubren': ['Día 5'], 'aportan': [{'dia': 'Día 5', 'series': 4}],
                            'hechas_por_sesion': [], 'pct': 54, 'pct_pend': 31, 'pct_plan': 100,
                            'objetivo': 11, 'bar_hechas': 64, 'bar_pend': 36,
                            'detalle': {'hechas': 7, 'pendientes': 4, 'sesiones_hechas': [], 'diferencias': [],
                                        'pendientes_detalle': [{'dia': 'Día 5', 'series': 4, 'ejercicios': []}]}}],
                 'semana_rango': '16/11–22/11', 'hasta_hoy': 'miércoles 18/11',
                 'sesiones_detalle': [{'dia': 'Día 5', 'estado': 'pendiente'}],
                 'referencia': {'texto': 'Plan de la semana 16/11–22/11 según el planificador: 5 sesiones, 1 sin hacer (Día 5)'},
                 'frase': 'Pecho: llevas 7 de 13 que pide el plan; las sesiones pendientes (Día 5) aportan 4 y quedarías en 11.'}
        with patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value=datos):
            r = self.client.get(reverse('clientes:trayectoria_plan'))
            self.assertContains(r, 'Tu semana por músculo')
            self.assertContains(r, '7 hechas · 4 pendientes')
            self.assertContains(r, 'Ver detalle')
            self.assertContains(r, 'Pendiente · Día 5')
            self.assertContains(r, 'Provisional.')
            self.assertContains(r, 'El plan semanal del planificador pide 13 series')
            self.assertNotContains(r, 'solo cansan')
            r = self.client.get(reverse('clientes:cuerpo'))
            self.assertContains(r, 'Pecho: llevas 7 de 13')
