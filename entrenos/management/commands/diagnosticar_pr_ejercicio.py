"""
Management command de solo lectura: diagnostica el "1RM est." mostrado en la
vista de sesión activa, que sale de RecordsService.obtener_mejor_marca() +
estimar_1rm() sobre esa marca — no de ningún cálculo de peso de descarga.

Origen: "Abducción de Cadera en Máquina" mostró "1RM est.: 597 kg" en una
máquina con tope físico de 60kg. Ese número no puede salir de una serie real
de pocas repeticiones (60kg x31 reps da e1RM≈122, no 597) — apunta a una fila
de EjercicioRealizado con repeticiones anómalas para ese peso.

No modifica nada en la base de datos.

Usage:
    python3 manage.py diagnosticar_pr_ejercicio --usuario david --ejercicio "Abducción de Cadera en Máquina"
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


# Umbral por encima del cual una sola serie es fisiológicamente implausible
# para casi cualquier ejercicio de máquina — señal de dato corrupto/typo,
# no de una serie real.
REPS_SOSPECHOSAS = 50


class Command(BaseCommand):
    help = "Diagnostica el origen del '1RM est.' (RecordsService.obtener_mejor_marca) para un ejercicio"

    def add_arguments(self, parser):
        parser.add_argument('--usuario', required=True, help='username de Django')
        parser.add_argument('--ejercicio', required=True, help='nombre exacto del ejercicio')

    def handle(self, *args, **options):
        from clientes.models import Cliente
        from entrenos.models import EjercicioRealizado, RecordPersonal
        from entrenos.services.records_service import RecordsService
        from analytics.utils import estimar_1rm

        try:
            usuario = User.objects.get(username=options['usuario'])
        except User.DoesNotExist:
            raise CommandError(f"Usuario '{options['usuario']}' no existe")

        try:
            cliente = Cliente.objects.get(user=usuario)
        except Cliente.DoesNotExist:
            raise CommandError(f"El usuario '{options['usuario']}' no tiene Cliente asociado")

        nombre_ejercicio = options['ejercicio']

        self.stdout.write(self.style.SUCCESS(
            f"\n=== PR / 1RM EST. — {cliente.nombre} — '{nombre_ejercicio}' ===\n"
        ))

        # 1. Lo que realmente usa la vista: obtener_mejor_marca() + estimar_1rm().
        pr = RecordsService.obtener_mejor_marca(cliente, nombre_ejercicio)
        if pr is None:
            self.stdout.write(self.style.WARNING("Sin marca (obtener_mejor_marca devolvió None).\n"))
        else:
            one_rm = estimar_1rm(float(pr.peso_kg), pr.repeticiones)
            self.stdout.write(
                f"obtener_mejor_marca() → EjercicioRealizado id={pr.id}  "
                f"fecha={pr.entreno.fecha}  peso={pr.peso_kg}  reps={pr.repeticiones}  "
                f"series={pr.series}  completado={pr.completado}\n"
            )
            self.stdout.write(f"estimar_1rm(peso, reps) → {one_rm:.1f} kg  (esto es el badge '1RM est.' en pantalla)\n")
            if pr.repeticiones and pr.repeticiones >= REPS_SOSPECHOSAS:
                self.stdout.write(self.style.ERROR(
                    f"\n⚠ reps={pr.repeticiones} en una sola serie es fisiológicamente implausible. "
                    "Dato probablemente corrupto (typo, import mal parseado, o duplicado sumado)."
                ))

        # 2. Todas las filas con el mismo peso que la marca elegida (para ver
        #    si hay empate y cuál desempató por fecha).
        if pr is not None:
            empatadas = list(
                EjercicioRealizado.objects
                .filter(entreno__cliente=cliente, nombre_ejercicio__iexact=nombre_ejercicio,
                        peso_kg=pr.peso_kg, completado=True)
                .select_related('entreno')
                .order_by('-entreno__fecha', '-id')
            )
            if len(empatadas) > 1:
                self.stdout.write(f"\nOtras filas con el mismo peso ({pr.peso_kg}kg), candidatas al empate:")
                for e in empatadas:
                    marca = ' ← elegida' if e.id == pr.id else ''
                    self.stdout.write(f"  id={e.id}  {e.entreno.fecha}  reps={e.repeticiones}  series={e.series}{marca}")

        # 3. Top 10 por peso descendente, para ver el panorama completo y
        #    detectar cualquier otra fila con reps anómalas aunque no sea la
        #    de mayor peso.
        top = list(
            EjercicioRealizado.objects
            .filter(entreno__cliente=cliente, nombre_ejercicio__iexact=nombre_ejercicio,
                    peso_kg__gt=0, completado=True)
            .select_related('entreno')
            .order_by('-peso_kg', '-entreno__fecha')[:10]
        )
        self.stdout.write(f"\nTop 10 filas por peso (todas las series completadas de este ejercicio):")
        for e in top:
            sospechosa = '  ⚠ reps sospechosas' if e.repeticiones and e.repeticiones >= REPS_SOSPECHOSAS else ''
            self.stdout.write(
                f"  id={e.id}  {e.entreno.fecha}  peso={e.peso_kg}  reps={e.repeticiones}  "
                f"series={e.series}  tope={e.es_tope_maquina}{sospechosa}"
            )

        # 4. RecordPersonal almacenados para este ejercicio, por si el dato
        #    corrupto viene de ahí en vez de EjercicioRealizado directo.
        records = list(
            RecordPersonal.objects
            .filter(cliente=cliente, ejercicio_nombre__iexact=nombre_ejercicio)
            .order_by('-fecha_logrado')[:10]
        )
        if records:
            self.stdout.write(f"\nRecordPersonal guardados para este ejercicio:")
            for r in records:
                self.stdout.write(
                    f"  {r.fecha_logrado}  tipo={r.tipo_record}  valor={r.valor}  superado={r.superado}"
                )
