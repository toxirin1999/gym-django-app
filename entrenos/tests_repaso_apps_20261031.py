"""31-oct-2026 · Repaso de apps fitness: lo que se decidió implementar.

- Idea 9 (Hevy): tocar el RPE guarda la serie si no se cambió peso ni reps.
- Idea 6 (Oura): una sola media de variabilidad (4 semanas) en todas las pantallas.
- Idea 2 (RP, sin botones): series por zona con datos que ya se registran:
  −2 si la zona pasa del máximo dos semanas seguidas; +2 si sus ejercicios
  terminan con margen de RPE tres sesiones seguidas sin progresar.
"""

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import timezone

from entrenos.models import GymDecisionVersion, PropuestaZonaGym
from entrenos.services import propuesta_zona_service as pz
from entrenos.tests_ultima_sesion import Base
from rutinas.models import EjercicioBase

HOY = timezone.localdate()
PLANTILLA = Path(settings.BASE_DIR) / 'entrenos' / 'templates' / 'entrenos' / 'entrenamiento_activo.html'


class RPEGuardaLaSerie(SimpleTestCase):
    def setUp(self):
        self.html = PLANTILLA.read_text(encoding='utf-8')

    def test_tocar_rpe_intenta_guardar(self):
        self.assertIn('guardarConRPESiNadaCambio(btn.dataset.fidSn);', self.html)
        self.assertIn("document.querySelector('.btn-guardar[data-fid=\"' + fid + '\"][data-sn=\"' + sn + '\"]')", self.html)

    def test_tocar_peso_reps_o_aproximacion_obliga_a_guardar(self):
        inicio = self.html.index('function ajustarPesoPanel(')
        self.assertIn('marcarSerieTocada(fid,sn);', self.html[inicio:inicio + 900])
        inicio = self.html.index('function cambiarPicker(')
        self.assertIn('marcarSerieTocada(fid,sn);', self.html[inicio:inicio + 900])
        self.assertIn("/^aproximacion-(.+)-(\\d+)$/", self.html)

    def test_no_guarda_al_corregir_una_serie_guardada(self):
        inicio = self.html.index('function guardarConRPESiNadaCambio(')
        cuerpo = self.html[inicio:inicio + 700]
        self.assertIn('_serieEnEdicion[fid] === parseInt(sn)', cuerpo)
        self.assertIn("document.getElementById('check-' + fidSn)?.checked", cuerpo)


class UnaSolaVariabilidad(Base):
    def dias(self, valores, desde=1):
        from clientes.models import BitacoraDiaria
        for i, v in enumerate(valores):
            # ``fecha`` es auto_now_add: se crea y se mueve al día que toca.
            b = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=v)
            BitacoraDiaria.objects.filter(pk=b.pk).update(fecha=HOY - timedelta(days=desde + i))

    def test_media_de_4_semanas_sin_la_de_hoy(self):
        from entrenos.services.recuperacion_service import media_variabilidad
        self.dias([60] * 6)                 # dentro de las 4 semanas
        self.dias([90] * 6, desde=40)       # fuera: no cuentan
        self.assertEqual(media_variabilidad(self.cliente, HOY), 60)

    def test_sin_mananas_suficientes_no_hay_media(self):
        from entrenos.services.recuperacion_service import media_variabilidad
        self.dias([60, 62])
        self.assertIsNone(media_variabilidad(self.cliente, HOY))

    def test_memoria_usa_la_misma_media(self):
        from entrenos.services.modelo_usuario_service import _get_hrv_patron
        from entrenos.services.recuperacion_service import media_variabilidad
        self.dias([45, 75] * 3)
        self.dias([95] * 6, desde=35)       # 60 días: subirían la media de Memoria
        altos, bajos = [i for i in range(1, 7) if i % 2 == 0], [i for i in range(1, 7) if i % 2]
        for i in altos + bajos:
            e = self.entreno(HOY - timedelta(days=i), {'Sentadilla Hack': '12-15'})
            rpe = 7 if i in altos else 9
            self.hacer(e, self.hack, [(60, 12, rpe)])
        patron = _get_hrv_patron(self.cliente, HOY)
        self.assertIsNotNone(patron)
        self.assertEqual(patron['hrv_medio'], media_variabilidad(self.cliente, HOY))

    def test_las_pantallas_dicen_la_ventana(self):
        base = Path(settings.BASE_DIR) / 'clientes' / 'templates' / 'clientes'
        self.assertIn('(media de las 4 semanas anteriores)', (base / 'cuerpo.html').read_text(encoding='utf-8'))
        memoria = (base / 'memoria_entrenador.html').read_text(encoding='utf-8')
        self.assertIn('HRV · media de 4 semanas', memoria)
        self.assertIn('HRV · media 4 sem.', memoria)


def _marcador(filas):
    return patch('entrenos.services.marcador_semanal_service.marcador_cacheado', return_value={'filas': filas})


