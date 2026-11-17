"""17-nov-2026 · Lentitud: la memoria de una petición (core.memo_peticion) y el registro de peticiones lentas."""

from datetime import timedelta

from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone

from core import memo_peticion
from core.lentitud_middleware import PeticionesLentasMiddleware, _escribe


class MemoriaDeUnaPeticion(SimpleTestCase):
    def setUp(self):
        self.llamadas = []

        @memo_peticion.por_peticion
        def leer(cliente_id, extra=None):
            self.llamadas.append((cliente_id, extra))
            return {'valor': [cliente_id]}

        self.leer = leer

    def tearDown(self):
        memo_peticion.terminar()

    def test_fuera_de_una_peticion_no_memoriza(self):
        self.leer(1)
        self.leer(1)
        self.assertEqual(len(self.llamadas), 2)

    def test_dentro_de_una_peticion_repite_una_sola_vez(self):
        memo_peticion.iniciar()
        self.leer(1)
        self.leer(1)
        self.leer(2)
        self.leer(1, extra='x')
        self.assertEqual(self.llamadas, [(1, None), (2, None), (1, 'x')])

    def test_lo_devuelto_se_copia(self):
        memo_peticion.iniciar()
        self.leer(1)['valor'].append(99)
        self.assertEqual(self.leer(1), {'valor': [1]})

    def test_invalidar_vacia_la_memoria(self):
        memo_peticion.iniciar()
        self.leer(1)
        memo_peticion.invalidar()
        self.leer(1)
        self.assertEqual(len(self.llamadas), 2)

    def test_al_terminar_la_peticion_no_queda_nada(self):
        memo_peticion.iniciar()
        self.leer(1)
        memo_peticion.terminar()
        memo_peticion.iniciar()
        self.leer(1)
        self.assertEqual(len(self.llamadas), 2)

    def test_argumento_no_hashable_no_rompe(self):
        memo_peticion.iniciar()
        self.leer([1, 2])
        self.leer([1, 2])
        self.assertEqual(len(self.llamadas), 2)

    def test_que_sentencias_cuentan_como_escritura(self):
        self.assertFalse(_escribe('SELECT 1'))
        self.assertFalse(_escribe('  select * from x'))
        self.assertFalse(_escribe('SAVEPOINT s1'))
        self.assertFalse(_escribe('RELEASE SAVEPOINT s1'))
        for sql in ('INSERT INTO t VALUES (1)', 'UPDATE t SET a=1', 'DELETE FROM t', 'ROLLBACK TO SAVEPOINT s1'):
            self.assertTrue(_escribe(sql), sql)


class MemoriaYEscrituras(TestCase):
    """Con el middleware real: una escritura en medio hace que la lectura siguiente vea lo nuevo."""

    def test_una_escritura_en_la_peticion_invalida_la_lectura_memorizada(self):
        from django.contrib.auth.models import User

        lecturas = []

        @memo_peticion.por_peticion
        def contar_usuarios():
            lecturas.append(1)
            return User.objects.count()

        def vista(request):
            antes = contar_usuarios()
            contar_usuarios()  # memorizada: no consulta
            User.objects.create_user(username='nuevo_lentitud', password='x')
            despues = contar_usuarios()  # tras la escritura: vuelve a leer
            request.resultado = (antes, despues)
            return type('R', (), {'status_code': 200})()

        peticion = RequestFactory().get('/x/')
        PeticionesLentasMiddleware(vista)(peticion)
        self.assertEqual(peticion.resultado[1], peticion.resultado[0] + 1)
        self.assertEqual(len(lecturas), 2)
        self.assertIsNone(memo_peticion._memo.get())  # la memoria muere con la petición

    def test_las_restricciones_por_lesion_se_leen_una_vez_por_peticion(self):
        from django.contrib.auth.models import User
        from clientes.models import Cliente
        from core.bio_context import BioContextProvider

        cliente, _ = Cliente.objects.get_or_create(user=User.objects.create_user(username='lent', password='x'),
                                                   defaults={'nombre': 'L'})

        def vista(request):
            with self.assertNumQueries(1):
                for _ in range(20):
                    BioContextProvider.get_current_restrictions(cliente)
            return type('R', (), {'status_code': 200})()

        PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/'))


class MemoriaConTopeYExcepcion(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from clientes.models import Cliente

        user = User.objects.create_user(username='tope_lent', password='x')
        self.cliente, _ = Cliente.objects.get_or_create(user=user, defaults={'nombre': 'T'})

    def test_un_tope_cambiado_en_la_misma_peticion_se_ve_en_la_lectura_siguiente(self):
        from entrenos.models import TopeMaquinaGym
        from entrenos.services.maquina_service import _clave, tope_de

        TopeMaquinaGym.objects.create(cliente=self.cliente, ejercicio_normalizado=_clave('Prensa de Piernas'),
                                      peso_max_kg=100)
        vistos = []

        def vista(request):
            vistos.append(tope_de(self.cliente, 'Prensa de Piernas'))
            vistos.append(tope_de(self.cliente, 'Prensa de Piernas'))  # memorizada
            TopeMaquinaGym.objects.filter(cliente=self.cliente).update(peso_max_kg=120)  # update masivo, sin señales
            vistos.append(tope_de(self.cliente, 'Prensa de Piernas'))
            return type('R', (), {'status_code': 200})()

        PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/'))
        self.assertEqual(vistos, [100.0, 100.0, 120.0])

    def test_la_siguiente_peticion_lee_de_nuevo_las_restricciones_vigentes(self):
        from hyrox.models import UserInjury
        from core.bio_context import BioContextProvider

        def lectura(request):
            request.tags = set(BioContextProvider.get_current_restrictions(self.cliente)['tags'])
            return type('R', (), {'status_code': 200})()

        p1 = RequestFactory().get('/x/')
        PeticionesLentasMiddleware(lectura)(p1)
        self.assertEqual(p1.tags, set())
        UserInjury.objects.create(cliente=self.cliente, zona_afectada='rodilla', fase=UserInjury.Fase.AGUDA,
                                  activa=True, tags_restringidos=['impacto_vertical'],
                                  fecha_inicio=timezone.localdate(), gravedad=2)
        p2 = RequestFactory().get('/x/')
        PeticionesLentasMiddleware(lectura)(p2)
        self.assertIn('impacto_vertical', p2.tags)

    def test_si_la_vista_falla_la_memoria_tambien_se_descarta(self):
        def vista(request):
            memo_peticion._memo.get()['clave'] = 'algo'
            raise RuntimeError('fallo de la vista')

        with self.assertRaises(RuntimeError):
            PeticionesLentasMiddleware(vista)(RequestFactory().get('/x/'))
        self.assertIsNone(memo_peticion._memo.get())
