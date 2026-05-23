"""
Phase Diario-Gym 3.0–3.3 — Tests de señal corporal del diario para el plan de entrenamiento.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from diario.models import SeguimientoVires
from diario.services.senales_entrenamiento import (
    obtener_senal_corporal_diario,
    contrastar_senal_vs_entreno,
    calcular_tendencia_senal,
)


def _crear_vires(usuario, dias_atras, cuerpo='', nivel_energia=None, molestia_zona=''):
    fecha = date.today() - timedelta(days=dias_atras)
    obj, _ = SeguimientoVires.objects.get_or_create(
        usuario=usuario, fecha=fecha,
        defaults={'cuerpo_cierre': cuerpo, 'nivel_energia': nivel_energia, 'molestia_zona': molestia_zona},
    )
    obj.cuerpo_cierre = cuerpo
    obj.nivel_energia = nivel_energia
    obj.molestia_zona = molestia_zona
    obj.save()
    return obj


class SenalCorporalDiarioTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('test_senal', password='x')

    # 1. Un único día cargado no genera señal
    def test_un_dia_cargado_no_genera_senal(self):
        _crear_vires(self.user, dias_atras=1, cuerpo='cargado')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertFalse(resultado['hay_senal'])

    # 2. Tres días con cuerpo_cierre="cargado" generan señal moderada
    def test_tres_dias_cargado_genera_moderada(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertTrue(resultado['hay_senal'])
        self.assertEqual(resultado['intensidad'], 'moderada')
        self.assertEqual(resultado['accion'], 'version_esencial')

    # 3. Dos días energía baja + un día cargado generan señal moderada
    def test_dos_energia_baja_mas_cargado_genera_moderada(self):
        _crear_vires(self.user, dias_atras=1, cuerpo='cargado', nivel_energia=1)
        _crear_vires(self.user, dias_atras=2, cuerpo='ligero', nivel_energia=2)
        _crear_vires(self.user, dias_atras=3, cuerpo='ligero', nivel_energia=4)
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertTrue(resultado['hay_senal'])
        self.assertEqual(resultado['intensidad'], 'moderada')

    # 4. dolorido repetido genera señal alta
    def test_dolorido_repetido_genera_alta(self):
        _crear_vires(self.user, dias_atras=1, cuerpo='dolorido')
        _crear_vires(self.user, dias_atras=2, cuerpo='dolorido')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertTrue(resultado['hay_senal'])
        self.assertEqual(resultado['intensidad'], 'alta')
        self.assertEqual(resultado['accion'], 'revisar_carga')

    # 5. Sin datos devuelve hay_senal=False
    def test_sin_datos_no_hay_senal(self):
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertFalse(resultado['hay_senal'])

    # 6. El texto de la señal no usa lenguaje alarmista ni culpabilizador
    def test_texto_no_alarmista(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        texto = resultado.get('texto', '').lower()
        palabras_alarmistas = ['peligro', 'grave', 'error', 'culpa', 'mal', 'fracas']
        for palabra in palabras_alarmistas:
            self.assertNotIn(palabra, texto, f"Texto contiene lenguaje alarmista: '{palabra}'")

    # 7. La señal alta con dolorido + molestia_zona funciona con un solo día dolorido
    def test_dolorido_mas_molestia_zona_genera_alta(self):
        _crear_vires(self.user, dias_atras=1, cuerpo='dolorido', molestia_zona='rodilla')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertTrue(resultado['hay_senal'])
        self.assertEqual(resultado['intensidad'], 'alta')

    # Verificación de no-bloqueo: la señal nunca bloquea ni cambia carga
    def test_senal_no_bloquea_progresion(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='dolorido')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertNotIn('bloquear', resultado)
        self.assertNotIn('modificar_carga', resultado)
        self.assertNotIn('ajuste_volumen', resultado)


class SugerenciaMarginalTest(TestCase):
    """Phase 3.2 — sugerencia de margen sin cambiar el plan."""

    def setUp(self):
        self.user = User.objects.create_user('test_sugerencia', password='x')

    def test_suave_no_tiene_sugerencia(self):
        for d in [1, 2]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertEqual(resultado['intensidad'], 'suave')
        self.assertNotIn('sugerencia', resultado)

    def test_moderada_tiene_sugerencia_de_margen(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertEqual(resultado['intensidad'], 'moderada')
        self.assertIn('sugerencia', resultado)
        sugerencia = resultado['sugerencia'].lower()
        self.assertIn('margen', sugerencia)

    def test_alta_tiene_sugerencia_de_version_esencial(self):
        for d in [1, 2]:
            _crear_vires(self.user, dias_atras=d, cuerpo='dolorido')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        self.assertEqual(resultado['intensidad'], 'alta')
        self.assertIn('sugerencia', resultado)
        sugerencia = resultado['sugerencia'].lower()
        self.assertIn('esencial', sugerencia)

    def test_sugerencia_no_ordena_ni_bloquea(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='apagado')
        resultado = obtener_senal_corporal_diario(self.user, n_dias=5)
        sugerencia = resultado.get('sugerencia', '').lower()
        for palabra in ('debes', 'tienes que', 'obligatorio', 'prohibido', 'bloquea'):
            self.assertNotIn(palabra, sugerencia)


# ── Phase 3.3 — Contraste señal diario vs resultado de entreno ───────────────

def _crear_entreno(cliente, fecha, rpes=None, hay_recovery=False):
    """Crea un EntrenoRealizado con ejercicios de RPE y/o recovery."""
    from entrenos.models import EntrenoRealizado, EjercicioRealizado
    from rutinas.models import EjercicioBase, Rutina
    rutina, _ = Rutina.objects.get_or_create(nombre='Test Rutina Contraste')
    entreno, _ = EntrenoRealizado.objects.get_or_create(
        cliente=cliente, fecha=fecha,
        defaults={'rutina': rutina},
    )
    if rpes:
        for rpe in rpes:
            EjercicioRealizado.objects.create(
                entreno=entreno,
                nombre_ejercicio='Test Squat Contraste',
                series=3,
                repeticiones=8,
                peso_kg=60,
                rpe=rpe,
                is_recovery_load=hay_recovery,
            )
    return entreno


class ContrastesenalVsEntrenoTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('test_contraste', password='x')
        from clientes.models import Cliente
        self.cliente = Cliente.objects.get(user=self.user)

    def test_sin_senal_retorna_none(self):
        # Solo un día cargado → sin señal (umbral no alcanzado)
        _crear_vires(self.user, dias_atras=1, cuerpo='cargado')
        hoy = date.today()
        _crear_entreno(self.cliente, hoy, rpes=[7, 8])
        resultado = contrastar_senal_vs_entreno(self.user, hoy)
        self.assertIsNone(resultado)

    def test_sin_entreno_retorna_none(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        # Sin entreno creado
        resultado = contrastar_senal_vs_entreno(self.user, date.today())
        self.assertIsNone(resultado)

    def test_senal_moderada_rpe_alto_es_alineado(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        hoy = date.today()
        _crear_entreno(self.cliente, hoy, rpes=[8, 9, 8])
        resultado = contrastar_senal_vs_entreno(self.user, hoy)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['tipo'], 'alineado')

    def test_senal_moderada_rpe_bajo_es_no_limitante(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        hoy = date.today()
        _crear_entreno(self.cliente, hoy, rpes=[6, 7, 6])
        resultado = contrastar_senal_vs_entreno(self.user, hoy)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['tipo'], 'no_limitante')

    def test_senal_alta_con_recovery_es_alineado(self):
        for d in [1, 2]:
            _crear_vires(self.user, dias_atras=d, cuerpo='dolorido')
        hoy = date.today()
        _crear_entreno(self.cliente, hoy, rpes=[6], hay_recovery=True)
        resultado = contrastar_senal_vs_entreno(self.user, hoy)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['tipo'], 'alineado')

    def test_texto_contraste_no_usa_acerto_ni_fallo(self):
        for d in [1, 2, 3]:
            _crear_vires(self.user, dias_atras=d, cuerpo='cargado')
        hoy = date.today()
        _crear_entreno(self.cliente, hoy, rpes=[8, 9])
        resultado = contrastar_senal_vs_entreno(self.user, hoy)
        texto = resultado['texto'].lower()
        for palabra in ('acertó', 'falló', 'error', 'culpa', 'mal'):
            self.assertNotIn(palabra, texto)

    def test_fecha_ref_ancla_ventana_correctamente(self):
        # Señal en ventana de 5 días antes de ayer, pero no hoy
        ayer = date.today() - timedelta(days=1)
        for d in range(1, 4):
            fecha = ayer - timedelta(days=d - 1)
            SeguimientoVires.objects.get_or_create(
                usuario=self.user, fecha=fecha,
                defaults={'cuerpo_cierre': 'cargado'},
            )
        senal_ayer = obtener_senal_corporal_diario(self.user, n_dias=5, fecha_ref=ayer)
        self.assertTrue(senal_ayer.get('hay_senal'))


# ── Phase 3.4 — Tendencia de señal corporal ─────────────────────────────────

class TendenciaSenalTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('test_tendencia', password='x')
        from clientes.models import Cliente
        self.cliente = Cliente.objects.get(user=self.user)

    def _dia_cargado_con_entreno_exigente(self, dias_atras):
        """3 días cargados previos + entreno de RPE alto en la fecha."""
        fecha_entreno = date.today() - timedelta(days=dias_atras)
        for offset in range(3):
            f = fecha_entreno - timedelta(days=offset)
            SeguimientoVires.objects.get_or_create(
                usuario=self.user, fecha=f,
                defaults={'cuerpo_cierre': 'cargado'},
            )
        _crear_entreno(self.cliente, fecha_entreno, rpes=[8, 9, 8])

    def test_sin_contrastes_no_hay_tendencia(self):
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        self.assertFalse(resultado['hay_tendencia'])

    def test_un_contraste_alineado_no_genera_tendencia(self):
        self._dia_cargado_con_entreno_exigente(dias_atras=3)
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        self.assertFalse(resultado['hay_tendencia'])

    def test_dos_contrastes_alineados_generan_tendencia_suave(self):
        self._dia_cargado_con_entreno_exigente(dias_atras=5)
        self._dia_cargado_con_entreno_exigente(dias_atras=12)
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        self.assertTrue(resultado['hay_tendencia'])
        self.assertEqual(resultado['nivel'], 'suave')

    def test_cuatro_contrastes_alineados_generan_tendencia_notable(self):
        for d in [3, 10, 17, 24]:
            self._dia_cargado_con_entreno_exigente(dias_atras=d)
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        self.assertTrue(resultado['hay_tendencia'])
        self.assertEqual(resultado['nivel'], 'notable')

    def test_no_limitante_atenua_tendencia(self):
        # 2 alineados + 2 no_limitante: score = 2 - 2//2 = 1 → sin tendencia
        self._dia_cargado_con_entreno_exigente(dias_atras=5)
        self._dia_cargado_con_entreno_exigente(dias_atras=12)
        # 2 entrenos con señal moderada pero RPE bajo → no_limitante
        for d in [18, 22]:
            fecha = date.today() - timedelta(days=d)
            for offset in range(3):
                f = fecha - timedelta(days=offset)
                SeguimientoVires.objects.get_or_create(
                    usuario=self.user, fecha=f,
                    defaults={'cuerpo_cierre': 'cargado'},
                )
            _crear_entreno(self.cliente, fecha, rpes=[6, 6, 6])
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        self.assertFalse(resultado['hay_tendencia'])

    def test_texto_tendencia_no_usa_lenguaje_absolutista(self):
        for d in [3, 10, 17, 24]:
            self._dia_cargado_con_entreno_exigente(dias_atras=d)
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        texto = resultado.get('texto', '').lower()
        for palabra in ('siempre', 'eres', 'no aguantas', 'imposible', 'fracas', 'culpa'):
            self.assertNotIn(palabra, texto)

    def test_tendencia_no_modifica_datos(self):
        # La función no debe escribir en BD ni devolver claves de modificación
        for d in [3, 10]:
            self._dia_cargado_con_entreno_exigente(dias_atras=d)
        resultado = calcular_tendencia_senal(self.user, n_semanas=4)
        self.assertNotIn('ajuste_volumen', resultado)
        self.assertNotIn('bloquear', resultado)
        self.assertNotIn('modificar_carga', resultado)
