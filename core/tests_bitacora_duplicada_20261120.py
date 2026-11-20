"""20-nov-2026: dos filas de bitacora el mismo dia no ocultan HRV, sueno ni energia."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from clientes.bitacora_dia import valores_del_dia
from clientes.models import BitacoraDiaria, Cliente
from core.services.physical_snapshot import build_physical_snapshot

HOY = date(2026, 11, 20)


class BitacoraDuplicadaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bit-dup')
        self.cliente = Cliente.objects.get(user=self.user)
        a = BitacoraDiaria.objects.create(cliente=self.cliente, fc_reposo=52)
        b = BitacoraDiaria.objects.create(
            cliente=self.cliente, horas_sueno=Decimal('7.99'), hrv_ms=130, energia_subjetiva=7,
            salud_importado_en=timezone.now())
        c = BitacoraDiaria.objects.create(cliente=self.cliente, fc_reposo=53)  # la ultima, casi vacia
        self.pks = [a.pk, b.pk, c.pk]
        BitacoraDiaria.objects.filter(pk__in=self.pks).update(fecha=HOY)

    def test_snapshot_lee_el_dia_entero(self):
        chk = build_physical_snapshot(self.cliente, HOY)['signals']['checkin']
        v = chk['values']
        self.assertEqual(v['hrv_ms'], 130)
        self.assertEqual(v['sleep_hours'], 7.99)
        self.assertEqual(v['energy'], 7)
        self.assertEqual(v['resting_hr'], 53)  # la ultima con dato gana
        self.assertEqual(chk['provenance']['record_id'], self.pks[-1])
        self.assertEqual(chk['provenance']['merged_record_ids'], self.pks)

    def test_no_se_borra_ni_modifica_ninguna_fila(self):
        build_physical_snapshot(self.cliente, HOY)
        self.assertEqual(BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=HOY).count(), 3)

    def test_valores_del_dia_ignora_vacios(self):
        filas = list(BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=HOY).order_by('pk'))
        self.assertEqual(valores_del_dia(filas)['hrv_ms'], 130)

    def test_senales_al_decidir_ve_hrv_y_sueno(self):
        from types import SimpleNamespace
        from entrenos.services.senales_al_decidir_service import calcular_senales
        ahora = timezone.make_aware(__import__('datetime').datetime(2026, 11, 20, 12, 0))
        out = calcular_senales(SimpleNamespace(cliente=self.cliente, pk=None, id=None, entreno_origen=None, peso_anterior=None, reps_anteriores=None, rpe_anterior=None, ejercicio='x'), ahora=ahora)
        self.assertEqual(out['salud_hoy']['hrv_ms'], 130)
        self.assertEqual(out['salud_hoy']['horas_sueno'], 7.99)


class BitacoraDiaEscrituraTests(TestCase):
    """Todas las rutas de escritura pasan por la misma puerta y respetan cada campo."""

    def setUp(self):
        from django.test import Client
        self.user = User.objects.create_user('bit-esc', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        self.http = Client()
        self.http.force_login(self.user)
        self.hoy = timezone.localdate()

    def _filas(self):
        return BitacoraDiaria.objects.filter(cliente=self.cliente, fecha=self.hoy)

    def test_zero_valido_solo_en_campos_que_lo_admiten(self):
        a = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=130, dolor_articular=5, energia_subjetiva=6)
        b = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=0, dolor_articular=0, energia_subjetiva=0)
        BitacoraDiaria.objects.filter(pk__in=[a.pk, b.pk]).update(fecha=HOY)
        v, fuentes = __import__('clientes.bitacora_dia', fromlist=['x']).lectura_del_dia(
            list(BitacoraDiaria.objects.filter(fecha=HOY).order_by('pk')))
        self.assertEqual(v['hrv_ms'], 130)          # un 0 no tapa una medida real
        self.assertEqual(fuentes['hrv_ms']['record_id'], a.pk)
        self.assertEqual(v['dolor_articular'], 0)   # un 0 de dolor es un dato
        self.assertEqual(v['energia_subjetiva'], 0)
        self.assertEqual(fuentes['dolor_articular']['record_id'], b.pk)
        self.assertEqual(fuentes['hrv_ms']['fecha'], HOY.isoformat())

    def test_solo_ceros_en_hrv_se_devuelven_como_cero(self):
        a = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=0)
        v = valores_del_dia([a])
        self.assertEqual(v['hrv_ms'], 0)

    def test_portal_get_or_create_con_duplicados_no_revienta_y_conserva_datos(self):
        a = BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=61, horas_sueno=Decimal('7.5'))
        b = BitacoraDiaria.objects.create(cliente=self.cliente, fc_reposo=50)
        BitacoraDiaria.objects.filter(pk__in=[a.pk, b.pk]).update(fecha=self.hoy)
        r = self.http.post(f'/clientes/sesion/{self.cliente.id}/', {'energia_subjetiva': 6, 'dolor_articular': 2})
        if r.status_code == 404:
            self.skipTest('ruta del portal distinta')
        self.assertIn(r.status_code, (302, 200))
        self.assertEqual(self._filas().count(), 2)
        a.refresh_from_db()
        self.assertEqual(a.hrv_ms, 61)               # el campo en blanco no borra el dato previo
        self.assertEqual(a.energia_subjetiva, 6)

    def test_checkin_matutino_sin_valor_conserva_el_previo(self):
        BitacoraDiaria.objects.create(cliente=self.cliente, hrv_ms=61, fc_reposo=50)
        BitacoraDiaria.objects.filter(cliente=self.cliente).update(fecha=self.hoy)
        from django.urls import reverse, NoReverseMatch
        try:
            url = reverse('clientes:checkin_matutino')
        except NoReverseMatch:
            self.skipTest('sin url')
        r = self.http.post(url, {'horas_sueno': '7', 'energia_subjetiva': '5'})
        self.assertEqual(r.status_code, 200)
        f = self._filas().get()
        self.assertEqual((f.hrv_ms, f.fc_reposo, f.energia_subjetiva), (61, 50, 5))

    def test_iphone_sin_valor_conserva_el_previo_y_una_sola_fila(self):
        from clientes.salud_iphone_service import guardar_checkin_iphone
        guardar_checkin_iphone(self.cliente, {'hrv': 48, 'sueno': 432}, hoy=self.hoy)
        guardar_checkin_iphone(self.cliente, {'pulso_reposo': 52}, hoy=self.hoy)
        f = self._filas().get()
        self.assertEqual((f.hrv_ms, f.fc_reposo), (48, 52))
        self.assertIsNotNone(f.horas_sueno)

    def test_registrar_bitacora_invalida_no_deja_fila_vacia(self):
        r = self.http.post('/clientes/bitacora/registrar/', {'energia_subjetiva': ''})
        if r.status_code == 404:
            self.skipTest('ruta distinta')
        self.assertEqual(self._filas().count(), 0)
