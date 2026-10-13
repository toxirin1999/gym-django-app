"""El Plan enseña la semana como la cola de Ahora (13-oct-2026)."""

from datetime import date, timedelta

from django.test import SimpleTestCase

from entrenos.services.trayectoria_plan_service import _aplicar_cola_semanal

LUNES = date(2026, 10, 12)
DOMINGO = LUNES + timedelta(days=6)


def _sesion(n, realizada=False, fecha_realizada=None):
    f = LUNES + timedelta(days=n - 1)
    return {
        'id': None, 'nombre': f'Día {n}', 'estado': 'completada' if realizada else 'prevista',
        'fecha_prevista': f, 'fecha_pospuesta': None, 'fecha_efectiva': f,
        'fecha_realizada': fecha_realizada, 'realizada': realizada,
        'completa': realizada, 'parcial': False,
    }


class ColaEnElPlan(SimpleTestCase):
    def test_lo_atrasado_pasa_a_hoy_y_el_resto_se_corre(self):
        sesiones = [_sesion(n) for n in range(1, 6)]
        resultado = _aplicar_cola_semanal(sesiones, LUNES + timedelta(days=1), DOMINGO)
        fechas = {s['nombre']: s['fecha_efectiva'] for s in resultado}
        self.assertEqual(fechas['Día 1'], LUNES + timedelta(days=1))   # hoy, martes
        self.assertEqual(fechas['Día 2'], LUNES + timedelta(days=2))
        self.assertEqual(fechas['Día 5'], LUNES + timedelta(days=5))   # sábado
        self.assertEqual(resultado[0]['fecha_pospuesta'], LUNES + timedelta(days=1))

    def test_sin_atrasos_no_cambia_nada(self):
        sesiones = [_sesion(1, realizada=True, fecha_realizada=LUNES)] + [_sesion(n) for n in range(2, 6)]
        resultado = _aplicar_cola_semanal(sesiones, LUNES + timedelta(days=1), DOMINGO)
        self.assertTrue(all(s['fecha_pospuesta'] is None for s in resultado))

    def test_si_hoy_ya_entrenaste_la_cola_empieza_manana(self):
        martes = LUNES + timedelta(days=1)
        sesiones = [_sesion(1), _sesion(2, realizada=True, fecha_realizada=martes)] + [
            _sesion(n) for n in range(3, 6)]
        resultado = _aplicar_cola_semanal(sesiones, martes, DOMINGO)
        fechas = {s['nombre']: s['fecha_efectiva'] for s in resultado}
        self.assertEqual(fechas['Día 1'], martes + timedelta(days=1))

    def test_lo_que_no_cabe_antes_del_domingo_queda_atrasado(self):
        sesiones = [_sesion(n) for n in range(1, 6)]
        sabado = LUNES + timedelta(days=5)
        resultado = _aplicar_cola_semanal(sesiones, sabado, DOMINGO)
        fechas = {s['nombre']: s['fecha_efectiva'] for s in resultado}
        self.assertEqual(fechas['Día 1'], sabado)
        self.assertEqual(fechas['Día 2'], DOMINGO)
        self.assertEqual(fechas['Día 3'], LUNES + timedelta(days=2))  # no cabe: sigue atrasada


class PlantillaSinComentariosVisibles(SimpleTestCase):
    """Un comentario {# #} de varias líneas se pinta como texto en Django."""

    def test_ninguna_plantilla_tiene_comentarios_multilinea(self):
        import glob
        import re
        culpables = []
        for ruta in glob.glob('**/templates/**/*.html', recursive=True):
            with open(ruta, encoding='utf-8', errors='ignore') as f:
                texto = f.read()
            if any('\n' in m.group(1) for m in re.finditer(r'\{#(.*?)#\}', texto, re.S)):
                culpables.append(ruta)
        self.assertEqual(culpables, [])
