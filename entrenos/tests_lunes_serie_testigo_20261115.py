"""15-nov-2026 · El lunes 16 de punta a punta: la sesión abre la serie testigo, se registra y no vuelve a salir."""

import json
from datetime import date

from django.core.cache import cache
from django.urls import reverse

from entrenos.models import ProtocoloTestigo, SerieTestigo
from entrenos.tests_serie_testigo_20261108 import Base

LUNES = date(2026, 11, 16)


class LunesDeSerieTestigo(Base):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.jalon(date(2026, 10, 20), 60, 12)
        self.client.force_login(self.user)

    def abrir(self, fecha=LUNES):
        url = reverse('entrenos:entrenamiento_activo', args=[self.cliente.id])
        return self.client.get(url, {'fecha': fecha.isoformat(), 'rutina_nombre': 'Día 1 - Fuerza'})

    def test_el_lunes_sale_el_bloque_con_el_peso_fijo(self):
        r = self.abrir()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="serie-testigo"')
        self.assertContains(r, 'Jalón al Pecho')
        p = ProtocoloTestigo.objects.get()
        self.assertEqual((p.dia_semana, p.rep_pregunta), (0, 8))

    def test_registrar_y_ya_no_vuelve_a_salir(self):
        self.abrir()
        r = self.client.post(
            reverse('entrenos:registrar_serie_testigo', args=[self.cliente.id]),
            json.dumps({'fecha': LUNES.isoformat(), 'reps': '14', 'quedaban': '4'}),
            content_type='application/json',
        )
        self.assertTrue(r.json()['ok'])
        self.assertIn('14 repeticiones', r.json()['msg'])
        self.assertEqual(SerieTestigo.objects.get().reps, 14)
        self.assertNotContains(self.abrir(), 'id="serie-testigo"')

    def test_otro_dia_no_sale(self):
        self.assertNotContains(self.abrir(date(2026, 11, 17)), 'id="serie-testigo"')

    def test_sin_jalon_en_el_historial_no_sale(self):
        from entrenos.models import EntrenoRealizado
        EntrenoRealizado.objects.filter(cliente=self.cliente).delete()
        self.assertNotContains(self.abrir(), 'id="serie-testigo"')
