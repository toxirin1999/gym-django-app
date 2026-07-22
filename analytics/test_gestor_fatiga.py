# analytics/test_gestor_fatiga.py
"""
Tests unitarios para GestorFatiga — fix reparto per-grupo de series_pesadas_max.

Cobertura:
  - Modo retrocompatible (sin grupos_dia): comportamiento IDÉNTICO al pre-fix.
  - Modo per-grupo (con grupos_dia): reparto determinista, sin grupos en 0
    cuando hay presupuesto suficiente.
  - bisagra_pesada_max y rodilla_pesada_max siguen siendo GLOBALES sin cambio.
"""

from django.test import TestCase

from analytics.planificador_helms.calculo.fatiga import GestorFatiga
from analytics.planificador_helms.config import LIMITES_FATIGA


# ---------------------------------------------------------------------------
# 1. Modo retrocompatible (sin grupos_dia)
# ---------------------------------------------------------------------------

class TestGestorFatigaModoRetrocompat(TestCase):
    """Sin grupos_dia: comportamiento IDÉNTICO al pre-fix (v2)."""

    def test_instancia_sin_grupos_dia_no_lanza(self):
        gf = GestorFatiga('hipertrofia')
        self.assertIsNotNone(gf)

    def test_primer_grupo_puede_agotar_presupuesto_compartido(self):
        """En modo global, el primer grupo en llamar puede consumir todo el presupuesto,
        dejando 0 al siguiente. Esto es el comportamiento legacy que se preserva."""
        gf = GestorFatiga('hipertrofia')
        presupuesto = LIMITES_FATIGA['hipertrofia']['series_pesadas_max']  # 10

        # cuadriceps consume 6 series pesadas (rodilla — acotado por rodilla_pesada_max=5)
        series1 = gf.ajustar_series_por_limite(
            'sentadilla', 'rodilla', 'compuesto_principal', 5, True, grupo='cuadriceps'
        )
        gf.registrar_fatiga('rodilla', series1, True, grupo='cuadriceps')

        # pecho consume lo que quede del presupuesto global
        series2 = gf.ajustar_series_por_limite(
            'press banca', 'empuje_horizontal', 'compuesto_principal', 6, True, grupo='pecho'
        )
        gf.registrar_fatiga('empuje_horizontal', series2, True, grupo='pecho')

        # hombros — presupuesto puede estar agotado si series1 + series2 >= presupuesto
        consumido = series1 + series2
        series3 = gf.ajustar_series_por_limite(
            'press militar', 'empuje_vertical', 'compuesto_principal', 4, True, grupo='hombros'
        )
        if consumido >= presupuesto:
            self.assertEqual(series3, 0,
                "En modo global, cuando el presupuesto está agotado el siguiente grupo "
                "recibe 0 — comportamiento legacy preservado.")
        else:
            self.assertLessEqual(series3, presupuesto - consumido)

    def test_tercer_grupo_recibe_0_cuando_presupuesto_agotado(self):
        """Tres grupos, cada uno pidiendo 4 series, presupuesto=10 → el 3er recibe 0."""
        gf = GestorFatiga('hipertrofia')

        series1 = gf.ajustar_series_por_limite(
            'press banca', 'empuje_horizontal', 'compuesto_principal', 4, True, grupo='pecho'
        )
        gf.registrar_fatiga('empuje_horizontal', series1, True, grupo='pecho')

        series2 = gf.ajustar_series_por_limite(
            'press militar', 'empuje_vertical', 'compuesto_principal', 4, True, grupo='hombros'
        )
        gf.registrar_fatiga('empuje_vertical', series2, True, grupo='hombros')

        # 8 series pesadas consumidas → presupuesto=10, margen=2 < 4 pedidas
        series3 = gf.ajustar_series_por_limite(
            'dominadas', 'traccion_vertical', 'compuesto_principal', 4, True, grupo='espalda'
        )
        gf.registrar_fatiga('traccion_vertical', series3, True, grupo='espalda')

        # 4to grupo: presupuesto agotado (4+4+2=10)
        series4 = gf.ajustar_series_por_limite(
            'curl', 'traccion_horizontal', 'aislamiento', 3, True, grupo='biceps'
        )
        self.assertEqual(series4, 0,
            "En modo global, el 4to grupo recibe 0 cuando el presupuesto está agotado.")

    def test_retrocompat_bisagra_rodilla_iguales(self):
        """Bisagra y rodilla se comportan igual en modo global (no cambiaron)."""
        gf = GestorFatiga('hipertrofia')
        limite_bisagra = LIMITES_FATIGA['hipertrofia']['bisagra_pesada_max']

        series = gf.ajustar_series_por_limite(
            'peso muerto', 'bisagra', 'compuesto_principal', limite_bisagra + 2, True, grupo='isquios'
        )
        self.assertLessEqual(series, limite_bisagra)


