"""4-nov-2026 · Repaso del Día 3 de la descarga.

1. Motivo de la descarga del bloque: primero que toca por el bloque.
2. Cabecera de los ejercicios por tiempo con el objetivo de hoy (no 15-25 s).
3. Zancadas en el cierre: «por pierna» y «las dos piernas».
4. Hip thrust de 2,5 en 2,5.
5. Dead hang en descarga: «· descarga» en la ejecución de hoy.
6. Dead hang en descarga: «Vuelve a 36 s» para la próxima vez.
7. Botón «Después» junto a «Ocupada».
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from entrenos.services.cierre_entrenamiento_service import _unidad_lado
from entrenos.services.maquina_service import salto_fisico
from entrenos.tests_recuperacion_20261024 import HOY
from entrenos.tests_ultima_sesion import Base

PLANTILLAS = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos'


class Plantillas(SimpleTestCase):
    def test_nota2_tiempo_con_objetivo(self):
        src = (PLANTILLAS / 'entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('{% if ejercicio.reps_objetivo %}{{ ejercicio.reps_objetivo }}{% else %}{{ rango_vis }}{% endif %} seg',
                      src)

    def test_nota7_boton_despues(self):
        src = (PLANTILLAS / 'entrenamiento_activo.html').read_text(encoding='utf-8')
        self.assertIn('onclick="dejarParaDespues(\'{{ ejercicio.form_id }}\')"', src)
        self.assertIn('<span>Después</span>', src)
        self.assertIn('function dejarParaDespues(fid)', src)
        self.assertIn('grid-template-columns:repeat(5,1fr)', src)

    def test_nota3_zancadas_por_pierna(self):
        self.assertEqual(_unidad_lado('Zancadas con Kettlebell'), {'reps': 'por pierna', 'kg': 'las dos piernas'})
        self.assertEqual(_unidad_lado('Pallof Press'), {'reps': 'por lado', 'kg': 'los dos lados'})
        src = (PLANTILLAS / 'post_entreno_resumen.html').read_text(encoding='utf-8')
        self.assertIn("{{ trabajo.unidad_lado.reps|default:'por lado' }}", src)

    def test_nota4_hip_thrust_de_2_5(self):
        self.assertEqual(salto_fisico('Hip Thrust con Barra'), 2.5)
        self.assertEqual(salto_fisico('Press Banca con Barra'), 5.0)


class DeadHangDescarga(Base):
    def _hang(self):
        from rutinas.models import EjercicioBase
        return EjercicioBase.objects.create(nombre='Aguante en Barra (Dead Hang)', grupo_muscular='antebrazos',
                                            tipo_progresion='progresion_tiempo')

    def _descarga_esta_semana(self):
        from entrenos.models import SemanaPlanGym
        lunes = HOY - timedelta(days=HOY.weekday())
        SemanaPlanGym.objects.create(cliente=self.cliente, lunes=lunes, semana_plan=44, descarga=True,
                                     origen='descarga_programada')

    def test_nota6_vuelve_a_36_s(self):
        from entrenos.services.cerebro_carga_service import proxima_vez_texto
        hang = self._hang()
        antes = self.entreno(HOY - timedelta(days=12), {hang.nombre: '15-25'})
        self.hacer(antes, hang, [(0, 36, 7), (0, 36, 7)])
        self._descarga_esta_semana()
        hoy = self.entreno(HOY, {hang.nombre: '15-25'})
        self.hacer(hoy, hang, [(0, 30, 6), (0, 30, 6)])
        texto, accion, efecto = proxima_vez_texto(self.cliente, hoy, hang.nombre, 'progresion_tiempo', None,
                                                  con_efecto=True)
        self.assertEqual(accion, 'Volver')
        self.assertEqual(efecto, 'Vuelve a 36 s')
        self.assertIn('36 s', texto)


class MotivoDescarga(SimpleTestCase):
    def test_nota1_texto(self):
        src = (Path(settings.BASE_DIR) / 'entrenos' / 'services' / 'periodizacion_dinamica_service.py').read_text(
            encoding='utf-8')
        self.assertIn('Toca la descarga del final del bloque y la hago', src)
        self.assertNotIn("f'Semana de descarga del bloque: {razon}.'", src)
