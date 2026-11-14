"""14-nov-2026 · Tu historia en el gym (panel tipo resumen anual), versión 2."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    EdicionHistoria, EjercicioRealizado, EntrenoRealizado, NotaHistoria, SerieRealizada,
)
from entrenos.services.tu_historia_service import (
    calcular_historia, clave_nombre, fase_de, sesiones_limpias,
)
from rutinas.models import EjercicioBase, Rutina

HOY = date(2026, 11, 14)


class TuHistoriaBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='historia', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=self.user, defaults={'nombre': 'H'})
        self.rutina = Rutina.objects.create(nombre='Dia 1 - Hipertrofia')

    def entreno(self, fecha, kg, minutos=60, nombre=None):
        return EntrenoRealizado.objects.create(
            cliente=self.cliente, rutina=self.rutina, fecha=fecha,
            volumen_total_kg=Decimal(kg), duracion_minutos=minutos,
            nombre_rutina_liftin=nombre,
        )


class LimpiezaTests(TuHistoriaBase):
    def test_descarta_dias_de_prueba_duplicados_y_sin_volumen(self):
        for _ in range(3):  # día de pruebas de la app
            self.entreno(date(2025, 8, 7), 1530)
        self.entreno(date(2025, 8, 25), 5420, 50)
        self.entreno(date(2025, 9, 1), 6000)
        self.entreno(date(2025, 9, 1), 6000)  # duplicado
        self.entreno(date(2025, 9, 2), 0)     # sin volumen
        sesiones = sesiones_limpias(self.cliente, HOY)
        self.assertEqual([s.fecha for s in sesiones], [date(2025, 8, 25), date(2025, 9, 1)])

    def test_duracion_absurda_cuenta_como_desconocida(self):
        self.entreno(date(2026, 8, 10), 27875, 1478)
        self.assertIsNone(sesiones_limpias(self.cliente, HOY)[0].minutos)

    def test_nombres_y_fases(self):
        self.assertEqual(clave_nombre('  Jalón  al PECHO '), 'jalon al pecho')
        self.assertEqual(fase_de('Dia 3 - Hipertrofia — Metabólica'), 'Hipertrofia — Metabólica')
        self.assertEqual(fase_de('Día 1 - Hipertrofia_Final'), 'Hipertrofia Final')
        self.assertIsNone(fase_de('Pádel por la mañana'))


class CalculoTests(TuHistoriaBase):
    def setUp(self):
        super().setUp()
        self.e1 = self.entreno(date(2025, 10, 6), 50000, 50, 'Dia 1 - Hipertrofia_Final')
        self.entreno(date(2025, 10, 8), 64000, 40)
        self.entreno(date(2025, 11, 3), 30000, None)  # sin duración
        self.e4 = self.entreno(date(2026, 10, 5), 150000, 70)
        self.e5 = self.entreno(date(2026, 10, 7), 130000, 80)
        self.entreno(date(2026, 11, 9), 13950, 60)
        EjercicioBase.objects.create(nombre='Jalón al Pecho', grupo_muscular='espalda')
        EjercicioRealizado.objects.create(entreno=self.e5, nombre_ejercicio='jalon al pecho', series=4)
        EjercicioRealizado.objects.create(entreno=self.e4, nombre_ejercicio='JALÓN AL PECHO ', series=3)
        EjercicioRealizado.objects.create(entreno=self.e4, nombre_ejercicio='Curl Martillo', series=3)

    def test_totales(self):
        h = calcular_historia(self.cliente, HOY)
        self.assertEqual(h['primera']['fecha'], '6 de octubre de 2025')
        self.assertEqual(h['primera']['nombre'], 'Dia 1 - Hipertrofia_Final')
        self.assertEqual(h['primera']['id'], self.e1.id)
        self.assertEqual(h['sesiones'], 6)
        self.assertEqual(h['dias'], 6)
        self.assertEqual(h['toneladas'], '438')
        # 300 min conocidos + 1 sesión estimada con la media (60) = 6 h
        self.assertEqual(h['horas'], 6)
        self.assertEqual(h['horas_estimadas'], 1)

    def test_mosaico_y_constancia(self):
        h = calcular_historia(self.cliente, HOY)
        self.assertEqual(h['meses_total'], 14)
        self.assertEqual(h['meses_con_entreno'], 4)
        octubre = h['mosaico'][0]
        self.assertEqual(octubre['etiqueta'], 'oct 25')
        self.assertEqual(octubre['dias'], 2)
        self.assertEqual(octubre['lista'], '6, 8')
        self.assertEqual(octubre['puntos'][4], 'fuera')   # 5-oct, antes del primero
        self.assertEqual(octubre['puntos'][5], 'si')      # 6-oct
        self.assertEqual(octubre['puntos'][6], 'no')      # 7-oct
        self.assertEqual(h['mosaico'][-1]['puntos'][14], 'fuera')  # 15-nov, futuro
        self.assertEqual(h['racha_semanas'], 1)

    def test_la_vuelta_es_la_pausa_mas_larga(self):
        v = calcular_historia(self.cliente, HOY)['vuelta']
        # 3-nov-2025 → 5-oct-2026: 335 días sin gym en los datos de prueba
        self.assertEqual(v['dias'], 335)
        self.assertEqual(v['vuelta']['id'], self.e4.id)
        self.assertTrue(v['larga'])

    def test_compara_el_ultimo_mes_completo_con_el_de_hace_un_anio(self):
        c = calcular_historia(self.cliente, HOY)['comparacion']
        self.assertEqual((c['antes_mes'], c['ahora_mes']), ('Octubre 2025', 'Octubre 2026'))
        self.assertEqual((c['antes_t'], c['ahora_t']), ('114', '280'))
        self.assertEqual(c['factor'], '2,5')

    def test_ejercicio_agrupa_variantes_y_usa_el_nombre_del_catalogo(self):
        ej = calcular_historia(self.cliente, HOY)['ejercicio']
        self.assertEqual(ej['nombre'], 'Jalón al Pecho')
        self.assertEqual((ej['entrenos'], ej['series']), (2, 7))
        self.assertEqual(ej['primera']['id'], self.e4.id)
        self.assertEqual(ej['ultima']['id'], self.e5.id)

    def test_sin_entrenos_no_hay_historia(self):
        EntrenoRealizado.objects.all().delete()
        self.assertIsNone(calcular_historia(self.cliente, HOY))


class EtapasYDescargaTests(TuHistoriaBase):
    def test_un_entreno_de_cada_etapa_y_la_descarga_respetada(self):
        d = date(2026, 9, 1)
        for k, kg in enumerate([10000, 12000, 11000, 13000]):
            self.entreno(d + timedelta(days=k), kg, 50, f'Dia {k + 1} - Fuerza — Avanzada')
        for k in range(3):
            self.entreno(d + timedelta(days=7 + k), 5000, 25, f'Dia {k + 1} - Descarga Activa')
        tipico = self.entreno(d + timedelta(days=14), 16000, 70, 'Dia 1 - Hipertrofia — Metabólica')
        EjercicioRealizado.objects.create(entreno=tipico, nombre_ejercicio='Prensa', series=4)
        self.entreno(d + timedelta(days=15), 18000, 70, 'Dia 2 - Hipertrofia — Metabólica')
        self.entreno(d + timedelta(days=16), 14000, 70, 'Dia 3 - Hipertrofia — Metabólica')
        h = calcular_historia(self.cliente, HOY)

        entonces, ahora = h['etapas']
        self.assertEqual(entonces['fase'], 'Fuerza — Avanzada')
        self.assertFalse(entonces['ahora'])
        self.assertEqual(ahora['fase'], 'Hipertrofia — Metabólica')
        self.assertEqual(ahora['entreno']['id'], tipico.id)  # la mediana en volumen
        self.assertEqual(ahora['ejercicios'], [{'nombre': 'Prensa', 'series': 4}])

        desc = h['descarga']
        self.assertEqual((desc['desde'], desc['hasta'], desc['sesiones']), ('8 de septiembre', '10 de septiembre', 3))
        self.assertEqual(desc['bajada'], 57)  # 5.000 frente a 11.500 de media
        self.assertEqual(desc['vuelta']['id'], tipico.id)


class SerieNormalTests(TuHistoriaBase):
    def setUp(self):
        super().setUp()
        self.base = EjercicioBase.objects.create(nombre='Press Inclinado con Mancuernas', grupo_muscular='pecho')

    def serie(self, entreno, peso, reps, rpe):
        SerieRealizada.objects.create(
            entreno=entreno, ejercicio=self.base, serie_numero=1, repeticiones=reps,
            peso_kg=Decimal(peso), rpe_real=rpe, completado=True,
        )

    def test_encuentra_la_serie_que_hoy_cuesta_menos(self):
        antigua = self.entreno(date(2026, 8, 1), 9000)
        self.serie(antigua, 30, 12, 10)
        reciente = self.entreno(date(2026, 11, 10), 9000)
        self.serie(reciente, 30, 13, 8)
        s = calcular_historia(self.cliente, HOY)['serie_normal']
        self.assertEqual(s['ejercicio'], 'Press Inclinado con Mancuernas')
        self.assertEqual((s['antes']['peso'], s['antes']['reps'], s['antes']['rpe']), ('30', 12, '10'))
        self.assertEqual((s['ahora']['peso'], s['ahora']['reps'], s['ahora']['rpe']), ('30', 13, '8'))
        self.assertEqual(s['ahora']['id'], reciente.id)

    def test_sin_margen_suficiente_no_hay_pantalla(self):
        antigua = self.entreno(date(2026, 8, 1), 9000)
        self.serie(antigua, 30, 12, 9)
        reciente = self.entreno(date(2026, 11, 10), 9000)
        self.serie(reciente, 30, 12, 8.5)  # solo medio punto menos
        self.assertIsNone(calcular_historia(self.cliente, HOY)['serie_normal'])


class VistaTests(TuHistoriaBase):
    def setUp(self):
        super().setUp()
        self.entreno(date(2025, 10, 6), 50000, 50)
        self.client.force_login(self.user)
        self.url = reverse('entrenos:tu_historia', args=[self.cliente.id])

    def test_pagina_y_acceso_desde_memoria(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '6 de octubre de 2025')
        self.assertContains(r, 'Guardar mi frase')
        memoria = self.client.get(reverse('clientes:memoria_entrenador', args=[self.cliente.id]))
        self.assertContains(memoria, self.url)

    def test_otro_usuario_no_ve_ni_escribe(self):
        otro = User.objects.create_user(username='otro', password='x')
        self.client.force_login(otro)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'accion': 'frase', 'texto': 'x'}).status_code, 404)
        self.assertFalse(NotaHistoria.objects.exists())

    def test_sin_entrenos_la_pagina_no_falla(self):
        EntrenoRealizado.objects.all().delete()
        self.assertContains(self.client.get(self.url), 'Todavía no hay entrenos registrados')

    def test_frase_se_guarda_y_se_cambia_sin_duplicarse(self):
        r = self.client.post(self.url, {'accion': 'frase', 'texto': 'Lo estaba haciendo mejor de lo que pensaba'})
        self.assertRedirects(r, f'{self.url}?ir=frase', fetch_redirect_response=False)
        self.client.post(self.url, {'accion': 'frase', 'texto': 'Otra'})
        self.assertEqual(NotaHistoria.objects.filter(tipo='frase').count(), 1)
        self.assertContains(self.client.get(self.url), 'Otra')

    def test_carta_queda_sellada_con_las_cifras_del_momento(self):
        self.client.post(self.url, {'accion': 'carta', 'texto': 'Texto secreto para el futuro'})
        carta = NotaHistoria.objects.get(tipo='carta')
        self.assertIsNone(carta.abrir_en)
        self.assertEqual(carta.cifras['dias'], 1)
        r = self.client.get(self.url)
        self.assertNotContains(r, 'Texto secreto para el futuro')
        self.assertContains(r, 'Cuándo se abre está por decidir')

    def test_carta_con_fecha_cumplida_se_abre_al_principio(self):
        NotaHistoria.objects.create(
            cliente=self.cliente, tipo='carta', texto='Hola, David del futuro',
            abrir_en=date.today(), cifras={'dias': 1},
        )
        self.assertContains(self.client.get(self.url), 'Hola, David del futuro')

    def test_congelar_la_edicion_y_abrirla_tal_cual(self):
        self.client.post(self.url, {'accion': 'frase', 'texto': 'Mi frase'})
        anio = date.today().year
        r = self.client.post(self.url, {'accion': 'congelar'})
        self.assertRedirects(r, f'{self.url}?edicion={anio}', fetch_redirect_response=False)
        edicion = EdicionHistoria.objects.get(cliente=self.cliente, anio=anio)
        self.assertEqual(edicion.datos['frase'], 'Mi frase')
        # Un entreno nuevo no cambia la edición guardada.
        self.entreno(date.today(), 9999, 45)
        self.client.post(self.url, {'accion': 'congelar'})
        self.assertEqual(EdicionHistoria.objects.count(), 1)
        congelada = self.client.get(f'{self.url}?edicion={anio}')
        self.assertContains(congelada, f'Edición {anio}')
        self.assertContains(congelada, 'Mi frase')
        self.assertNotContains(congelada, 'Sellar la carta')
        self.assertEqual(self.client.get(f'{self.url}?edicion=1999').status_code, 404)
