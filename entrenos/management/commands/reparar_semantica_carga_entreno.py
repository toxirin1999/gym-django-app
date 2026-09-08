import json
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada, SesionProgramada


SERIES = {
    1813: (Decimal("75"), Decimal("36"), "por_mano", Decimal("72")),
    1814: (Decimal("75"), Decimal("36"), "por_mano", Decimal("72")),
    1821: (Decimal("15"), Decimal("15"), "por_mano", Decimal("30")),
    1822: (Decimal("15"), Decimal("15"), "por_mano", Decimal("30")),
    1823: (Decimal("15"), Decimal("15"), "por_mano", Decimal("30")),
    1824: (Decimal("45"), Decimal("45"), "por_lado", Decimal("90")),
    1825: (Decimal("40"), Decimal("40"), "por_lado", Decimal("80")),
    1826: (Decimal("35"), Decimal("35"), "por_lado", Decimal("70")),
}
AGREGADOS = {
    1059: (75.0, 36.0, "por_mano", Decimal("72")),
    1062: (15.0, 15.0, "por_mano", Decimal("30")),
    1063: (40.0, 40.0, "por_lado", Decimal("80")),
}


def snapshot(obj, fields):
    return {"id": obj.pk, **{field: getattr(obj, field) for field in fields}}


class Command(BaseCommand):
    help = "Repara de forma auditable snapshots de carga de un entreno concreto"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--entreno", type=int, default=362)
        parser.add_argument("--cliente", type=int, default=2)
        parser.add_argument("--fecha", required=True, type=date.fromisoformat)
        parser.add_argument("--volumen-anterior", default="9102.50")
        parser.add_argument("--volumen-final", default="9576.50")
        parser.add_argument("--sesion-programada", type=int, default=44)

    def handle(self, *args, **options):
        with transaction.atomic():
            result = self._execute(options)
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write(json.dumps(result, ensure_ascii=False, default=str, sort_keys=True))

    def _execute(self, options):
        expected_before = Decimal(options["volumen_anterior"])
        expected_after = Decimal(options["volumen_final"])
        try:
            entreno = EntrenoRealizado.objects.select_for_update().get(pk=options["entreno"])
            sp = SesionProgramada.objects.select_for_update().get(pk=options["sesion_programada"])
        except (EntrenoRealizado.DoesNotExist, SesionProgramada.DoesNotExist) as exc:
            raise CommandError(f"Guardrail: falta objeto esperado: {exc}") from exc
        if entreno.cliente_id != options["cliente"] or entreno.fecha != options["fecha"]:
            raise CommandError("Guardrail entreno: cliente o fecha no coinciden")
        if entreno.volumen_total_kg not in (expected_before, expected_after):
            raise CommandError("Guardrail entreno: volumen inesperado")
        if sp.cliente_id != entreno.cliente_id or sp.entreno_realizado_id not in (None, entreno.pk):
            raise CommandError("Guardrail sesión programada: cliente/vínculo conflictivo")
        if sp.estado not in (SesionProgramada.ESTADO_PENDIENTE, SesionProgramada.ESTADO_COMPLETADA):
            raise CommandError("Guardrail sesión programada: estado conflictivo")

        series = {o.pk: o for o in SerieRealizada.objects.select_for_update().filter(pk__in=SERIES)}
        agregados = {o.pk: o for o in EjercicioRealizado.objects.select_for_update().filter(pk__in=AGREGADOS)}
        if set(series) != set(SERIES) or set(agregados) != set(AGREGADOS):
            raise CommandError("Guardrail: faltan series o agregados esperados")
        for pk, (peso_anterior, peso_final, _tipo, _total) in SERIES.items():
            obj = series[pk]
            if obj.entreno_id != entreno.pk or obj.peso_kg not in (peso_anterior, peso_final):
                raise CommandError(f"Guardrail serie {pk}: entreno/peso inesperado")
        for pk, (peso_anterior, peso_final, _tipo, _total) in AGREGADOS.items():
            obj = agregados[pk]
            pesos_validos = (Decimal(str(peso_anterior)), Decimal(str(peso_final)))
            if obj.entreno_id != entreno.pk or Decimal(str(obj.peso_kg)) not in pesos_validos:
                raise CommandError(f"Guardrail agregado {pk}: entreno/peso inesperado")

        fields = ("peso_kg", "tipo_carga", "multiplicador_carga", "peso_total_kg")
        before = {
            "entreno": snapshot(entreno, ("cliente_id", "fecha", "volumen_total_kg")),
            "series": [snapshot(series[pk], fields) for pk in SERIES],
            "agregados": [snapshot(agregados[pk], fields) for pk in AGREGADOS],
            "sesion_programada": snapshot(sp, ("estado", "fecha_realizada", "entreno_realizado_id")),
        }
        after = {
            "entreno": {"id": entreno.pk, "volumen_total_kg": expected_after},
            "series": [{"id": pk, "peso_kg": p, "tipo_carga": t, "multiplicador_carga": 2, "peso_total_kg": total} for pk, (_old, p, t, total) in SERIES.items()],
            "agregados": [{"id": pk, "peso_kg": p, "tipo_carga": t, "multiplicador_carga": 2, "peso_total_kg": total} for pk, (_old, p, t, total) in AGREGADOS.items()],
            "sesion_programada": {"id": sp.pk, "estado": "completada", "fecha_realizada": entreno.fecha, "entreno_realizado_id": entreno.pk},
        }
        noop = before["entreno"]["volumen_total_kg"] == expected_after
        noop = noop and all(snapshot(series[x], fields) == after["series"][i] for i, x in enumerate(SERIES))
        noop = noop and all(snapshot(agregados[x], fields) == after["agregados"][i] for i, x in enumerate(AGREGADOS))
        noop = noop and sp.estado == "completada" and sp.fecha_realizada == entreno.fecha and sp.entreno_realizado_id == entreno.pk

        if options["apply"] and not noop:
            for pk, (_peso_anterior, peso, tipo, total) in SERIES.items():
                SerieRealizada.objects.filter(pk=pk).update(peso_kg=peso, tipo_carga=tipo, multiplicador_carga=2, peso_total_kg=total)
            for pk, (_peso_anterior, peso, tipo, total) in AGREGADOS.items():
                EjercicioRealizado.objects.filter(pk=pk).update(peso_kg=peso, tipo_carga=tipo, multiplicador_carga=2, peso_total_kg=total)
            EntrenoRealizado.objects.filter(pk=entreno.pk).update(volumen_total_kg=expected_after)
            SesionProgramada.objects.filter(pk=sp.pk).update(estado="completada", fecha_realizada=entreno.fecha, entreno_realizado_id=entreno.pk)
        return {"modo": "apply" if options["apply"] else "dry-run", "noop": noop, "before": before, "after": after, "reversible": {"restaurar": before}}
