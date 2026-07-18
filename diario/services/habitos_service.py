# diario/services/habitos_service.py
#
# Phase Hábitos 2.0D: HabitosService reescrito como punto único sobre
# Gesto/RegistroGesto. Sustituye la lógica previa basada en
# ProsocheHabito/ProsocheHabitoDia (que sigue existiendo como legacy,
# pero ya no es la fuente de datos del dashboard de gestos).

import calendar

from django.db.models import Q
from django.utils import timezone

from ..models import Gesto, PausaGesto, RegistroGesto


class HabitosService:
    """Servicio centralizado para lógica de gestos (Phase 2.0D)."""

    @staticmethod
    def obtener_gestos_por_tipo(usuario):
        """
        Devuelve los Gesto visibles del usuario separados por tipo.

        Fase 5B del CONTRATO_ANALIZADOR_GESTOS.md: cultivo incluye
        también 'pausado' (para poder reactivar desde el dashboard) —
        suelto se mantiene solo 'activo', deliberadamente fuera de este
        cambio. 'cerrado' nunca aparece aquí en ningún tipo — ver
        obtener_gestos_cerrados_cultivo().

        Retorna {'cultivo': [Gesto, ...], 'suelto': [Gesto, ...]}.
        """
        gestos = Gesto.objects.filter(usuario=usuario).filter(
            Q(tipo='cultivo', estado__in=('activo', 'pausado')) | Q(tipo='suelto', estado='activo')
        )
        resultado = {'cultivo': [], 'suelto': []}
        for gesto in gestos:
            resultado.setdefault(gesto.tipo, []).append(gesto)
        return resultado

    @staticmethod
    def obtener_gestos_cerrados_cultivo(usuario):
        """Gesto tipo='cultivo' cerrados — lectura, sin acciones (cerrar
        es definitivo, no existe transición inversa). suelto queda fuera
        a propósito, igual que en obtener_gestos_por_tipo."""
        return Gesto.objects.filter(usuario=usuario, tipo='cultivo', estado='cerrado').order_by('-fecha_cierre')

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
    def pausar_gesto(gesto, fecha=None):
        """
        Pausa un Gesto (Fase 3): pone estado='pausado' y abre una
        PausaGesto(fecha_inicio=fecha, fecha_fin=None). Idempotente — si
        ya hay una pausa abierta, no crea una segunda (la restricción de
        unicidad de PausaGesto lo impediría de todas formas).
        """
        fecha = fecha or timezone.localdate()
        if not gesto.pausas.filter(fecha_fin__isnull=True).exists():
            PausaGesto.objects.create(gesto=gesto, fecha_inicio=fecha, fecha_fin=None)
        if gesto.estado != 'pausado':
            gesto.estado = 'pausado'
            gesto.save(update_fields=['estado'])

    @staticmethod
    def reactivar_gesto(gesto, fecha=None):
        """
        Reactiva un Gesto pausado (Fase 3): cierra la pausa abierta y
        pone estado='activo'. Si la pausa se abrió y se cierra el mismo
        día, el intervalo [fecha, fecha) no contiene ningún día bajo
        semántica semiabierta y no aporta información — se borra en vez
        de guardarse con fecha_fin=fecha_inicio.
        """
        fecha = fecha or timezone.localdate()
        HabitosService._cerrar_pausa_abierta(gesto, fecha)
        if gesto.estado != 'activo':
            gesto.estado = 'activo'
            gesto.save(update_fields=['estado'])

    @staticmethod
    def _cerrar_pausa_abierta(gesto, fecha):
        """Cierra la PausaGesto abierta de un gesto en `fecha`, si existe.
        Colapsa (borra) el intervalo si fecha_inicio == fecha."""
        pausa_abierta = gesto.pausas.filter(fecha_fin__isnull=True).first()
        if pausa_abierta is None:
            return
        if pausa_abierta.fecha_inicio == fecha:
            pausa_abierta.delete()
        else:
            pausa_abierta.fecha_fin = fecha
            pausa_abierta.save(update_fields=['fecha_fin'])

    @staticmethod
    def generar_insights_basicos(gesto):
        """Genera insights básicos sobre el progreso de un Gesto.

        Fase 5A del CONTRATO_ANALIZADOR_GESTOS.md: la racha solo es una
        lectura honesta para tipo_cadencia='diaria' (suelto no tiene
        cadencia y queda fuera de esta política — su racha ya era
        correcta antes del analizador)."""
        insights = []
        racha = gesto.get_racha_actual()

        if racha >= 3:
            if gesto.tipo == 'suelto':
                insights.append({
                    'tipo': 'motivacion',
                    'mensaje': f"Llevas {racha} días consecutivos sin {gesto.nombre}. Mantén el impulso."
                })
            elif gesto.tipo_cadencia == Gesto.CADENCIA_DIARIA:
                insights.append({
                    'tipo': 'motivacion',
                    'mensaje': f"Racha de {racha} días con {gesto.nombre}. La consistencia es clave."
                })

        return insights
