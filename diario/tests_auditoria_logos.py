import json
from datetime import datetime, time, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from diario.models import (
    ProsocheDiario,
    ProsocheMes,
    RachaEscritura,
    ReflexionGuiadaTema,
    ReflexionLibre,
)


class AuditoriaLogosReadOnlyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="secreto-usuario", email="secreto@example.test"
        )
        hoy = timezone.localdate()
        self.tema = ReflexionGuiadaTema.objects.create(
            titulo="Tema ultrasecreto", slug="tema-auditoria", fecha_activacion=hoy,
            contexto="contexto secreto", cita_filosofica="cita secreta",
            autor_cita="autor secreto", pregunta_1="pregunta secreta",
            accion_sugerida="accion secreta",
        )

    def _reflexion(self, *, fecha=None, etiquetas="", guiada=False, contenido="contenido secreto"):
        obj = ReflexionLibre.objects.create(
            usuario=self.user, titulo="titulo secreto", contenido=contenido,
            etiquetas=etiquetas, reflexion_guiada=self.tema if guiada else None,
        )
        if fecha:
            instante = timezone.make_aware(datetime.combine(fecha, time(12)))
            ReflexionLibre.objects.filter(pk=obj.pk).update(fecha=instante)
        return obj

    def _entrada(self, fecha, texto=""):
        mes = ProsocheMes.objects.create(
            usuario=self.user, mes=f"mes-{fecha.month}", año=fecha.year,
        )
        return ProsocheDiario.objects.create(
            prosoche_mes=mes, fecha=fecha, reflexiones_dia=texto,
            cierre_confirmado_en=timezone.now(),
        )

    def test_servicio_detecta_con_codigos_y_snapshot_de_racha_puro(self):
        from diario.services.auditoria_logos_service import auditar_logos

        hoy = timezone.localdate()
        primera = self._reflexion(fecha=hoy - timedelta(days=1), guiada=True)
        self._reflexion(fecha=hoy, guiada=True)
        no_canonica = self._reflexion(fecha=hoy, etiquetas=" foco,FOCO , calma ")
        huerfana = self._reflexion(fecha=hoy - timedelta(days=3), etiquetas="cierre_dia")
        entrada = self._entrada(hoy - timedelta(days=2), texto="cierre altamente secreto")
        RachaEscritura.objects.filter(usuario=self.user).update(
            dias_consecutivos=99, total_dias_escritos=99,
        )

        antes = list(RachaEscritura.objects.filter(usuario=self.user).values())
        resultado = auditar_logos(usuario_id=self.user.pk, limit=100)
        despues = list(RachaEscritura.objects.filter(usuario=self.user).values())

        self.assertEqual(antes, despues)
        por_codigo = {item["codigo"]: item for item in resultado["hallazgos"]}
        self.assertEqual(por_codigo["reflexion_guiada_duplicada"]["tema_id"], self.tema.pk)
        self.assertEqual(por_codigo["reflexion_guiada_duplicada"]["conteo"], 2)
        self.assertEqual(por_codigo["etiquetas_no_canonicas"]["reflexion_id"], no_canonica.pk)
        self.assertIn("racha_desalineada", por_codigo)
        self.assertEqual(
            por_codigo["proyeccion_cierre_sin_fuente"]["reflexion_id"], huerfana.pk
        )
        self.assertEqual(
            por_codigo["fuente_cierre_sin_proyeccion"]["prosoche_diario_id"], entrada.pk
        )
        self.assertEqual(resultado["tema_del_dia_id"], self.tema.pk)
        self.assertNotIn("titulo secreto", json.dumps(resultado))
        self.assertNotIn(str(primera.contenido), json.dumps(resultado))

    def test_comando_jsonl_determinista_filtrable_limitado_y_sin_secretos(self):
        self._reflexion(etiquetas=" secreto,SECRETO ")
        self._reflexion(etiquetas=" otra,OTRA ")
        before = {
            "reflexiones": list(ReflexionLibre.objects.values().order_by("pk")),
            "rachas": list(RachaEscritura.objects.values().order_by("pk")),
        }

        salidas = []
        for _ in range(2):
            out = StringIO()
            call_command(
                "auditar_logos", usuario_id=self.user.pk, limit=1, stdout=out
            )
            salidas.append(out.getvalue())

        self.assertEqual(salidas[0], salidas[1])
        lineas = [json.loads(linea) for linea in salidas[0].splitlines()]
        self.assertEqual(len(lineas), 2)
        self.assertEqual(lineas[-1]["tipo"], "resumen")
        self.assertEqual(lineas[-1]["emitidos"], 1)
        self.assertNotIn("secreto", salidas[0].casefold())
        self.assertNotIn("email", salidas[0].casefold())
        self.assertNotIn("username", salidas[0].casefold())
        after = {
            "reflexiones": list(ReflexionLibre.objects.values().order_by("pk")),
            "rachas": list(RachaEscritura.objects.values().order_by("pk")),
        }
        self.assertEqual(before, after)

    def test_comando_no_expone_opcion_apply_y_rechaza_limites_inseguros(self):
        with self.assertRaises(CommandError):
            call_command("auditar_logos", "--apply", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("auditar_logos", "--limit", "0", stdout=StringIO())

    def test_usuario_sin_actividad_no_produce_hallazgos_ni_crea_racha(self):
        from diario.services.auditoria_logos_service import auditar_logos

        RachaEscritura.objects.filter(usuario=self.user).delete()
        self.assertFalse(RachaEscritura.objects.filter(usuario=self.user).exists())

        filtrado = auditar_logos(usuario_id=self.user.pk)
        global_resultado = auditar_logos()

        self.assertEqual(filtrado["hallazgos"], [])
        self.assertEqual(global_resultado["hallazgos"], [])
        self.assertFalse(RachaEscritura.objects.filter(usuario=self.user).exists())
