import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from entrenos.models import (
    EjercicioRealizado,
    EntrenoRealizado,
    SerieRealizada,
    SesionProgramada,
)
from rutinas.models import EjercicioBase


TECNICAS = {choice for choice, _label in SerieRealizada.TECNICA_CHOICES}


@dataclass(frozen=True)
class SerieNueva:
    numero: int
    peso: Decimal
    repeticiones: int
    rpe: float
    tecnica: str


def _decimal(valor, opcion):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError) as exc:
        raise CommandError(f"Valor inválido para {opcion}: {valor}") from exc


def _parsear_serie(valor):
    partes = valor.split(":")
    if len(partes) != 5:
        raise CommandError("--serie debe usar NUM:PESO:REPS:RPE:TECNICA")
    try:
        numero = int(partes[0])
        peso = _decimal(partes[1], "--serie PESO")
        repeticiones = int(partes[2])
        rpe = float(partes[3])
    except ValueError as exc:
        raise CommandError(f"--serie inválida: {valor}") from exc
    tecnica = partes[4].strip().lower()
    if numero < 1 or peso < 0 or repeticiones < 1 or not 0 <= rpe <= 10:
        raise CommandError(f"--serie contiene valores fuera de rango: {valor}")
    if tecnica not in TECNICAS:
        raise CommandError(f"técnica inválida en --serie: {tecnica}")
    return SerieNueva(numero, peso, repeticiones, rpe, tecnica)


def _parsear_tecnica(valor):
    partes = valor.split(":")
    if len(partes) != 2:
        raise CommandError("--tecnica-existente debe usar NUM:TECNICA")
    try:
        numero = int(partes[0])
    except ValueError as exc:
        raise CommandError(f"--tecnica-existente inválida: {valor}") from exc
    tecnica = partes[1].strip().lower()
    if numero < 1 or tecnica not in TECNICAS:
        raise CommandError(f"técnica inválida en --tecnica-existente: {valor}")
    return numero, tecnica