# ---------------------------------------------------------------------------
# 2. Modo per-grupo (con grupos_dia): reparto determinista
# ---------------------------------------------------------------------------

class TestGestorFatigaModoPerGrupo(TestCase):
    """Con grupos_dia: reparto determinista, ningún grupo con cupo ≥1 recibe 0."""

    def test_reparto_3_grupos_presupuesto_10(self):
        """10//3=3, resto=1 → grupos[0]=4, grupos[1]=3, grupos[2]=3. Total=10."""
        grupos = ['pecho', 'triceps', 'hombros']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        self.assertEqual(gf.cupo_pesadas_por_grupo['pecho'], 4)
        self.assertEqual(gf.cupo_pesadas_por_grupo['triceps'], 3)
        self.assertEqual(gf.cupo_pesadas_por_grupo['hombros'], 3)
        self.assertEqual(sum(gf.cupo_pesadas_por_grupo.values()), 10)

    def test_reparto_determinista_dos_instancias(self):
        """100% determinista: dos instancias con la misma lista → mismo cupo."""
        grupos = ['cuadriceps', 'isquios', 'gluteos', 'gemelos', 'core', 'pecho']
        gf1 = GestorFatiga('hipertrofia', grupos_dia=grupos)
        gf2 = GestorFatiga('hipertrofia', grupos_dia=grupos)
        self.assertEqual(gf1.cupo_pesadas_por_grupo, gf2.cupo_pesadas_por_grupo)

    def test_6_grupos_presupuesto_10_ninguno_recibe_0(self):
        """Escenario real del bug de david: 6 grupos, presupuesto=10 → todos ≥1."""
        grupos = ['cuadriceps', 'isquios', 'gluteos', 'pecho', 'espalda', 'hombros']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        for g in grupos:
            with self.subTest(grupo=g):
                self.assertGreaterEqual(
                    gf.cupo_pesadas_por_grupo[g], 1,
                    f"{g} recibió 0 cupo con presupuesto=10 y 6 grupos — bug no arreglado"
                )

    def test_6_grupos_presupuesto_10_reparto_exacto(self):
        """10//6=1, resto=4 → grupos[0..3]=2, grupos[4..5]=1. Total=10."""
        grupos = ['cuadriceps', 'isquios', 'gluteos', 'pecho', 'espalda', 'hombros']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        self.assertEqual(sum(gf.cupo_pesadas_por_grupo.values()), 10)
        for g in grupos[:4]:
            with self.subTest(grupo=g):
                self.assertEqual(gf.cupo_pesadas_por_grupo[g], 2)
        for g in grupos[4:]:
            with self.subTest(grupo=g):
                self.assertEqual(gf.cupo_pesadas_por_grupo[g], 1)

    def test_8_grupos_presupuesto_10_todos_reciben_al_menos_1(self):
        """10//8=1, resto=2 → grupos[0..1]=2, grupos[2..7]=1. Todos ≥1."""
        grupos = ['cuadriceps', 'isquios', 'gluteos', 'pecho', 'espalda', 'hombros', 'biceps', 'triceps']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        for g in grupos:
            with self.subTest(grupo=g):
                self.assertGreaterEqual(gf.cupo_pesadas_por_grupo[g], 1)

    def test_limite_fisico_mas_grupos_que_presupuesto_determinista(self):
        """12 grupos, presupuesto=10 → grupos[0..9]=1, grupos[10..11]=0.
        Límite físico real — el resultado es determinista en dos ejecuciones."""
        grupos = [
            'cuadriceps', 'isquios', 'gluteos', 'pecho', 'espalda',
            'hombros', 'biceps', 'triceps', 'gemelos', 'core', 'trapecios', 'antebrazos'
        ]
        gf1 = GestorFatiga('hipertrofia', grupos_dia=grupos)
        gf2 = GestorFatiga('hipertrofia', grupos_dia=grupos)
        self.assertEqual(gf1.cupo_pesadas_por_grupo, gf2.cupo_pesadas_por_grupo,
            "El reparto debe ser 100% determinista entre instancias")
        for g in grupos[:10]:
            with self.subTest(grupo=g):
                self.assertEqual(gf1.cupo_pesadas_por_grupo[g], 1)
        for g in grupos[10:]:
            with self.subTest(grupo=g):
                self.assertEqual(gf1.cupo_pesadas_por_grupo[g], 0,
                    f"{g} debería recibir 0 cuando hay más grupos que presupuesto — "
                    "es una limitación física real, no un bug.")

    def test_consumo_por_grupo_es_independiente(self):
        """El cupo de cada grupo es independiente — agotar pecho no afecta espalda."""
        grupos = ['pecho', 'espalda', 'cuadriceps']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        cupo_pecho = gf.cupo_pesadas_por_grupo['pecho']

        # Agotar el cupo de pecho completamente
        gf.registrar_fatiga('empuje_horizontal', cupo_pecho, True, grupo='pecho')

        # Espalda tiene su propio cupo intacto
        series_espalda = gf.ajustar_series_por_limite(
            'dominadas', 'traccion_vertical', 'compuesto_principal', 4, True, grupo='espalda'
        )
        self.assertGreater(series_espalda, 0,
            "El cupo de espalda debe ser independiente del consumo de pecho")

    def test_grupo_agotado_recibe_0_adicional(self):
        """Después de agotar el cupo propio, el grupo recibe 0 adicional."""
        grupos = ['pecho', 'espalda']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        cupo_pecho = gf.cupo_pesadas_por_grupo['pecho']

        gf.registrar_fatiga('empuje_horizontal', cupo_pecho, True, grupo='pecho')

        series = gf.ajustar_series_por_limite(
            'press inclinado', 'empuje_horizontal', 'compuesto_secundario', 3, True, grupo='pecho'
        )
        self.assertEqual(series, 0,
            "Después de agotar el cupo individual, el grupo no puede añadir más series pesadas")


