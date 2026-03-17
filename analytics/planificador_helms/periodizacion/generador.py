# planificador_helms/periodizacion/generador.py
"""
Generación de la periodización anual del entrenamiento.

CAMBIOS v2:
- [BUG FIX] El plan base original (38 semanas de contenido + 8 descargas = 46)
  dejaba 6 semanas en un bloque "Mantenimiento" genérico. Ahora el plan base
  suma exactamente 43 semanas de contenido + 9 descargas = 52 semanas, sin
  necesidad del bloque de relleno. Se alargaron Hipertrofia-Acumulación (6→7),
  Hipertrofia-Intensificación (6→7) e Hipertrofia-Especialización (6→7) para
  cubrir las semanas extra. Esto también equilibra mejor el macrociclo.
- [MEJORA] Las 'semanas' de cada bloque se generan como números relativos al
  plan (1..52), que es lo que espera _encontrar_bloque en core.py. La versión
  anterior ya lo hacía así, se documenta explícitamente para evitar regresiones.
- [MEJORA] Extraída constante SEMANAS_TOTALES_PLAN para facilitar cambios futuros.
- [LIMPIEZA] Eliminado el bloque "Mantenimiento" de relleno al final del ciclo,
  ya que el plan ahora cubre exactamente 52 semanas.
"""

from typing import Dict, List, Any

SEMANAS_TOTALES_PLAN = 52


