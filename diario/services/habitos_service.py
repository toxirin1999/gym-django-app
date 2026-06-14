# diario/services/habitos_service.py
#
# Phase Hábitos 2.0D: HabitosService reescrito como punto único sobre
# Gesto/RegistroGesto. Sustituye la lógica previa basada en
# ProsocheHabito/ProsocheHabitoDia (que sigue existiendo como legacy,
# pero ya no es la fuente de datos del dashboard de gestos).

import calendar

from django.utils import timezone

from ..models import Gesto, RegistroGesto


class HabitosService:
    """Servicio centralizado para lógica de gestos (Phase 2.0D)."""

    @staticmethod
    def obtener_gestos_por_tipo(usuario):
        """
        Devuelve los Gesto activos del usuario separados por tipo.

        Retorna {'cultivo': [Gesto, ...], 'suelto': [Gesto, ...]}.
        """
        gestos = Gesto.objects.filter(usuario=usuario, estado='activo')
        resultado = {'cultivo': [], 'suelto': []}
        for gesto in gestos:
            resultado.setdefault(gesto.tipo, []).append(gesto)
        return resultado

    @staticmethod
    def proyeccion_mensual(gesto, año, mes):
        """
        Devuelve la proyección de un Gesto para un mes/año dados como
        lista de dicts {'numero': dia, 'completado': bool}, en el formato
        que consume habitos_dashboard.html.
        """
        _, dias_en_mes = calendar.monthrange(año, mes)

        fechas_cumplidas = set(
            gesto.registros.filter(
                estado='cumplido',
                fecha__year=año,
                fecha__month=mes,
            ).values_list('fecha', flat=True)
        )

        proyeccion = []
        for dia_num in range(1, dias_en_mes + 1):
            fecha = timezone.datetime(año, mes, dia_num).date()
            proyeccion.append({
                'numero': dia_num,
                'completado': fecha in fechas_cumplidas,
            })
        return proyeccion

    @staticmethod
    def toggle_dia(gesto, fecha):
        """
        Alterna el registro de un Gesto para una fecha dada.

        Si existe un RegistroGesto(estado='cumplido') para esa fecha, lo
        elimina (toggle off) y devuelve False. Si no existe, lo crea
        (toggle on), recalcula mejor_racha y devuelve True.
        """
        registro = RegistroGesto.objects.filter(
            gesto=gesto, fecha=fecha, estado='cumplido'
        ).first()

        if registro:
            registro.delete()
            return False

        RegistroGesto.objects.update_or_create(
            gesto=gesto, fecha=fecha, defaults={'estado': 'cumplido'}
        )

        racha_actual = gesto.get_racha_actual()
        if racha_actual > gesto.mejor_racha:
            gesto.mejor_racha = racha_actual
            gesto.save(update_fields=['mejor_racha'])

        return True

    @staticmethod
    def generar_insights_basicos(gesto):
        """Genera insights básicos sobre el progreso de un Gesto."""
        insights = []
        racha = gesto.get_racha_actual()

        if racha >= 3:
            if gesto.tipo == 'suelto':
                insights.append({
                    'tipo': 'motivacion',
                    'mensaje': f"Llevas {racha} días consecutivos sin {gesto.nombre}. Mantén el impulso."
                })
            else:
                insights.append({
                    'tipo': 'motivacion',
                    'mensaje': f"Racha de {racha} días con {gesto.nombre}. La consistencia es clave."
                })

        return insights
