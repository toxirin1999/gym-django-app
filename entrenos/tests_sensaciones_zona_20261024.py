"""24-oct-2026 · Paso 3: bombeo / agujetas / molestia por zona al cierre."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from entrenos.models import PropuestaZonaGym, SensacionZonaGym
from entrenos.services import sensacion_zona_service as svc
from entrenos.services.propuesta_zona_service import generar_propuesta_si_procede
from entrenos.tests_ultima_sesion import Base

HOY = timezone.localdate()


class ConEntrenos(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.cliente.user)

    def sesion(self, dias_atras, *bases):
        e = self.entreno(HOY - timedelta(days=dias_atras), {b.nombre: '10-12' for b in bases})
        for b in bases:
            self.hacer(e, b, [(60, 10, 8), (60, 10, 8)])
        return e


class Servicio(ConEntrenos):
    def test_zonas_de_la_sesion_sin_repetir(self):
        e = self.sesion(0, self.hack, self.prensa, self.gemelos)
        self.assertEqual([z for z, _ in svc.zonas_de_entreno(e)], ['cuadriceps', 'gemelos'])

    def test_contexto_marca_lo_guardado(self):
        e = self.sesion(0, self.hack)
        svc.guardar(self.cliente, e, 'cuadriceps', 'bombeo', 2)
        fila = svc.contexto_cierre(e)[0]
        valores = {p['campo']: p['valor'] for p in fila['preguntas']}
        self.assertEqual(valores, {'bombeo': 2, 'agujetas': None, 'molestia': None})

    def test_guardar_valida(self):
        e = self.sesion(0, self.hack)
        with self.assertRaises(ValueError):
            svc.guardar(self.cliente, e, 'cuadriceps', 'bombeo', 3)
        with self.assertRaises(ValueError):
            svc.guardar(self.cliente, e, 'cuadriceps', 'dolor', 1)
        with self.assertRaises(ValueError):
            svc.guardar(self.cliente, e, 'biceps', 'bombeo', 1)  # no se trabajó hoy

    def test_una_mala_sesion_no_basta_para_bajar(self):
        e = self.sesion(2, self.hack)
        svc.guardar(self.cliente, e, 'cuadriceps', 'molestia', 2)
        self.assertIsNone(svc.zona_para_bajar(self.cliente, HOY))

    def test_dos_malas_en_14_dias_bajan(self):
        a, b = self.sesion(9, self.hack), self.sesion(2, self.hack)
        svc.guardar(self.cliente, a, 'cuadriceps', 'agujetas', 2)
        svc.guardar(self.cliente, b, 'cuadriceps', 'molestia', 1)
        d = svc.zona_para_bajar(self.cliente, HOY)
        self.assertEqual((d['zona'], d['sesiones']), ('cuadriceps', 2))

    def test_agujetas_leves_no_cuentan_y_fuera_de_ventana_tampoco(self):
        a, b = self.sesion(20, self.hack), self.sesion(2, self.hack)
        svc.guardar(self.cliente, a, 'cuadriceps', 'molestia', 2)
        svc.guardar(self.cliente, b, 'cuadriceps', 'agujetas', 1)
        self.assertIsNone(svc.zona_para_bajar(self.cliente, HOY))

    def test_frena_subir_mira_la_ultima_respuesta(self):
        a, b = self.sesion(6, self.hack), self.sesion(1, self.hack)
        svc.guardar(self.cliente, a, 'cuadriceps', 'molestia', 2)
        self.assertTrue(svc.frena_subir(self.cliente, 'cuadriceps', HOY))
        svc.guardar(self.cliente, b, 'cuadriceps', 'molestia', 0)
        self.assertFalse(svc.frena_subir(self.cliente, 'cuadriceps', HOY))


class Propuesta(ConEntrenos):
    def test_propuesta_de_bajar_cita_sesiones_y_fechas(self):
        a, b = self.sesion(9, self.hack), self.sesion(2, self.hack)
        svc.guardar(self.cliente, a, 'cuadriceps', 'molestia', 1)
        svc.guardar(self.cliente, b, 'cuadriceps', 'agujetas', 2)
        p = generar_propuesta_si_procede(self.cliente, HOY)
        self.assertIsNotNone(p)
        self.assertEqual((p.zona, p.direccion), ('cuadriceps', PropuestaZonaGym.DIRECCION_BAJAR))
        self.assertIn('2 sesiones', p.texto)
        self.assertIn(a.fecha.strftime('%d/%m'), p.texto)
        self.assertIn('Sentadilla Hack', p.ejercicios)

    def test_sin_sensaciones_no_hay_propuesta(self):
        self.sesion(2, self.hack)
        self.assertIsNone(generar_propuesta_si_procede(self.cliente, HOY))


class Pantalla(ConEntrenos):
    def test_cierre_muestra_las_zonas(self):
        e = self.sesion(0, self.hack, self.gemelos)
        r = self.client.get(reverse('entrenos:post_entreno_resumen', args=[self.cliente.id, e.id]))
        self.assertContains(r, '¿Cómo respondió el músculo?')
        self.assertContains(r, 'data-zona="cuadriceps"')
        self.assertContains(r, 'data-zona="gemelos"')
        self.assertContains(r, 'Agujetas de la vez anterior')

    def test_endpoint_guarda_y_responde(self):
        e = self.sesion(0, self.hack)
        url = reverse('entrenos:guardar_sensacion_zona', args=[self.cliente.id, e.id])
        r = self.client.post(url, {'zona': 'cuadriceps', 'campo': 'molestia', 'valor': '1'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertEqual(SensacionZonaGym.objects.get(entreno=e, zona='cuadriceps').molestia, 1)
        # Cambiar la respuesta pisa la anterior, no duplica.
        self.client.post(url, {'zona': 'cuadriceps', 'campo': 'molestia', 'valor': '0'})
        self.assertEqual(SensacionZonaGym.objects.filter(entreno=e).count(), 1)
        self.assertEqual(SensacionZonaGym.objects.get(entreno=e).molestia, 0)

    def test_endpoint_rechaza_basura_y_get(self):
        e = self.sesion(0, self.hack)
        url = reverse('entrenos:guardar_sensacion_zona', args=[self.cliente.id, e.id])
        self.assertEqual(self.client.post(url, {'zona': 'cuadriceps', 'campo': 'bombeo', 'valor': 'x'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'zona': 'cuadriceps', 'campo': 'bombeo', 'valor': '7'}).status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_endpoint_no_deja_tocar_entrenos_ajenos(self):
        from django.contrib.auth.models import User
        e = self.sesion(0, self.hack)
        otro = User.objects.create_user(username='otro_sens', password='x')
        self.client.force_login(otro)
        url = reverse('entrenos:guardar_sensacion_zona', args=[self.cliente.id, e.id])
        r = self.client.post(url, {'zona': 'cuadriceps', 'campo': 'bombeo', 'valor': '1'})
        self.assertEqual(r.status_code, 404)
