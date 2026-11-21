"""La huella que calcula el movil (JavaScript) y la del servidor deben coincidir.

Los valores esperados salen de ejecutar la implementacion real de
``entrenamiento_activo.html`` (``sha256Hex`` + ``cadenaCanonica``) con Node.
Si cambias una de las dos implementaciones, regenera estos valores.
"""

import re
import shutil
import subprocess
import tempfile
import os
from pathlib import Path

from django.http import QueryDict
from django.test import SimpleTestCase

from entrenos.services import guardado_sesion_service as gs

CASOS = [
    [["fecha", "2026-11-21"], ["rutina_nombre", "Día Pierna ñ"], ["ej1_peso_1", "60"], ["ej1_reps_1", "8"], ["duracion_minutos_real", "99"], ["csrfmiddlewaretoken", "x"]],
    [["notas", "línea1\r\nlínea2\rlínea3 "], ["b", "  espacios  "], ["a", "1"], ["a", "2"], ["e", "😀 emoji"]],
    [["vacio", ""]],
    [["k" + str(i), "v" * i] for i in range(1, 80)],
]
ESPERADAS = [
    '97588010120addeb63037b4ee174eb3ffdf03174baac662a9310974471daea0c',
    '9bda09be744562337e868cf0377ca2794cf7dc2aa597f94ccec185f35126c789',
    'ea83aa342d6be7b72a56310aebc33d7329fe6095452858c2478d8fa15ef57ef8',
    '9bc69fdd0b64b39e12d86ddbb7f1fd1d61c51218ee68d1ba6662913ecad95dd6',
]
PLANTILLA = Path(__file__).parent / 'templates' / 'entrenos' / 'entrenamiento_activo.html'


def _post(entradas):
    q = QueryDict(mutable=True)
    for k, v in entradas:
        q.appendlist(k, v)
    return q


class ParidadDeLaHuella(SimpleTestCase):
    def test_python_da_las_huellas_esperadas(self):
        for entradas, esperada in zip(CASOS, ESPERADAS):
            self.assertEqual(gs.huella_de_post(_post(entradas)), esperada)

    def test_las_claves_excluidas_coinciden_en_js_y_python(self):
        js = PLANTILLA.read_text(encoding='utf-8')
        m = re.search(r'const CLAVES_FUERA_DE_HUELLA=\[(.*?)\];', js, re.S)
        self.assertIsNotNone(m)
        claves_js = set(re.findall(r"'([^']+)'", m.group(1)))
        self.assertEqual(claves_js, set(gs.CLAVES_FUERA_DE_HUELLA))

    def test_la_implementacion_js_de_la_plantilla_da_lo_mismo(self):
        if not shutil.which('node'):
            self.skipTest('node no esta instalado')
        js = PLANTILLA.read_text(encoding='utf-8')
        a = js.index('function sha256Hex')
        b = js.index('function huellaDeFormData')
        import json
        codigo = (
            js[a:b]
            + f"\nconst casos={json.dumps(CASOS)};\n"
            + "console.log(JSON.stringify(casos.map(c=>sha256Hex(cadenaCanonica(c)))));\n"
        )
        # CLAVES_FUERA_DE_HUELLA se declara justo antes de cadenaCanonica: ya esta en el recorte.
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, 'par.js')
            Path(ruta).write_text(codigo, encoding='utf-8')
            salida = subprocess.run(['node', ruta], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(salida), ESPERADAS)


class ComportamientoDelMovil(SimpleTestCase):
    """Ejecuta el arnes Node del guardado seguro (DOM y servidor simulados)."""

    def test_arnes_js_del_guardado_seguro(self):
        if not shutil.which('node'):
            self.skipTest('node no esta instalado')
        arnes = Path(__file__).parent / 'tests_js' / 'guardado_seguro_harness.js'
        r = subprocess.run(['node', str(arnes), str(PLANTILLA)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('pruebas JS ok', r.stdout)