class PorEncimaDelMaximo(Base):
    FILA = {'clave': 'tríceps', 'grupo': 'Tríceps', 'hechas': 17, 'minimo': 9, 'maximo': 14}

    def test_dos_semanas_seguidas_por_encima(self):
        with _marcador([self.FILA]), patch('entrenos.services.marcador_semanal_service.series_hechas',
                                           return_value={'tríceps': 16}):
            self.assertEqual(pz.zonas_por_encima_del_maximo(self.cliente, HOY), {'triceps': (17, 16, 9, 14)})

    def test_una_semana_alta_no_basta(self):
        with _marcador([self.FILA]), patch('entrenos.services.marcador_semanal_service.series_hechas',
                                           return_value={'tríceps': 12}):
            self.assertEqual(pz.zonas_por_encima_del_maximo(self.cliente, HOY), {})

    def test_propone_bajar_con_el_dato(self):
        with _marcador([self.FILA]), patch('entrenos.services.marcador_semanal_service.series_hechas',
                                           return_value={'tríceps': 16}):
            p = pz.generar_propuesta_si_procede(self.cliente, HOY)
        self.assertEqual((p.zona, p.direccion), ('triceps', PropuestaZonaGym.DIRECCION_BAJAR))
        self.assertEqual(p.deteccion['motivo'], 'por_encima_del_maximo')
        self.assertIn('17 series esta semana y 16 la anterior', p.texto)
        self.assertIn('(9–14)', p.texto)
        self.assertIn('−2 series semanales de Tríceps', p.texto)

    def test_zona_por_encima_no_recibe_mas_series_aunque_retroceda(self):
        retroceso = {'zona': 'triceps', 'nombre_zona': 'Tríceps', 'pct': -6.0, 'ejercicios': []}
        with patch.object(pz, '_generar_propuesta_por_encima', return_value=None), \
                patch.object(pz, 'detectar_zona_en_retroceso', return_value=retroceso), \
                patch.object(pz, 'zonas_por_encima_del_maximo', return_value={'triceps': (17, 16, 9, 14)}), \
                patch.object(pz, '_generar_propuesta_margen', return_value=None), \
                patch.object(pz, '_generar_propuesta_bajar', return_value=None):
            self.assertIsNone(pz.generar_propuesta_si_procede(self.cliente, HOY))


class MargenSinProgreso(Base):
    def setUp(self):
        super().setUp()
        self.depie = EjercicioBase.objects.create(
            nombre='Elevación de Gemelos de Pie', grupo_muscular='gemelos', tipo_progresion='peso_reps',
        )

    def sesion(self, dias, series_por_base, rpe_pedido=9):
        e = self.entreno(HOY - timedelta(days=dias), {b.nombre: '15-20' for b in series_por_base})
        v = e.gym_decision_version
        v.snapshot = {'entrenamiento': {'ejercicios': [
            {'nombre': b.nombre, 'repeticiones': '15-20', 'rpe_objetivo': rpe_pedido} for b in series_por_base
        ]}}
        v.save(update_fields=['snapshot'])
        for b, series in series_por_base.items():
            self.hacer(e, b, series)
        return e

    def tres(self, sentado, depie):
        for dias, s, p in zip((21, 14, 7), sentado, depie):
            self.sesion(dias, {self.gemelos: s, self.depie: p})

    FILA = [{'clave': 'gemelos', 'grupo': 'Gemelos', 'hechas': 6, 'minimo': 9, 'maximo': 13}]

    def test_tres_sesiones_con_margen_y_sin_subir(self):
        self.tres([[(80, 15, 7)]] * 3, [[(100, 15, 7)]] * 3)
        with _marcador(self.FILA):
            d = pz.detectar_zona_con_margen(self.cliente, HOY)
            p = pz.generar_propuesta_si_procede(self.cliente, HOY)
        self.assertEqual(d['zona'], 'gemelos')
        self.assertEqual((p.zona, p.direccion), ('gemelos', PropuestaZonaGym.DIRECCION_SUBIR))
        self.assertIn('terminaste a RPE 7, 7, 7 cuando se pedía 9', p.texto)
        self.assertIn('+2 series semanales de Gemelos', p.texto)

    def test_si_progresa_no_propone(self):
        self.tres([[(80, 15, 7)], [(80, 16, 7)], [(85, 15, 7)]], [[(100, 15, 7)], [(100, 16, 7)], [(105, 15, 7)]])
        with _marcador(self.FILA):
            self.assertIsNone(pz.detectar_zona_con_margen(self.cliente, HOY))

    def test_sin_margen_suficiente_no_propone(self):
        self.tres([[(80, 15, 7)], [(80, 15, 8.5)], [(80, 15, 7)]], [[(100, 15, 7)], [(100, 15, 8.5)], [(100, 15, 7)]])
        with _marcador(self.FILA):
            self.assertIsNone(pz.detectar_zona_con_margen(self.cliente, HOY))

    def test_con_energia_baja_cuenta_el_rpe_pedido_ese_dia(self):
        # Ese día se pidió 7 (energía baja): RPE 7 era lo pedido, no margen.
        self.sesion(21, {self.gemelos: [(80, 15, 7)], self.depie: [(100, 15, 7)]})
        self.sesion(14, {self.gemelos: [(80, 15, 7)], self.depie: [(100, 15, 7)]}, rpe_pedido=7)
        self.sesion(7, {self.gemelos: [(80, 15, 7)], self.depie: [(100, 15, 7)]})
        with _marcador(self.FILA):
            self.assertIsNone(pz.detectar_zona_con_margen(self.cliente, HOY))

    def test_zona_ya_en_su_maximo_no_sube(self):
        self.tres([[(80, 15, 7)]] * 3, [[(100, 15, 7)]] * 3)
        llena = [dict(self.FILA[0], hechas=13)]
        with _marcador(llena):
            self.assertIsNone(pz.detectar_zona_con_margen(self.cliente, HOY))

    def test_molestia_reciente_frena(self):
        from entrenos.services import sensacion_zona_service as svc
        self.tres([[(80, 15, 7)]] * 3, [[(100, 15, 7)]] * 3)
        ultima = self.sesion(2, {self.gemelos: [(80, 15, 7)]})
        svc.guardar(self.cliente, ultima, 'gemelos', 'molestia', 2)
        with _marcador(self.FILA):
            self.assertIsNone(pz.detectar_zona_con_margen(self.cliente, HOY))
