from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from entrenos.models import (
    ContratoBloqueGym,
    ContratoSemanalGym,
    EntrenoRealizado,
    EstrategiaSemanalGym,
    EvaluacionBloqueGym,
    SesionProgramada,
)


class BloqueGymColaborativoCentroTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bloque-colaborativo", password="x")
        self.otro_user = User.objects.create_user("bloque-colaborativo-otro", password="x")
        self.cliente = Cliente.objects.get(user=self.user)
        self.otro = Cliente.objects.get(user=self.otro_user)
        self.inicio = date(2026, 8, 31)
        self.client.force_login(self.user)

    def datos(self, **extra):
        datos = {
            "semana_inicio": self.inicio.isoformat(),
            "semanas_previstas": "4",
            "objetivo_principal": "fuerza",
            "objetivos_secundarios": ["gemelos"],
            "motivo": "Preparar el siguiente bloque",
        }
        datos.update(extra)
        return datos

    def preparar(self, *, follow=False, **extra):
        return self.client.post(
            reverse("clientes:preparar_bloque_gym"), self.datos(**extra), follow=follow,
        )

    def test_get_no_muta_y_sin_bloque_ofrece_preparar(self):
        antes = (
            EstrategiaSemanalGym.objects.count(), ContratoBloqueGym.objects.count(),
            ContratoSemanalGym.objects.count(), SesionProgramada.objects.count(),
        )
        response = self.client.get(reverse("clientes:plan_decisiones"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preparar bloque Gym")
        self.assertEqual(antes, (
            EstrategiaSemanalGym.objects.count(), ContratoBloqueGym.objects.count(),
            ContratoSemanalGym.objects.count(), SesionProgramada.objects.count(),
        ))

    def test_preparar_resuelve_estrategia_canonica_y_no_materializa_plan(self):
        response = self.preparar()
        self.assertRedirects(response, reverse("clientes:plan_decisiones"))
        estrategia = EstrategiaSemanalGym.objects.get()
        bloque = ContratoBloqueGym.objects.get()
        self.assertEqual((estrategia.objetivo_sesiones, estrategia.minimo_valido), (5, 3))
        self.assertEqual(bloque.estrategia, estrategia)
        self.assertEqual(bloque.estado, "propuesto")
        self.assertEqual(bloque.objetivos_secundarios, ["gemelos"])
        self.assertEqual(bloque.motor_nombre, "Helms")
        self.assertEqual(bloque.limites_snapshot, {"sin_autoajustes": True})
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)
        self.assertEqual(SesionProgramada.objects.count(), 0)
        self.assertEqual(EntrenoRealizado.objects.count(), 0)

    def test_post_rechaza_campos_fuera_de_allowlist_y_lunes_invalido_con_prg(self):
        response = self.preparar(
            estrategia="999", motor_nombre="Otro", minimo_valido="1",
            limites_snapshot='{"privado": true}', cliente=str(self.otro.pk),
        )
        self.assertRedirects(response, reverse("clientes:plan_decisiones"))
        self.assertEqual(ContratoBloqueGym.objects.count(), 0)
        response = self.preparar(semana_inicio="2026-09-01")
        self.assertRedirects(response, reverse("clientes:plan_decisiones"))
        self.assertEqual(ContratoBloqueGym.objects.count(), 0)

    def test_propuesta_muestra_acciones_y_solo_datos_estructurados_seguros(self):
        self.preparar(motivo="NOTA-PRIVADA")
        bloque = ContratoBloqueGym.objects.get()
        response = self.client.get(reverse("clientes:plan_decisiones"))
        self.assertContains(response, "Bloque Gym propuesto")
        self.assertContains(response, "Ganancia de Fuerza")
        self.assertContains(response, "4 semanas")
        self.assertContains(response, "5 sesiones · mínimo 3")
        self.assertContains(response, reverse("clientes:activar_bloque_gym_colaborativo", args=[bloque.pk]))
        self.assertContains(response, reverse("clientes:revisar_bloque_gym_colaborativo", args=[bloque.pk]))
        self.assertContains(response, reverse("clientes:retirar_bloque_gym_colaborativo", args=[bloque.pk]))
        self.assertNotContains(response, bloque.fingerprint)
        self.assertNotContains(response, "NOTA-PRIVADA")
        self.assertNotContains(response, "sin_autoajustes")

    def test_activar_exige_version_y_propietario_sin_crear_semanas_ni_sesiones(self):
        self.preparar()
        bloque = ContratoBloqueGym.objects.get()
        url = reverse("clientes:activar_bloque_gym_colaborativo", args=[bloque.pk])
        response = self.client.post(url, {"version": bloque.version + 1}, follow=True)
        self.assertContains(response, "versión")
        bloque.refresh_from_db()
        self.assertEqual(bloque.estado, "propuesto")

        response = self.client.post(url, {"version": bloque.version})
        self.assertRedirects(response, reverse("clientes:plan_decisiones"))
        bloque.refresh_from_db()
        self.assertEqual(bloque.estado, "activo")
        self.assertEqual(bloque.aprobado_por, self.user)
        self.assertEqual(ContratoSemanalGym.objects.count(), 0)
        self.assertEqual(SesionProgramada.objects.count(), 0)
        self.assertEqual(EntrenoRealizado.objects.count(), 0)

        self.client.force_login(self.otro_user)
        self.assertEqual(self.client.post(url, {"version": bloque.version}).status_code, 404)

    def test_revision_crea_sucesora_y_retira_anterior_atomicamente(self):
        self.preparar()
        anterior = ContratoBloqueGym.objects.get()
        url = reverse("clientes:revisar_bloque_gym_colaborativo", args=[anterior.pk])
        datos = self.datos(semanas_previstas="6", version=str(anterior.version))
        response = self.client.post(url, datos)
        self.assertRedirects(response, reverse("clientes:plan_decisiones"))
        anterior.refresh_from_db()
        sucesora = ContratoBloqueGym.objects.exclude(pk=anterior.pk).get()
        self.assertEqual(anterior.estado, "retirado")
        self.assertEqual(sucesora.estado, "propuesto")
        self.assertEqual(sucesora.predecesor, anterior)
        self.assertEqual(sucesora.version, anterior.version + 1)
        self.assertEqual(sucesora.semanas_previstas, 6)

        # Repetir sobre la versión retirada no crea otra sucesora.
        response = self.client.post(url, datos, follow=True)
        self.assertContains(response, "Solo una propuesta")
        self.assertEqual(ContratoBloqueGym.objects.count(), 2)

    def test_retirar_solo_propuesta_y_objeto_ajeno_es_404(self):
        self.preparar()
        bloque = ContratoBloqueGym.objects.get()
        url = reverse("clientes:retirar_bloque_gym_colaborativo", args=[bloque.pk])
        self.client.post(url, {"version": bloque.version})
        bloque.refresh_from_db()
        self.assertEqual(bloque.estado, "retirado")
        self.client.post(url, {"version": bloque.version}, follow=True)
        self.assertEqual(ContratoBloqueGym.objects.count(), 1)

        estrategia_ajena = EstrategiaSemanalGym.objects.create(
            cliente=self.otro, version=1, objetivo_sesiones=5, minimo_valido=3,
            vigente_desde=self.inicio, aprobado_por=self.otro_user,
        )
        ajeno = ContratoBloqueGym.objects.create(
            cliente=self.otro, version=1, estado="propuesto", semana_inicio=self.inicio,
            semanas_previstas=4, semana_fin_prevista=self.inicio + timedelta(days=27),
            estrategia=estrategia_ajena, objetivo_sesiones=5, minimo_valido=3,
            objetivo_principal="fuerza", objetivos_secundarios=[], limites_snapshot={},
            motor_nombre="Helms", motor_version="actual", fingerprint="ajeno-colaborativo",
        )
        self.assertEqual(self.client.post(
            reverse("clientes:retirar_bloque_gym_colaborativo", args=[ajeno.pk]),
            {"version": 1},
        ).status_code, 404)

    def test_cierre_pendiente_bloquea_nueva_preparacion(self):
        self.preparar()
        bloque = ContratoBloqueGym.objects.get()
        bloque.estado = "finalizado"
        bloque.save(update_fields=["estado", "actualizado_en"])
        EvaluacionBloqueGym.objects.create(
            bloque=bloque, version_calculo=1, fingerprint_evidencia="pendiente-colab",
            estado_resultado=EvaluacionBloqueGym.RESULTADO_MINIMO,
            evidencia_snapshot={}, estado_revision=EvaluacionBloqueGym.REVISION_PENDIENTE,
        )
        response = self.preparar(
            semana_inicio="2026-09-28", motivo="No debe crearse", follow=True,
        )
        self.assertContains(response, "cierre del bloque pendiente")
        self.assertEqual(ContratoBloqueGym.objects.count(), 1)

    def test_preparar_no_compite_con_propuesta_o_bloque_ya_abierto(self):
        self.preparar()
        response = self.preparar(
            semana_inicio="2026-09-28", semanas_previstas="8", follow=True,
        )
        self.assertContains(response, "Ya existe un bloque o una propuesta")
        self.assertEqual(ContratoBloqueGym.objects.count(), 1)