class Command(BaseCommand):
    help = "Repara series detalladas ausentes con guardrails estrictos (dry-run por defecto)"

    def add_arguments(self, parser):
        parser.add_argument("--entreno", required=True, type=int)
        parser.add_argument("--ejercicio", required=True, type=int)
        parser.add_argument("--agregado", required=True, type=int)
        parser.add_argument("--sesion-programada", required=True, type=int)
        parser.add_argument("--fecha", required=True, type=date.fromisoformat)
        parser.add_argument("--expected-numero-ejercicios", required=True, type=int)
        parser.add_argument("--expected-volumen", required=True, type=Decimal)
        parser.add_argument("--expected-volumen-final", required=True, type=Decimal)
        parser.add_argument("--expected-series-final", required=True, type=int)
        parser.add_argument("--expected-peso-promedio-final", required=True, type=Decimal)
        parser.add_argument("--expected-reps-promedio-final", required=True, type=Decimal)
        parser.add_argument("--expected-rpe-promedio-final", required=True, type=Decimal)
        parser.add_argument("--serie", required=True, action="append")
        parser.add_argument("--tecnica-existente", action="append", default=[])
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        nuevas = [_parsear_serie(valor) for valor in options["serie"]]
        tecnicas = [_parsear_tecnica(valor) for valor in options["tecnica_existente"]]
        self._validar_duplicados(nuevas, tecnicas)

        with transaction.atomic():
            resultado = self._reparar(options, nuevas, tecnicas)

        self.stdout.write(json.dumps(resultado, ensure_ascii=False, sort_keys=True))

    @staticmethod
    def _validar_duplicados(nuevas, tecnicas):
        numeros_nuevos = [serie.numero for serie in nuevas]
        if len(numeros_nuevos) != len(set(numeros_nuevos)):
            raise CommandError("conflicto: --serie contiene números duplicados")
        numeros_tecnica = [numero for numero, _tecnica in tecnicas]
        if len(numeros_tecnica) != len(set(numeros_tecnica)):
            raise CommandError("conflicto: --tecnica-existente contiene números duplicados")
        solapados = set(numeros_nuevos) & set(numeros_tecnica)
        if solapados:
            raise CommandError(f"conflicto: una serie no puede ser nueva y existente: {sorted(solapados)}")

    def _reparar(self, options, nuevas, tecnicas):
        try:
            entreno = EntrenoRealizado.objects.select_for_update().get(pk=options["entreno"])
        except EntrenoRealizado.DoesNotExist as exc:
            raise CommandError(f"No existe el entreno {options['entreno']}") from exc
        try:
            ejercicio = EjercicioBase.objects.get(pk=options["ejercicio"])
            agregado = EjercicioRealizado.objects.select_for_update().get(pk=options["agregado"])
            sp = SesionProgramada.objects.select_for_update().get(pk=options["sesion_programada"])
        except EjercicioBase.DoesNotExist as exc:
            raise CommandError(f"No existe el ejercicio {options['ejercicio']}") from exc
        except EjercicioRealizado.DoesNotExist as exc:
            raise CommandError(f"No existe el agregado {options['agregado']}") from exc
        except SesionProgramada.DoesNotExist as exc:
            raise CommandError(f"No existe la sesión programada {options['sesion_programada']}") from exc

        expected_volumen = _decimal(options["expected_volumen"], "--expected-volumen")
        expected_final = _decimal(options["expected_volumen_final"], "--expected-volumen-final")
        if entreno.fecha != options["fecha"]:
            raise CommandError(f"Guardrail fecha: actual={entreno.fecha} esperada={options['fecha']}")
        if entreno.numero_ejercicios != options["expected_numero_ejercicios"]:
            raise CommandError(
                "Guardrail numero_ejercicios: "
                f"actual={entreno.numero_ejercicios} esperado={options['expected_numero_ejercicios']}"
            )
        if entreno.volumen_total_kg not in (expected_volumen, expected_final):
            raise CommandError(
                "Guardrail volumen: "
                f"actual={entreno.volumen_total_kg} esperado={expected_volumen} o final={expected_final}"
            )
        candidatos_agregado = list(
            EjercicioRealizado.objects.select_for_update().filter(
                entreno=entreno, nombre_ejercicio=ejercicio.nombre
            )
        )
        if len(candidatos_agregado) != 1:
            raise CommandError(
                f"Guardrail agregado ambiguo: hay {len(candidatos_agregado)} candidatos para el ejercicio"
            )
        if agregado.entreno_id != entreno.pk or candidatos_agregado[0].pk != agregado.pk:
            raise CommandError("Guardrail agregado: no pertenece al entreno/ejercicio indicados")
        if sp.cliente_id != entreno.cliente_id:
            raise CommandError("Guardrail sesión programada: pertenece a otro cliente")
        if sp.entreno_realizado_id not in (None, entreno.pk):
            raise CommandError("Guardrail sesión programada: ya está vinculada a otro entreno")
        if sp.estado not in (SesionProgramada.ESTADO_PENDIENTE, SesionProgramada.ESTADO_COMPLETADA):
            raise CommandError(f"Guardrail sesión programada: estado incompatible {sp.estado}")
        if sp.estado == SesionProgramada.ESTADO_COMPLETADA and (
            sp.entreno_realizado_id != entreno.pk or sp.fecha_realizada != entreno.fecha
        ):
            raise CommandError("Guardrail sesión programada: cierre completado conflictivo")

        series = list(
            SerieRealizada.objects.select_for_update()
            .filter(entreno=entreno, ejercicio=ejercicio)
            .order_by("serie_numero", "pk")
        )
        por_numero = {}
        for serie in series:
            if serie.serie_numero in por_numero:
                raise CommandError(f"conflicto: serie {serie.serie_numero} está duplicada en la base")
            por_numero[serie.serie_numero] = serie
        nuevas_a_crear = []
        for nueva in nuevas:
            existente = por_numero.get(nueva.numero)
            if existente is None:
                nuevas_a_crear.append(nueva)
                continue
            if not self._serie_coincide(existente, nueva):
                raise CommandError(f"conflicto: serie {nueva.numero} ya existe con datos distintos")

        tecnicas_a_actualizar = []
        for numero, tecnica in tecnicas:
            serie = por_numero.get(numero)
            if serie is None:
                raise CommandError(f"No existe la serie existente {numero}")
            if serie.tecnica_calidad not in (None, "", tecnica):
                raise CommandError(
                    f"conflicto de técnica en serie {numero}: actual={serie.tecnica_calidad} nueva={tecnica}"
                )
            if serie.tecnica_calidad != tecnica:
                tecnicas_a_actualizar.append((serie, tecnica))

        incremento = sum((serie.peso * serie.repeticiones for serie in nuevas), Decimal("0"))
        calculado_final = expected_volumen + incremento
        if calculado_final != expected_final:
            raise CommandError(
                f"Guardrail volumen final: calculado={calculado_final} esperado={expected_final}"
            )
        final_por_numero = dict(por_numero)
        final_por_numero.update({serie.numero: serie for serie in nuevas_a_crear})
        total_series_final = len(final_por_numero)
        expected_series_final = options["expected_series_final"]
        if total_series_final != expected_series_final:
            raise CommandError(
                f"Guardrail series final: calculado={total_series_final} esperado={expected_series_final}"
            )
        valores_finales = list(final_por_numero.values())
        peso_promedio = sum((_decimal(s.peso_kg, "peso") if isinstance(s, SerieRealizada) else s.peso for s in valores_finales), Decimal("0")) / total_series_final
        reps_promedio = sum((Decimal(s.repeticiones) for s in valores_finales), Decimal("0")) / total_series_final
        if any((s.rpe_real if isinstance(s, SerieRealizada) else s.rpe) is None for s in valores_finales):
            raise CommandError("Guardrail agregado: no se puede calcular RPE promedio con valores nulos")
        rpe_promedio = sum(
            (_decimal(s.rpe_real, "rpe") if isinstance(s, SerieRealizada) else _decimal(s.rpe, "rpe") for s in valores_finales),
            Decimal("0"),
        ) / total_series_final
        esperados_promedio = (
            _decimal(options["expected_peso_promedio_final"], "--expected-peso-promedio-final"),
            _decimal(options["expected_reps_promedio_final"], "--expected-reps-promedio-final"),
            _decimal(options["expected_rpe_promedio_final"], "--expected-rpe-promedio-final"),
        )
        if (peso_promedio, reps_promedio, rpe_promedio) != esperados_promedio:
            raise CommandError(
                "Guardrail promedios finales: "
                f"calculados={(peso_promedio, reps_promedio, rpe_promedio)} esperados={esperados_promedio}"
            )

        agregado_final = {
            "series": expected_series_final,
            "peso_kg": float(peso_promedio),
            "repeticiones": int(reps_promedio),
            "rpe": int(rpe_promedio),
            "completado": True,
        }
        before = {
            "volumen_total_kg": f"{entreno.volumen_total_kg:.2f}",
            "agregado": self._snapshot_agregado(agregado),
            "sesion_programada": self._snapshot_sp(sp),
        }
        agregado_necesita_update = any(
            getattr(agregado, campo) != valor for campo, valor in agregado_final.items()
        )
        sp_ya_cerrada = (
            sp.estado == SesionProgramada.ESTADO_COMPLETADA
            and sp.fecha_realizada == entreno.fecha
            and sp.entreno_realizado_id == entreno.pk
        )

        if options["apply"]:
            SerieRealizada.objects.bulk_create([
                SerieRealizada(
                    entreno=entreno,
                    ejercicio=ejercicio,
                    serie_numero=serie.numero,
                    peso_kg=serie.peso,
                    repeticiones=serie.repeticiones,
                    rpe_real=serie.rpe,
                    tecnica_calidad=serie.tecnica,
                    completado=True,
                )
                for serie in nuevas_a_crear
            ])
            for serie, tecnica in tecnicas_a_actualizar:
                SerieRealizada.objects.filter(pk=serie.pk).update(tecnica_calidad=tecnica)
            if agregado_necesita_update:
                EjercicioRealizado.objects.filter(pk=agregado.pk).update(**agregado_final)
            if entreno.volumen_total_kg != expected_final:
                EntrenoRealizado.objects.filter(pk=entreno.pk).update(volumen_total_kg=expected_final)
            if not sp_ya_cerrada:
                SesionProgramada.objects.filter(pk=sp.pk).update(
                    estado=SesionProgramada.ESTADO_COMPLETADA,
                    fecha_realizada=entreno.fecha,
                    entreno_realizado_id=entreno.pk,
                )

        ids_creados = []
        if options["apply"] and nuevas_a_crear:
            ids_creados = list(
                SerieRealizada.objects.filter(
                    entreno=entreno,
                    ejercicio=ejercicio,
                    serie_numero__in=[serie.numero for serie in nuevas_a_crear],
                ).order_by("serie_numero").values_list("pk", flat=True)
            )
        after = {
            "volumen_total_kg": f"{expected_final:.2f}",
            "agregado": agregado_final,
            "sesion_programada": {
                "estado": SesionProgramada.ESTADO_COMPLETADA,
                "fecha_realizada": entreno.fecha.isoformat(),
                "entreno_realizado_id": entreno.pk,
            },
        }
        noop = not any((nuevas_a_crear, tecnicas_a_actualizar, agregado_necesita_update,
                        entreno.volumen_total_kg != expected_final, not sp_ya_cerrada))

        return {
            "after": after,
            "before": before,
            "ids": {"agregado": agregado.pk, "ejercicio": ejercicio.pk,
                    "entreno": entreno.pk, "sesion_programada": sp.pk},
            "ids_creados": ids_creados,
            "modo": "apply" if options["apply"] else "dry-run",
            "noop": noop,
            "plan": {
                "series_a_crear": [serie.numero for serie in nuevas_a_crear],
                "tecnicas_a_actualizar": [serie.serie_numero for serie, _ in tecnicas_a_actualizar],
            },
            "reversible": {
                "eliminar_series_ids": ids_creados,
                "restaurar": before,
            },
        }

    @staticmethod
    def _serie_coincide(existente, nueva):
        return (
            existente.peso_kg == nueva.peso
            and existente.repeticiones == nueva.repeticiones
            and existente.rpe_real == nueva.rpe
            and existente.tecnica_calidad == nueva.tecnica
            and existente.completado is True
        )

    @staticmethod
    def _snapshot_agregado(agregado):
        return {
            "series": agregado.series,
            "peso_kg": agregado.peso_kg,
            "repeticiones": agregado.repeticiones,
            "rpe": agregado.rpe,
            "completado": agregado.completado,
            "es_tope_maquina": agregado.es_tope_maquina,
        }

    @staticmethod
    def _snapshot_sp(sp):
        return {
            "estado": sp.estado,
            "fecha_realizada": sp.fecha_realizada.isoformat() if sp.fecha_realizada else None,
            "entreno_realizado_id": sp.entreno_realizado_id,
        }