# ---------------------------------------------------------------------------
# 3. bisagra/rodilla siguen siendo GLOBALES — invariante que no debe romperse
# ---------------------------------------------------------------------------

class TestGestorFatigaBisagraRodillaGlobal(TestCase):
    """Confirma que bisagra_pesada_max y rodilla_pesada_max NO cambian a per-grupo."""

    def test_bisagra_max_sigue_siendo_global_con_grupos_dia(self):
        """Con grupos_dia, bisagra_pesada_max es un contador GLOBAL compartido."""
        grupos = ['isquios', 'gluteos', 'pecho']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        limite = LIMITES_FATIGA['hipertrofia']['bisagra_pesada_max']  # 3

        # isquios agota el presupuesto global de bisagra
        gf.registrar_fatiga('bisagra', limite, True, grupo='isquios')

        # gluteos (también bisagra) ya no puede añadir más — presupuesto GLOBAL agotado
        series_gluteos = gf.ajustar_series_por_limite(
            'peso muerto rumano', 'bisagra', 'compuesto_principal', 4, True, grupo='gluteos'
        )
        self.assertEqual(series_gluteos, 0,
            "bisagra_pesada_max debe ser GLOBAL incluso con grupos_dia — no per-grupo")

    def test_rodilla_max_sigue_siendo_global_con_grupos_dia(self):
        """Con grupos_dia, rodilla_pesada_max es un contador GLOBAL compartido."""
        grupos = ['cuadriceps', 'pecho', 'espalda']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)
        limite = LIMITES_FATIGA['hipertrofia']['rodilla_pesada_max']  # 5

        # cuadriceps agota el presupuesto global de rodilla
        gf.registrar_fatiga('rodilla', limite, True, grupo='cuadriceps')

        # Otro ejercicio de rodilla → bloqueado por límite GLOBAL
        series = gf.ajustar_series_por_limite(
            'leg press', 'rodilla', 'compuesto_secundario', 4, True, grupo='cuadriceps'
        )
        self.assertEqual(series, 0,
            "rodilla_pesada_max debe ser GLOBAL — no cambia con el fix per-grupo")

    def test_bisagra_y_rodilla_tienen_contadores_independientes_entre_si(self):
        """Bisagra y rodilla son presupuestos independientes entre sí."""
        grupos = ['isquios', 'cuadriceps']
        gf = GestorFatiga('hipertrofia', grupos_dia=grupos)

        # Agotar bisagra
        gf.registrar_fatiga('bisagra', LIMITES_FATIGA['hipertrofia']['bisagra_pesada_max'], True, grupo='isquios')

        # Rodilla sigue disponible
        series_rodilla = gf.ajustar_series_por_limite(
            'sentadilla', 'rodilla', 'compuesto_principal', 3, True, grupo='cuadriceps'
        )
        self.assertGreater(series_rodilla, 0,
            "Agotar bisagra no debe afectar el presupuesto de rodilla")

    def test_bisagra_rodilla_global_en_modo_retrocompat(self):
        """En modo retrocompat (sin grupos_dia), bisagra/rodilla siguen igual."""
        gf = GestorFatiga('hipertrofia')
        limite_rodilla = LIMITES_FATIGA['hipertrofia']['rodilla_pesada_max']

        gf.registrar_fatiga('rodilla', limite_rodilla, True)

        series = gf.ajustar_series_por_limite(
            'hack squat', 'rodilla', 'compuesto_principal', 3, True, grupo='cuadriceps'
        )
        self.assertEqual(series, 0,
            "Modo retrocompat: rodilla_pesada_max sigue acotando igual que en v2")
