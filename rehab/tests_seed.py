from django.core.management import call_command
from django.test import TestCase

from rehab.models import EjercicioRehab, FaseProtocolo, PrescripcionEjercicio, ProtocoloRehab


class SeedProtocolosRehabTests(TestCase):
    def test_idempotente_no_duplica(self):
        call_command('seed_protocolos_rehab')

        conteos_antes = (
            ProtocoloRehab.objects.count(),
            FaseProtocolo.objects.count(),
            EjercicioRehab.objects.count(),
            PrescripcionEjercicio.objects.count(),
        )

        call_command('seed_protocolos_rehab')

        conteos_despues = (
            ProtocoloRehab.objects.count(),
            FaseProtocolo.objects.count(),
            EjercicioRehab.objects.count(),
            PrescripcionEjercicio.objects.count(),
        )

        self.assertEqual(conteos_antes, conteos_despues)

    def test_protocolo_tiene_tres_fases_en_orden_cook_purdam(self):
        call_command('seed_protocolos_rehab')

        protocolo = ProtocoloRehab.objects.get(slug='tendinopatia-rotuliana', activo=True)
        fases = list(protocolo.fases.order_by('orden'))

        self.assertEqual(len(fases), 3)
        self.assertIn('isometr', fases[0].slug)
        self.assertIn('isotonic', fases[1].slug)
        self.assertTrue(
            'pliometr' in fases[2].slug or 'almacenamiento' in fases[2].slug
        )

    def test_cada_fase_tiene_al_menos_una_prescripcion(self):
        call_command('seed_protocolos_rehab')

        protocolo = ProtocoloRehab.objects.get(slug='tendinopatia-rotuliana', activo=True)
        for fase in protocolo.fases.all():
            self.assertGreaterEqual(fase.prescripciones.count(), 1)