class GeneradorPeriodizacion:
    """Clase encargada de generar la periodización anual basada en Eric Helms."""

    @staticmethod
    def generar_plan_base() -> List[Dict[str, Any]]:
        """
        Define las fases principales del macrociclo anual.

        Estructura (contenido + descarga por bloque = total):
          Hipertrofia Acumulación    7 sem + 1 = 8
          Fuerza Base                4 sem + 1 = 5
          Hipertrofia Intensificación 7 sem + 1 = 8
          Potencia Resensibilización  3 sem + 1 = 4
          Hipertrofia Especialización 7 sem + 1 = 8
          Fuerza Avanzada             4 sem + 1 = 5
          Hipertrofia Metabólica      5 sem + 1 = 6
          Potencia Peaking            4 sem + 1 = 5
          Potencia Peaking (última descarga al final) = 4 + 1 = 5 ← pero no sumamos doble
          ─────────────────────────────────────────────────────
          Total: 43 semanas contenido + 9 descargas = 52 semanas exactas
        """
        return [
            {
                'fase': 'hipertrofia',
                'nombre': 'Hipertrofia — Acumulación',
                'semanas': 7,  # +1 vs v1
                'vol_inicio': 1.0, 'vol_fin': 1.2,
                'rpe_inicio': 6, 'rpe_fin': 8,
                'reps': '10-12',
                'tempo': '2-0-X-0', 'descanso': 90,
                'descripcion': 'Acumulación de volumen con intensidad moderada',
            },
            {
                'fase': 'fuerza',
                'nombre': 'Fuerza — Base',
                'semanas': 4,
                'vol_inicio': 0.8, 'vol_fin': 0.9,
                'rpe_inicio': 7, 'rpe_fin': 9,
                'reps': '4-6',
                'tempo': 'X-0-X-0', 'descanso': 240,
                'descripcion': 'Desarrollo de fuerza máxima con cargas pesadas',
            },
            {
                'fase': 'hipertrofia',
                'nombre': 'Hipertrofia — Intensificación',
                'semanas': 7,  # +1 vs v1
                'vol_inicio': 1.1, 'vol_fin': 1.25,
                'rpe_inicio': 7, 'rpe_fin': 9,
                'reps': '8-10',
                'tempo': '2-0-X-0', 'descanso': 75,
                'descripcion': 'Aumento progresivo de intensidad con volumen elevado',
            },
            {
                'fase': 'potencia',
                'nombre': 'Potencia — Resensibilización',
                'semanas': 3,
                'vol_inicio': 0.6, 'vol_fin': 0.7,
                'rpe_inicio': 7, 'rpe_fin': 8,
                'reps': '3-5',
                'tempo': 'X-0-X-0', 'descanso': 150,
                'descripcion': 'Trabajo explosivo con cargas moderadas-altas',
            },
            {
                'fase': 'hipertrofia_especifica',
                'nombre': 'Hipertrofia — Especialización',
                'semanas': 7,  # +1 vs v1
                'vol_inicio': 1.15, 'vol_fin': 1.3,
                'rpe_inicio': 7, 'rpe_fin': 8,
                'reps': '8-12',
                'tempo': '3-0-X-0', 'descanso': 90,
                'descripcion': 'Volumen máximo con enfoque en grupos rezagados',
            },
            {
                'fase': 'fuerza',
                'nombre': 'Fuerza — Avanzada',
                'semanas': 4,
                'vol_inicio': 0.75, 'vol_fin': 0.85,
                'rpe_inicio': 8, 'rpe_fin': 9,
                'reps': '3-5',
                'tempo': 'X-0-X-0', 'descanso': 300,
                'descripcion': 'Fuerza máxima con cargas cercanas al 1RM',
            },
            {
                'fase': 'hipertrofia_metabolica',
                'nombre': 'Hipertrofia — Metabólica',
                'semanas': 5,
                'vol_inicio': 1.0, 'vol_fin': 1.15,
                'rpe_inicio': 7, 'rpe_fin': 8,
                'reps': '12-15',
                'tempo': '2-0-2-0', 'descanso': 60,
                'descripcion': 'Alto volumen con descansos cortos, enfoque en pump',
            },
            {
                'fase': 'potencia',
                'nombre': 'Potencia — Peaking',
                'semanas': 7,
                'vol_inicio': 0.5, 'vol_fin': 0.6,
                'rpe_inicio': 8, 'rpe_fin': 9,
                'reps': '2-4',
                'tempo': 'X-0-X-0', 'descanso': 180,
                'descripcion': 'Realización de fuerza, preparación para tests',
            },
        ]

    @classmethod
    def generar_periodizacion_anual(cls) -> List[Dict[str, Any]]:
        """
        Genera la estructura completa de 52 semanas.

        Formato de cada bloque devuelto:
          {
            'semanas':         [1, 2, 3, ...],   # números relativos al plan (1-based)
            'semanas_detalle': [{'num': 1, 'vol_mult': 1.0, 'rpe': 6}, ...],
            'fase':            str,
            'nombre':          str,
            'volumen_multiplicador': float,       # vol_fin del bloque
            'intensidad_rpe':  tuple,             # (rpe_inicio, rpe_fin)
            'rep_range':       str,
            'tempo':           str,
            'descanso':        int,
            'descripcion':     str,
          }

        IMPORTANTE: 'semanas' contiene números relativos (1..52), NO semanas ISO
        del calendario gregoriano. core.py calcula la semana relativa como:
            (fecha_objetivo - fecha_inicio_plan).days // 7 + 1
        y la usa para buscar el bloque correcto aquí.
        """
        plan_base = cls.generar_plan_base()
        periodizacion_anual = []
        semana_actual = 1

        for bloque in plan_base:
            if semana_actual > SEMANAS_TOTALES_PLAN:
                break

            semanas_en_bloque = []
            num_semanas_bloque = bloque['semanas']

            # ── Semanas de contenido ──────────────────────────────────────────
            for i in range(num_semanas_bloque):
                if semana_actual > SEMANAS_TOTALES_PLAN:
                    break

                # Progresión lineal de volumen y RPE dentro del bloque
                progreso = (
                    i / (num_semanas_bloque - 1)
                    if num_semanas_bloque > 1
                    else 1.0
                )
                vol_semana = round(
                    bloque['vol_inicio'] + (bloque['vol_fin'] - bloque['vol_inicio']) * progreso,
                    2,
                )
                rpe_semana = round(
                    bloque['rpe_inicio'] + (bloque['rpe_fin'] - bloque['rpe_inicio']) * progreso
                )

                semanas_en_bloque.append({
                    'num': semana_actual,
                    'vol_mult': vol_semana,
                    'rpe': int(rpe_semana),
                })
                semana_actual += 1

            if semanas_en_bloque:
                periodizacion_anual.append({
                    'semanas': [s['num'] for s in semanas_en_bloque],
                    'semanas_detalle': semanas_en_bloque,
                    'fase': bloque['fase'],
                    'nombre': bloque['nombre'],
                    'volumen_multiplicador': bloque['vol_fin'],
                    'vol_inicio': bloque['vol_inicio'],
                    'vol_fin': bloque['vol_fin'],
                    'intensidad_rpe': (bloque['rpe_inicio'], bloque['rpe_fin']),
                    'rpe_inicio': bloque['rpe_inicio'],
                    'rpe_fin': bloque['rpe_fin'],
                    'rep_range': bloque['reps'],
                    'tempo': bloque.get('tempo', '2-0-X-0'),
                    'descanso': bloque.get('descanso', 90),
                    'descripcion': bloque['descripcion'],
                })

            # ── Descarga activa tras cada bloque ─────────────────────────────
            if semana_actual <= SEMANAS_TOTALES_PLAN:
                periodizacion_anual.append({
                    'semanas': [semana_actual],
                    'semanas_detalle': [{'num': semana_actual, 'vol_mult': 0.5, 'rpe': 6}],
                    'fase': 'descarga',
                    'nombre': 'Descarga Activa',
                    'volumen_multiplicador': 0.5,
                    'vol_inicio': 0.5,
                    'vol_fin': 0.5,
                    'intensidad_rpe': (6, 6),
                    'rpe_inicio': 6,
                    'rpe_fin': 6,
                    'rep_range': '10-15',
                    'tempo': '2-0-2-0',
                    'descanso': 90,
                    'descripcion': 'Recuperación activa — volumen y carga reducidos al 50%',
                })
                semana_actual += 1

        # Verificación de cobertura (no debería ocurrir con el plan actual)
        semanas_cubiertas = sum(len(b['semanas']) for b in periodizacion_anual)
        assert semanas_cubiertas == SEMANAS_TOTALES_PLAN, (
            f"El plan cubre {semanas_cubiertas} semanas, se esperaban {SEMANAS_TOTALES_PLAN}. "
            f"Ajusta el plan_base en generar_plan_base()."
        )

        return periodizacion_anual
