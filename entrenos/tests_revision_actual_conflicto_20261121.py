"""Etapa 3: «Aplicar la mía encima» se apoya en la revisión ACTUAL del servidor.

Si otro dispositivo cambia la sesión entre que ves el conflicto y pulsas aplicar,
el servidor no pisa nada: devuelve un conflicto nuevo con la huella vigente, y solo
entonces vale aplicarla.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import CorreccionSesionGym, EntrenoRealizado
from rutinas.models import EjercicioBase

NOMBRE = 'Press Banca Revision'
TOKEN = 'tokenRRRRRRRRRRRRRRR1'


def datos(reps=('8', '8'), **extra):
    d = {
        'fecha': date.today().isoformat(), 'rutina_nombre': 'Dia Revision',
        'sesion_token': TOKEN, 'ej1_nombre': NOMBRE, 'ej1_tipo_progresion': 'peso_reps',
        'duracion_minutos_real': '50',
    }
    for i, (p, r) in enumerate(zip(('60', '62.5'), reps), start=1):
        d.update({f'ej1_peso_{i}': p, f'ej1_reps_{i}': r, f'ej1_rpe_{i}': '8', f'ej1_completado_{i}': '1'})
    d.update(extra)
    return d


class AplicarLaMiaConRevisionActual(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('revision21', password='x')
        self.cliente = Cliente.objects.get(user=self.user)
        EjercicioBase.objects.create(nombre=NOMBRE, grupo_muscular='pecho')
        self.client.force_login(self.user)
        self.url = reverse('entrenos:guardar_entrenamiento_activo', args=[self.cliente.pk])

    def enviar(self, payload):
        return self.client.post(self.url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def entreno(self):
        return EntrenoRealizado.objects.get(cliente=self.cliente)

    def test_otro_cambio_entre_el_aviso_y_aplicar_vuelve_a_dar_conflicto_con_la_huella_vigente(self):
        h0 = self.enviar(datos()).json()['huella']
        # Otro dispositivo corrige (h0 -> h1).
        otro = datos(reps=('10', '10')); otro['bases_huella'] = h0
        h1 = self.enviar(otro).json()['huella']
        # Este móvil (que solo conocía h0) ve el conflicto y recibe h1 como vigente.
        mio = datos(reps=('7', '7')); mio['bases_huella'] = h0
        aviso = self.enviar(mio)
        self.assertEqual(aviso.status_code, 409)
        self.assertEqual(aviso.json()['huella'], h1)
        self.assertEqual(aviso.json()['revision'], 2)
        # Antes de que pulse «aplicar», un tercero cambia otra vez (h1 -> h2).
        tercero = datos(reps=('12', '12')); tercero['bases_huella'] = h1
        h2 = self.enviar(tercero).json()['huella']
        # «Aplicar la mía» con la huella que vio (h1): ya no es la vigente.
        mio['resolver_conflicto'] = h1
        r = self.enviar(mio)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['huella'], h2)
        self.assertEqual(r.json()['revision'], 3)
        self.assertEqual(self.entreno().huella_contenido, h2)  # nada pisado
        self.assertEqual(self.entreno().revision, 3)
        # Con la huella vigente sí se aplica, y queda registrado como conflicto resuelto.
        mio['resolver_conflicto'] = h2
        r = self.enviar(mio)
        self.assertEqual(r.status_code, 200)
        e = self.entreno()
        self.assertEqual(e.revision, 4)
        self.assertEqual(e.huella_contenido, r.json()['huella'])
        self.assertEqual(
            list(CorreccionSesionGym.objects.order_by('revision_resultante').values_list('origen', flat=True))[-1],
            'conflicto_resuelto')
