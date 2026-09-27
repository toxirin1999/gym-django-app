"""
Corrige registros de HistorialFase donde 'semanas_completadas' quedo
inflado muy por encima de 'semanas_planificadas'.

Motivo: la deteccion de cambio de fase comparaba solo por nombre_fase.
Como varios bloques del año comparten nombre (p.ej. "Descarga Activa"
se repite tras cada bloque de la periodizacion), una fase de descarga
podia quedar marcada como 'activa' durante meses antes de que el
sistema detectara una fase realmente nueva, y al cerrarse se le
asignaba como 'semanas_completadas' el numero de dias de calendario
transcurridos / 7 (p.ej. 26 semanas) en vez de su duracion real
planificada (p.ej. 1 semana). Ver el fix de codigo en
analytics/views.py (explicacion_plan_helms) y
analytics/planificador_helms/calculo/peso.py (1RM lookup) del mismo
commit.

Este comando SOLO toca registros ya completados/cerrados cuya
'semanas_completadas' sea mayor que su 'semanas_planificadas' (un
registro correcto nunca deberia superar su propia duracion
planificada) y los ajusta a esa duracion planificada.

Uso:
    python manage.py fix_historial_fase_descarga --dry-run   (por defecto, no escribe nada)
    python manage.py fix_historial_fase_descarga --apply      (aplica los cambios)
"""
from django.core.management.base import BaseCommand
from django.db.models import F

from analytics.models import HistorialFase


class Command(BaseCommand):
    help = "Corrige HistorialFase.semanas_completadas inflado por el bug de deteccion por nombre."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Aplica los cambios. Sin este flag, solo muestra un dry-run.",
        )

    def handle(self, *args, **options):
        aplicar = options["apply"]

        candidatos = (
            HistorialFase.objects
            .filter(completada=True, semanas_planificadas__gt=0)
            .filter(semanas_completadas__gt=F("semanas_planificadas"))
            .order_by("cliente_id", "-fecha_inicio")
        )

        total = candidatos.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "No se encontraron registros con semanas_completadas > semanas_planificadas."
            ))
            return

        self.stdout.write(f"Registros a corregir: {total}")
        for fase in candidatos:
            self.stdout.write(
                f"  cliente_id={fase.cliente_id} id={fase.id} '{fase.nombre_fase}' "
                f"({fase.fecha_inicio} -> {fase.fecha_fin}): "
                f"semanas_completadas {fase.semanas_completadas} -> {fase.semanas_planificadas}"
            )
            if aplicar:
                fase.semanas_completadas = fase.semanas_planificadas
                fase.save(update_fields=["semanas_completadas"])

        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"Corregidos {total} registros."))
        else:
            self.stdout.write(self.style.WARNING(
                "Dry-run: no se escribio nada. Repite con --apply para aplicar los cambios."
            ))
