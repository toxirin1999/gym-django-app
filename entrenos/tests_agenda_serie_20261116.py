"""16-nov-2026 · Nota 27 (la serie testigo se ajusta sola) y agenda de pendientes con fecha."""

import json
import tempfile
from datetime import date, timedelta

from django.test import SimpleTestCase
from django.urls import reverse

from core import pendientes
from entrenos.models import ProtocoloTestigo, SerieTestigo
from entrenos.services import serie_testigo_service as st
from entrenos.tests_serie_testigo_20261108 import Base

L16 = date(2026, 11, 16)
L23 = date(2026, 11, 23)


class AjusteDeLaSerieTestigo(Base):
    def setUp(self):
        super().setUp()
        self.jalon(date(2026, 10, 20), 60, 12)  # protocolo de 57,5 kg
        self.p1 = st.protocolo_vigente(self.cliente, L16)
        ProtocoloTestigo.objects.filter(pk=self.p1.pk).update(peso_kg=52.5)
        self.p1.refresh_from_db()

    def test_peso_ajustado_a_partir_de_22_reps_con_52_5(self):
        self.assertEqual(st.peso_ajustado(52.5, 22), 62.5)

    def test_el_mismo_dia_no_cambia_el_protocolo(self):
        st.registrar(self.cliente, L16, 22, 4)
        self.assertEqual(st.protocolo_vigente(self.cliente, L16).pk, self.p1.pk)

    def test_el_lunes_siguiente_parte_de_peso_nuevo_y_la_referencia_empieza_ahi(self):
        st.registrar(self.cliente, L16, 22, 4)
        p2 = st.protocolo_vigente(self.cliente, L23)
        self.assertNotEqual(p2.pk, self.p1.pk)
        self.assertEqual((p2.peso_kg, p2.desde), (62.5, L23))
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.hasta, L23 - timedelta(days=1))
        # la de hoy se corrige con su protocolo, y no entra en la referencia nueva
        self.assertEqual(st.protocolo_vigente(self.cliente, L16).pk, self.p1.pk)
        st.registrar(self.cliente, L23, 13, 5)
        res = st.resumen(self.cliente)
        self.assertEqual(res['protocolo'].pk, p2.pk)
        self.assertEqual(res['faltan_para_referencia'], 2)

    def test_una_serie_cerca_del_objetivo_no_ajusta(self):
        st.registrar(self.cliente, L16, 14, 4)
        self.assertEqual(st.protocolo_vigente(self.cliente, L23).pk, self.p1.pk)

    def test_con_dos_series_ya_no_se_reajusta(self):
        st.registrar(self.cliente, L16, 22, 4)
        p2 = st.protocolo_vigente(self.cliente, L23)
        st.registrar(self.cliente, L23, 22, 4)  # aunque otra vez salga lejos, no hay reajuste en cadena
        self.assertEqual(st.protocolo_vigente(self.cliente, L23 + timedelta(days=7)).pk, p2.pk)

    def test_la_frase_de_la_primera_avisa_del_ajuste(self):
        s = st.registrar(self.cliente, L16, 22, 4)
        frase = st.frase_serie(s, st.resumen(self.cliente))
        self.assertIn('prueba de ajuste', frase)
        self.assertIn('62,5 kg', frase)


class AgendaDePendientes(SimpleTestCase):
    def _archivo(self, datos):
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(datos, f)
        f.close()
        return f.name

    def test_agrupa_por_fecha_y_estado(self):
        hoy = date(2026, 11, 16)
        ruta = self._archivo([
            {'titulo': 'ayer', 'fecha': '2026-11-15', 'estado': 'pendiente'},
            {'titulo': 'hoy', 'fecha': '2026-11-16'},
            {'titulo': 'miercoles', 'fecha': '2026-11-18'},
            {'titulo': 'lejos', 'fecha': '2026-12-07'},
            {'titulo': 'sin fecha', 'fecha': None},
            {'titulo': 'hecha', 'estado': 'hecho', 'hecho_el': '2026-11-14', 'fecha': '2026-11-14'},
        ])
        g = pendientes.agrupar(pendientes.cargar(ruta), hoy)
        self.assertEqual([t['titulo'] for t in g['vencidas']], ['ayer'])
        self.assertEqual([t['titulo'] for t in g['hoy']], ['hoy'])
        self.assertEqual([t['titulo'] for t in g['semana']], ['miercoles'])
        self.assertEqual([t['titulo'] for t in g['despues']], ['lejos'])
        self.assertEqual([t['titulo'] for t in g['sin_fecha']], ['sin fecha'])
        self.assertEqual([t['titulo'] for t in g['cerradas']], ['hecha'])
        self.assertEqual(pendientes.resumen(pendientes.cargar(ruta), hoy),
                         {'vencidas': 1, 'hoy': 1, 'pendientes': 5})

    def test_archivo_roto_o_ausente_no_rompe(self):
        self.assertEqual(pendientes.cargar('/no/existe.json'), [])
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        f.write('{no es json')
        f.close()
        self.assertEqual(pendientes.cargar(f.name), [])

    def test_el_archivo_real_es_valido_y_tiene_fechas_futuras_y_hechas(self):
        tareas = pendientes.cargar()
        self.assertGreater(len(tareas), 5)
        ids = [t['id'] for t in tareas]
        self.assertEqual(len(ids), len(set(ids)), 'ids repetidos')
        self.assertTrue(any(t['estado'] == 'hecho' for t in tareas))
        self.assertTrue(any(t['fecha'] for t in tareas if t['estado'] == 'pendiente'))


class PaginaDePendientes(Base):
    def test_exige_sesion_y_se_ve(self):
        url = reverse('clientes:agenda_pendientes')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pendientes')
        self.assertContains(r, 'Serie testigo con el peso nuevo')
