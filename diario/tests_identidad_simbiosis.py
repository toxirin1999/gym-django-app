import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from diario.models import (
    AliasSimbiosis,
    Interaccion,
    OperacionIdentidadSimbiosis,
    PersonaImportante,
    PersonaInterina,
)
from diario.services.identidad_simbiosis_service import (
    corregir_identidad,
    deshacer_operacion_identidad,
    fusionar_personas,
    normalizar_nombre_identidad,
    resolver_alias,
)


class NormalizacionIdentidadTests(TestCase):
    def test_nfkc_espacios_casefold_y_tildes(self):
        self.assertEqual(normalizar_nombre_identidad("  MAR\u00cdA\t  Jos\u00e9  "), "mar\u00eda jos\u00e9")
        self.assertEqual(normalizar_nombre_identidad("ＡＮＡ"), "ana")


class ModelosIdentidadSimbiosisTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("identidad")
        self.persona = PersonaImportante.objects.create(usuario=self.user, nombre="  Mar\u00eda  ")
        self.interina = PersonaInterina.objects.create(usuario=self.user, nombre="Equipo Norte")

    def test_nombres_se_normalizan_y_tipo_parte_sin_clasificar(self):
        self.assertEqual(self.persona.nombre_normalizado, "mar\u00eda")
        self.assertEqual(self.persona.tipo_entidad, "sin_clasificar")
        self.assertEqual(self.interina.nombre_normalizado, "equipo norte")

    def test_alias_exige_exactamente_un_objetivo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AliasSimbiosis.objects.create(usuario=self.user, nombre="Nada", nombre_normalizado="nada")
        with self.assertRaises(IntegrityError), transaction.atomic():
            AliasSimbiosis.objects.create(
                usuario=self.user, nombre="Ambos", nombre_normalizado="ambos",
                persona_confirmada=self.persona, persona_interina=self.interina,
            )

    def test_alias_rechaza_objetivo_de_otro_usuario(self):
        otro = get_user_model().objects.create_user("otro")
        alias = AliasSimbiosis(
            usuario=otro, nombre="Mar\u00eda", persona_confirmada=self.persona,
        )
        with self.assertRaises(ValidationError):
            alias.full_clean()


class ServiciosIdentidadSimbiosisTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("servicios")
        self.other = get_user_model().objects.create_user("ajeno")
        self.ana = PersonaImportante.objects.create(
            usuario=self.user, nombre="Ana", tipo_entidad="persona",
        )
        self.anita = PersonaImportante.objects.create(
            usuario=self.user, nombre="Anita", tipo_entidad="persona",
        )

    def test_corregir_nombre_y_tipo_crea_alias_y_ledger_idempotente(self):
        clave = uuid.uuid4()
        op1 = corregir_identidad(
            self.ana, nombre="  Ana Mar\u00eda ", tipo_entidad="persona",
            operacion_id=clave,
        )
        op2 = corregir_identidad(
            self.ana, nombre="IGNORADO", tipo_entidad="grupo", operacion_id=clave,
        )
        self.ana.refresh_from_db()
        self.assertEqual(op1.pk, op2.pk)
        self.assertEqual(self.ana.nombre, "Ana Mar\u00eda")
        self.assertEqual(self.ana.nombre_normalizado, "ana mar\u00eda")
        self.assertTrue(AliasSimbiosis.objects.filter(
            usuario=self.user, persona_confirmada=self.ana,
            nombre_normalizado="ana", activo=True,
        ).exists())

    def test_fusion_logica_no_mueve_m2m_y_es_idempotente(self):
        interaccion = Interaccion.objects.create(
            usuario=self.user, titulo="historia", descripcion="se conserva",
        )
        interaccion.personas.add(self.anita)
        clave = uuid.uuid4()
        op1 = fusionar_personas(self.anita, self.ana, operacion_id=clave)
        op2 = fusionar_personas(self.anita, self.ana, operacion_id=clave)
        self.anita.refresh_from_db()
        self.assertEqual(op1.pk, op2.pk)
        self.assertEqual(self.anita.fusionada_en, self.ana)
        self.assertTrue(interaccion.personas.filter(pk=self.anita.pk).exists())
        self.assertFalse(interaccion.personas.filter(pk=self.ana.pk).exists())
        self.assertEqual(resolver_alias(self.user, "ANITA"), self.ana)

    def test_fusion_rechaza_multiusuario_tipo_cruzado_no_raiz_y_ciclo(self):
        ajena = PersonaImportante.objects.create(usuario=self.other, nombre="Ajena", tipo_entidad="persona")
        grupo = PersonaImportante.objects.create(usuario=self.user, nombre="Equipo", tipo_entidad="grupo")
        with self.assertRaises(ValidationError):
            fusionar_personas(self.anita, ajena)
        with self.assertRaises(ValidationError):
            fusionar_personas(self.anita, grupo)
        fusionar_personas(self.anita, self.ana)
        with self.assertRaises(ValidationError):
            fusionar_personas(self.anita, grupo)
        with self.assertRaises(ValidationError):
            fusionar_personas(self.ana, self.anita)

    def test_deshacer_restauracion_idempotente(self):
        op = fusionar_personas(self.anita, self.ana)
        undo1 = deshacer_operacion_identidad(op)
        undo2 = deshacer_operacion_identidad(op)
        self.anita.refresh_from_db()
        self.assertIsNone(self.anita.fusionada_en)
        self.assertEqual(undo1.pk, undo2.pk)
        self.assertEqual(undo1.deshace_a, op)

    def test_resolver_alias_no_decide_ambiguedad(self):
        AliasSimbiosis.objects.create(
            usuario=self.user, nombre="A", nombre_normalizado="a",
            persona_confirmada=self.ana,
        )
        AliasSimbiosis.objects.create(
            usuario=self.user, nombre="A", nombre_normalizado="a",
            persona_confirmada=self.anita,
        )
        self.assertIsNone(resolver_alias(self.user, "a"))

    def test_clave_idempotente_no_cruza_usuario_ni_tipo_de_operacion(self):
        clave = uuid.uuid4()
        corregir_identidad(self.ana, nombre="Ana María", operacion_id=clave)
        ajena = PersonaImportante.objects.create(
            usuario=self.other, nombre="Ajena", tipo_entidad="persona",
        )
        with self.assertRaises(ValidationError):
            corregir_identidad(ajena, nombre="Otra", operacion_id=clave)
        with self.assertRaises(ValidationError):
            fusionar_personas(self.anita, self.ana, operacion_id=clave)
