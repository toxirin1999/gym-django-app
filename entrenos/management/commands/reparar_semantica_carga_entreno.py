import json
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from entrenos.models import EjercicioRealizado, EntrenoRealizado, SerieRealizada
from entrenos.services.peso_semantica_service import resolver_semantica_carga


ALLOWED = {
    SerieRealizada: {"peso_kg", "repeticiones", "distancia_metros", "tipo_carga",
                     "multiplicador_carga", "peso_total_kg", "rpe_real", "tecnica_calidad"},
    EjercicioRealizado: {"peso_kg", "repeticiones", "series", "tipo_carga",
                         "multiplicador_carga", "peso_total_kg", "rpe", "es_tope_maquina"},
}


def _json(value, nombre):
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError as exc:
        raise CommandError(f"{nombre} no es JSON válido: {exc}") from exc
    if not isinstance(parsed, list):
        raise CommandError(f"{nombre} debe ser una lista")
    return parsed


def _serializar(value):
    return str(value) if isinstance(value, Decimal) else value


def _igual(a, b):
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:
        return a == b


class Command(BaseCommand):
    help = "Repara declarativamente cargas de un entreno; dry-run por defecto."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--entreno", required=True, type=int)
        parser.add_argument("--cliente", required=True, type=int)
        parser.add_argument("--fecha", required=True, type=date.fromisoformat)
        parser.add_argument("--series-json", default="[]")
        parser.add_argument("--agregados-json", default="[]")

    def handle(self, *args, **options):
        with transaction.atomic():
            result = self._execute(options)
            if not options["apply"]:
                transaction.set_rollback(True)
        self.stdout.write(json.dumps(result, ensure_ascii=False, default=str, sort_keys=True))

    def _execute(self, options):
        try:
            entreno = EntrenoRealizado.objects.select_for_update().get(pk=options["entreno"])
        except EntrenoRealizado.DoesNotExist as exc:
            raise CommandError("Guardrail: el entreno no existe") from exc
        if entreno.cliente_id != options["cliente"] or entreno.fecha != options["fecha"]:
            raise CommandError("Guardrail: cliente o fecha no coinciden")

        specs = {
            "series": (SerieRealizada, _json(options["series_json"], "series-json")),
            "agregados": (EjercicioRealizado, _json(options["agregados_json"], "agregados-json")),
        }
        before, after, reversible = {}, {}, {}
        noop = True
        for clave, (model, items) in specs.items():
            before[clave], after[clave], reversible[clave] = [], [], []
            ids = [item.get("id") for item in items]
            if any(pk is None for pk in ids) or len(ids) != len(set(ids)):
                raise CommandError(f"Guardrail {clave}: IDs ausentes o repetidos")
            objetos = {o.pk: o for o in model.objects.select_for_update().filter(pk__in=ids)}
            if set(objetos) != set(ids):
                raise CommandError(f"Guardrail {clave}: faltan IDs solicitados")
            for item in items:
                obj = objetos[item["id"]]
                if obj.entreno_id != entreno.pk:
                    raise CommandError(f"Guardrail {clave} {obj.pk}: pertenece a otro entreno")
                expected, changes = item.get("expected", {}), dict(item.get("set", {}))
                invalidos = (set(expected) | set(changes)) - ALLOWED[model]
                if invalidos:
                    raise CommandError(f"Guardrail {clave}: campos no permitidos {sorted(invalidos)}")
                if "peso_kg" in changes or "tipo_carga" in changes:
                    sem = resolver_semantica_carga(
                        changes.get("tipo_carga", obj.tipo_carga),
                        changes.get("peso_kg", obj.peso_kg),
                    )
                    changes.update(sem)
                actual = {field: _serializar(getattr(obj, field)) for field in changes}
                final = {field: _serializar(value) for field, value in changes.items()}
                esperado = {field: _serializar(value) for field, value in expected.items()}
                if not all(
                    _igual(getattr(obj, f), v) or (f in changes and _igual(getattr(obj, f), changes[f]))
                    for f, v in expected.items()
                ):
                    raise CommandError(f"Guardrail {clave} {obj.pk}: estado inesperado")
                before[clave].append({"id": obj.pk, **actual})
                after[clave].append({"id": obj.pk, **final})
                reversible[clave].append({"id": obj.pk, "expected": final, "set": actual})
                item_noop = all(_igual(getattr(obj, f), v) for f, v in changes.items())
                noop = noop and item_noop
                if options["apply"] and not item_noop:
                    model.objects.filter(pk=obj.pk).update(**changes)

        if options["apply"] and not noop:
            entreno.refresh_from_db()
            EntrenoRealizado.objects.filter(pk=entreno.pk).update(
                volumen_total_kg=entreno.calcular_volumen_total()
            )
        return {
            "modo": "apply" if options["apply"] else "dry-run", "noop": noop,
            "before": before, "after": after, "reversible": reversible,
        }
