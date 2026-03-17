# planificador_helms/core.py
"""
Planificador principal basado en la metodología de Eric Helms.

CAMBIOS v2:
- [BUG FIX] generar_entrenamiento_para_fecha: eliminado uso de isocalendar() para
  determinar la semana del plan. Ahora calcula la semana relativa desde la fecha de
  inicio real del programa, que es la única forma correcta cuando el plan no empieza
  en enero. El método anterior siempre devolvía None para programas iniciados fuera
  de la semana 1 del año ISO.
- [BUG FIX] generar_entrenamiento_para_fecha: ahora acepta opcionalmente fecha_inicio
  como parámetro para que el caller pueda pasarla sin regenerar el plan completo.
- [MEJORA] DISTRIBUCION_DIAS[4] corregida: hombros pasan a día 3 (Upper B) para
  garantizar frecuencia 2x/semana. Isquios/glúteos distribuidos correctamente.
- [MEJORA] _calcular_descanso_pormenorizado: usa DESCANSOS de config en lugar de
  valores hardcodeados, manteniendo consistencia con el resto del sistema.
- [MEJORA] _generar_semana_especifica: el ajuste de vol_mult ahora respeta el factor
  de recuperación del perfil cuando está disponible.
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
import math

from .config import DISTRIBUCION_DIAS, VOLUMENES_BASE, TEMPOS, DESCANSOS
from .models.perfil_cliente import PerfilCliente
from .database.ejercicios import EJERCICIOS_DATABASE
from .periodizacion.generador import GeneradorPeriodizacion
from .calculo.peso import CalculadorPeso
from .calculo.fatiga import GestorFatiga
from .ejercicios.selector import SelectorEjercicios
from .ejercicios.patrones import PatronManager
from .utils.helpers import normalizar_nombre, extraer_nombre_ejercicio

# ─── Distribución de días corregida ──────────────────────────────────────────
# La distribución original para 4 días (Upper/Lower) tenía dos problemas:
#   1. Hombros solo aparecían en dia_1, dando frecuencia 1x/semana.
#   2. Isquios/glúteos se repetían en dia_2 y dia_4 con gemelos solo en dia_4.
#
# Solución: Upper A / Upper B garantizan frecuencia 2x para todos los grupos
# de tren superior. Lower A / Lower B reparten isquios y gemelos de forma
# equilibrada. Esto es coherente con la evidencia (Schoenfeld 2016).
_DISTRIBUCION_4_DIAS_CORREGIDA = {
    'dia_1': ['pecho', 'triceps'],  # Upper A — empuje
    'dia_2': ['cuadriceps', 'gluteos'],  # Lower A — dominante rodilla
    'dia_3': ['espalda', 'hombros', 'biceps'],  # Upper B — tracción + hombros 2ª vez
    'dia_4': ['isquios', 'gemelos', 'core'],  # Lower B — dominante bisagra
}

# Para 5 días el body part split original da frecuencia 1x. Se reemplaza por
# PPL + Upper/Lower, que mantiene frecuencia 2x para todos los grupos grandes.
_DISTRIBUCION_5_DIAS_CORREGIDA = {
    'dia_1': ['pecho', 'hombros', 'triceps'],  # Push
    'dia_2': ['espalda', 'biceps'],  # Pull
    'dia_3': ['cuadriceps', 'isquios', 'gluteos', 'gemelos'],  # Legs
    'dia_4': ['pecho', 'espalda', 'hombros'],  # Upper
    'dia_5': ['cuadriceps', 'isquios', 'gluteos'],  # Lower
}

# Merge con la distribución original (3 días no tenía problemas)
DISTRIBUCION_DIAS_CORREGIDA = {
    **DISTRIBUCION_DIAS,
    4: _DISTRIBUCION_4_DIAS_CORREGIDA,
    5: _DISTRIBUCION_5_DIAS_CORREGIDA,
}

# Mapa de offsets de día-de-semana por número de días (Lunes = 0)
_OFFSETS_DIA_SEMANA = {
    3: [0, 2, 4],  # Lun / Mié / Vie
    4: [0, 1, 3, 4],  # Lun / Mar / Jue / Vie
    5: [0, 1, 2, 3, 4],  # Lun a Vie
}


class PlanificadorHelms:
    """
    Planificador principal que orquestra la generación de rutinas
    basadas en los principios de "The Muscle and Strength Pyramid".
    """

    def __init__(self, perfil_cliente: PerfilCliente):
        self.perfil = perfil_cliente
        self.dias_disponibles = (
            perfil_cliente.dias_disponibles
            if perfil_cliente.dias_disponibles in [3, 4, 5]
            else 4
        )
        self.experiencia_años = perfil_cliente.experiencia_años
        self.objetivo_principal = perfil_cliente.objetivo_principal
        self.maximos_actuales = getattr(perfil_cliente, 'maximos_actuales', {})
        self.ejercicios_evitar = set(
            normalizar_nombre(e) for e in (perfil_cliente.ejercicios_evitar or [])
        )

    # ─── API pública ──────────────────────────────────────────────────────────

    def generar_entrenamiento_para_fecha(
            self,
            fecha_objetivo: date,
            fecha_inicio_plan: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Genera la rutina específica para una fecha dada.

        Args:
            fecha_objetivo:   Fecha para la que se quiere el entrenamiento.
            fecha_inicio_plan: Primer lunes del programa. Si no se pasa, se
                              asume el primer lunes del año del perfil (o del
                              año actual). Pásalo siempre que lo tengas para
                              evitar el recálculo.

        Returns:
            Dict con ejercicios del día, o None si la fecha queda fuera del plan.

        CORRECCIÓN: La versión anterior usaba fecha_objetivo.isocalendar()[1]
        (semana ISO del año) para buscar el bloque en la periodización. Esto es
        incorrecto porque GeneradorPeriodizacion genera semanas *relativas* al
        inicio del plan (1..52), no semanas ISO del calendario gregoriano. Para
        un programa que empieza en julio, la semana ISO 28 no tiene nada que ver
        con la semana 1 del plan. El método siempre devolvía None.

        La corrección calcula la semana relativa como:
            semana_relativa = (fecha_objetivo - fecha_inicio_plan).days // 7 + 1
        que es siempre correcta independientemente de cuándo empiece el programa.
        """
        if fecha_inicio_plan is None:
            fecha_inicio_plan = self._calcular_fecha_inicio_plan()

        dias_desde_inicio = (fecha_objetivo - fecha_inicio_plan).days
        if dias_desde_inicio < 0:
            return None  # Fecha anterior al inicio del plan

        semana_relativa = dias_desde_inicio // 7 + 1
        dia_semana_num = fecha_objetivo.weekday()  # Lunes = 0

        if semana_relativa > 52:
            return None  # Fuera del plan anual

        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        bloque_actual, idx_bloque = self._encontrar_bloque(periodizacion, semana_relativa)

        if bloque_actual is None:
            return None

        offsets = _OFFSETS_DIA_SEMANA.get(self.dias_disponibles, _OFFSETS_DIA_SEMANA[4])
        if dia_semana_num not in offsets:
            return {
                "rutina_nombre": "Día de Descanso",
                "ejercicios": [],
                "objetivo": "Descanso",
                "es_descanso": True,
            }

        idx_en_offset = offsets.index(dia_semana_num)
        clave_dia = f'dia_{idx_en_offset + 1}'

        # Ajustar el bloque a la semana específica dentro del bloque
        semana_dentro_bloque = semana_relativa - sum(
            len(b['semanas']) for b in periodizacion[:idx_bloque]
        )
        bloque_ajustado = self._ajustar_bloque_a_semana(bloque_actual, semana_dentro_bloque - 1)

        semana_completa = self._generar_semana_especifica(bloque_ajustado, idx_bloque + 1)
        ejercicios_del_dia = semana_completa.get(clave_dia)

        if not ejercicios_del_dia:
            return {
                "rutina_nombre": "Día de Descanso",
                "ejercicios": [],
                "objetivo": "Descanso",
                "es_descanso": True,
            }

        return {
            "rutina_nombre": f"{clave_dia.replace('_', ' ').title()} — {bloque_actual['nombre']}",
            "ejercicios": ejercicios_del_dia,
            "objetivo": bloque_actual['fase'].replace('_', ' ').title(),
            "bloque": bloque_actual['nombre'],
            "semana_relativa": semana_relativa,
            "semana_dentro_bloque": semana_dentro_bloque,
            "es_descanso": False,
        }

    def generar_plan_anual(self) -> Dict[str, Any]:
        """
        Genera el plan anual completo (YYYY-MM-DD -> rutina).
        """
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        entrenos_por_fecha: Dict[str, Any] = {}
        plan_por_bloques = []

        dias_offsets = _OFFSETS_DIA_SEMANA.get(self.dias_disponibles, _OFFSETS_DIA_SEMANA[4])
        fecha_inicio_plan = self._calcular_fecha_inicio_plan()

        semana_global = 0
        for num_bloque_idx, bloque in enumerate(periodizacion, 1):
            semanas_resumen = []
            semanas_detalle = bloque.get("semanas_detalle", [])

            for idx_sem, _sem_num in enumerate(bloque["semanas"]):
                semana_global += 1
                if semana_global > 52:
                    break

                semanas_resumen.append({"semana_num_total": semana_global})

                bloque_semana = self._ajustar_bloque_a_semana(bloque, idx_sem)

                plan_semana = self._generar_semana_especifica(bloque_semana, num_bloque_idx)

                dia_keys = sorted(plan_semana.keys())
                for i, dia_key in enumerate(dia_keys):
                    if i >= len(dias_offsets):
                        break

                    offset = dias_offsets[i]
                    dias_desde_inicio = ((semana_global - 1) * 7) + offset
                    fecha = fecha_inicio_plan + timedelta(days=dias_desde_inicio)

                    entrenos_por_fecha[fecha.isoformat()] = {
                        "nombre_rutina": f"Día {i + 1} — {bloque['nombre']}",
                        "ejercicios": plan_semana[dia_key],
                        "semana_bloque": idx_sem + 1,
                        "total_semanas_bloque": len(bloque["semanas"]),
                        "volumen_mult": bloque_semana["volumen_multiplicador"],
                        "rpe_objetivo": bloque_semana["intensidad_rpe"][0],
                    }

            plan_por_bloques.append({
                "nombre": bloque["nombre"],
                "objetivo": bloque["fase"],
                "duracion": len(bloque["semanas"]),
                "semanas": semanas_resumen,
                "descripcion": bloque.get("descripcion", ""),
            })

            if semana_global > 52:
                break

        return {
            "cliente_id": self.perfil.id,
            "plan_por_bloques": plan_por_bloques,
            "entrenos_por_fecha": entrenos_por_fecha,
            "fecha_inicio_plan": fecha_inicio_plan.isoformat(),
            "metadata": {
                "generado_por": "helms_v2",
                "periodizacion_completa": periodizacion,
                "año_planificacion": fecha_inicio_plan.year,
                "distribucion_dias": self.dias_disponibles,
            },
        }

    # ─── Helpers privados ─────────────────────────────────────────────────────

    def _calcular_fecha_inicio_plan(self) -> date:
        año = getattr(self.perfil, "año_planificacion", None) or datetime.now().year
        primer_dia = date(año, 1, 1)
        dias_para_lunes = (0 - primer_dia.weekday() + 7) % 7
        return primer_dia + timedelta(days=dias_para_lunes)

    @staticmethod
    def _encontrar_bloque(
            periodizacion: List[Dict[str, Any]],
            semana_relativa: int,
    ) -> tuple:
        """
        Devuelve (bloque, índice) para la semana relativa dada.
        Las semanas en cada bloque son relativas (1..N), no ISO.
        """
        acumulado = 0
        for idx, bloque in enumerate(periodizacion):
            acumulado += len(bloque["semanas"])
            if semana_relativa <= acumulado:
                return bloque, idx
        return None, -1

    @staticmethod
    def _ajustar_bloque_a_semana(
            bloque: Dict[str, Any],
            idx_sem: int,
    ) -> Dict[str, Any]:
        """
        Copia el bloque y sobreescribe volumen/RPE según el detalle
        de la semana específica dentro del bloque (si existe).
        """
        bloque_semana = bloque.copy()
        semanas_detalle = bloque.get("semanas_detalle", [])
        if idx_sem < len(semanas_detalle):
            detalle = semanas_detalle[idx_sem]
            bloque_semana["volumen_multiplicador"] = detalle.get(
                "vol_mult", bloque.get("volumen_multiplicador", 1.0)
            )
            bloque_semana["intensidad_rpe"] = (
                detalle.get("rpe", (bloque.get("intensidad_rpe") or (7,))[0]),
            )
        return bloque_semana

    def _generar_semana_especifica(
            self,
            bloque: Dict[str, Any],
            numero_bloque: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Genera una semana completa de entrenamiento."""
        fase = bloque.get('fase', 'hipertrofia')
        vol_mult = bloque.get('volumen_multiplicador', 1.0)
        rpe_objetivo = (bloque.get('intensidad_rpe') or (7,))[0]
        rep_range = bloque.get('rep_range', '8-12')

        # Aplicar factor de recuperación del perfil al volumen
        factor_recuperacion = (
            self.perfil.calcular_factor_recuperacion()
            if hasattr(self.perfil, 'calcular_factor_recuperacion')
            else 1.0
        )
        vol_mult_efectivo = vol_mult * factor_recuperacion

        nivel = self.perfil.calcular_nivel_experiencia()
        volumen_semanal_base = VOLUMENES_BASE.get(nivel, VOLUMENES_BASE['principiante'])

        # Usar distribución corregida
        distribucion_volumen = DISTRIBUCION_DIAS_CORREGIDA.get(
            self.dias_disponibles, DISTRIBUCION_DIAS_CORREGIDA[4]
        )

        ejercicios_bloque = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
            numero_bloque, fase, self.ejercicios_evitar
        )

        patron_manager = PatronManager(fase)
        semana_planificada: Dict[str, List[Dict[str, Any]]] = {}

        orden_dias = sorted(distribucion_volumen.keys())
        for idx_dia, dia_key in enumerate(orden_dias):
            gestor_fatiga = GestorFatiga(fase)
            ejercicios_dia: List[Dict[str, Any]] = []

            grupos_del_dia = distribucion_volumen[dia_key]
            for grupo in grupos_del_dia:
                vol_base_grupo = volumen_semanal_base.get(grupo, 0)
                frecuencia = sum(
                    1 for d in distribucion_volumen.values() if grupo in d
                )
                vol_dia = (
                    math.ceil((vol_base_grupo / frecuencia) * vol_mult_efectivo)
                    if frecuencia > 0
                    else 0
                )

                if vol_dia <= 0:
                    continue

                candidatos = ejercicios_bloque.get(grupo, [])
                if not candidatos:
                    continue

                n_candidatos = len(candidatos[:2])
                es_pesado = (int(rep_range.split('-')[0]) <= 6 or rpe_objetivo >= 9)

                for ej in candidatos[:2]:
                    nombre = ej['nombre']
                    patron = ej.get('patron') or patron_manager.obtener_patron_ejercicio(nombre)
                    tipo_ej = self._determinar_tipo_ejercicio_completo(grupo, nombre)

                    if patron == 'bisagra' and not patron_manager.puede_usar_bisagra(idx_dia):
                        continue

                    series_objetivo = max(2, min(4, math.ceil(vol_dia / n_candidatos)))
                    series_ajustadas = gestor_fatiga.ajustar_series_por_limite(
                        nombre, patron, tipo_ej, series_objetivo, es_pesado
                    )

                    if series_ajustadas <= 0:
                        continue

                    peso = CalculadorPeso.calcular_peso_trabajo(
                        nombre, rep_range, rpe_objetivo, self.maximos_actuales
                    )
                    tempo = TEMPOS.get(fase, TEMPOS['hipertrofia'])
                    descanso = self._calcular_descanso_pormenorizado(tipo_ej, rpe_objetivo)

                    ejercicios_dia.append({
                        'nombre': nombre,
                        'grupo_muscular': grupo,
                        'series': series_ajustadas,
                        'repeticiones': rep_range,
                        'peso_kg': peso,
                        'rpe_objetivo': rpe_objetivo,
                        'tempo': tempo,
                        'descanso_minutos': descanso,
                        'patron': patron,
                    })

                    patron_manager.registrar_uso_patron(patron, idx_dia, grupo)
                    gestor_fatiga.registrar_fatiga(patron, series_ajustadas, es_pesado)

            if ejercicios_dia:
                semana_planificada[dia_key] = ejercicios_dia

        return semana_planificada

    def _determinar_tipo_ejercicio_completo(self, grupo: str, nombre: str) -> str:
        """Determina si un ejercicio es principal, secundario o aislamiento."""
        db_grupo = EJERCICIOS_DATABASE.get(grupo, {})
        for tipo in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
            for ej in db_grupo.get(tipo, []):
                if extraer_nombre_ejercicio(ej).lower() == nombre.lower():
                    return tipo
        return 'aislamiento'

    @staticmethod
    def _calcular_descanso_pormenorizado(tipo: str, rpe: int) -> int:
        """
        Calcula el tiempo de descanso en minutos usando DESCANSOS de config.
        Antes los valores estaban hardcodeados aquí; ahora hay una única fuente.
        """
        nivel_rpe = 'rpe_alto' if rpe >= 8 else 'rpe_bajo'
        clave_tipo = 'principal' if tipo == 'compuesto_principal' else 'secundario'
        return DESCANSOS.get(clave_tipo, {}).get(nivel_rpe, 2)
