# planificador_helms/core.py
"""
Planificador principal basado en la metodología de Eric Helms.
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set
import logging
import math

logger = logging.getLogger(__name__)

from .config import DISTRIBUCION_DIAS, TEMPOS, REP_RANGE_AJUSTE_PEQUENOS, GRUPOS_GRANDES, TOPE_SERIES_POR_EJERCICIO, VOLUMENES_BASE
from .distribucion.asignador import GrupoParaAsignar, asignar_semana, AsignacionImposibleError
from .volumen.calculadora import calcular_volumen_optimo, CalculadoraVolumen
from .models.perfil_cliente import PerfilCliente
from .database.ejercicios import EJERCICIOS_DATABASE
from .periodizacion.generador import GeneradorPeriodizacion
from .calculo.peso import CalculadorPeso
from .calculo.compatibilidad_fase import resolver_peso_objetivo, resolver_ancla_historica, _bucket_desde_reps
from .calculo.fatiga import GestorFatiga
from .calculo.prescripcion_tipo import rpe_por_tipo, rango_por_tipo, unidad_por_tipo, carga_por_tipo
from .ejercicios.selector import SelectorEjercicios
from .ejercicios.patrones import PatronManager
from .ejercicios.variacion import derivar_rep_rpe_toque, construir_variantes_por_toque
from .utils.helpers import normalizar_nombre, extraer_nombre_ejercicio, extraer_patron_ejercicio
from entrenos.services.descanso_service import get_descanso_sugerido


class PlanificadorHelms:
    def __init__(self, perfil_cliente: PerfilCliente):
        self.perfil = perfil_cliente
        self.dias_disponibles = self.perfil.dias_disponibles if self.perfil.dias_disponibles in [3, 4, 5, 6] else 4
        self.experiencia_años = perfil_cliente.experiencia_años
        self.objetivo_principal = perfil_cliente.objetivo_principal
        self.maximos_actuales = getattr(perfil_cliente, 'maximos_actuales', {})
        self.ejercicios_evitar = set(normalizar_nombre(e) for e in (perfil_cliente.ejercicios_evitar or []))

    def _semana_dinamica(self, fecha_objetivo: date):
        """Semana del plan según la periodización dinámica (paso 4), o None.

        Solo para clientes reales: si el perfil no corresponde a un Cliente de
        la base de datos (tests, simulaciones) se usa el calendario fijo. Para
        fechas anteriores al arranque también (``legacy``).
        """
        if getattr(self, '_sin_dinamica', False):
            return None
        try:
            if not hasattr(self, '_cliente_dinamico'):
                from clientes.models import Cliente
                self._cliente_dinamico = Cliente.objects.filter(pk=self.perfil.id).first()
            if self._cliente_dinamico is None:
                return None
            from entrenos.services.periodizacion_dinamica_service import lunes_de, resolver_semana
            memo = self.__dict__.setdefault('_memo_semanas', {})
            clave = lunes_de(fecha_objetivo)
            if clave not in memo:
                memo[clave] = resolver_semana(self._cliente_dinamico, fecha_objetivo)
            info = memo[clave]
        except Exception:
            logger.exception('PlanificadorHelms: periodización dinámica no disponible')
            return None
        if info.get('legacy'):
            return None
        return info

    def _ajustes_volumen_grupo(self) -> Dict[str, int]:
        """Series extra por grupo que decide el entrenador (paso 5), solo clientes reales."""
        if '_ajustes_grupo' in self.__dict__:
            return self._ajustes_grupo
        self._ajustes_grupo = {}
        try:
            if not hasattr(self, '_cliente_dinamico'):
                from clientes.models import Cliente
                self._cliente_dinamico = Cliente.objects.filter(pk=self.perfil.id).first()
            if self._cliente_dinamico is not None:
                from django.utils import timezone
                from entrenos.services.volumen_grupo_service import series_por_grupo
                self._ajustes_grupo = series_por_grupo(self._cliente_dinamico, timezone.localdate())
        except Exception:
            logger.exception('PlanificadorHelms: ajustes de volumen por grupo no disponibles')
        return self._ajustes_grupo

    def generar_entrenamiento_para_fecha(self, fecha_objetivo: date) -> Optional[Dict[str, Any]]:
        info_dinamica = self._semana_dinamica(fecha_objetivo)
        if info_dinamica is not None:
            return self._generar_entrenamiento_dinamico(fecha_objetivo, info_dinamica)
        try:
            # Bug 1 fix: usar semana RELATIVA al plan, no semana ISO del calendario
            año_planificacion = getattr(self.perfil, 'año_planificacion', None) or datetime.now().year
            primer_dia_del_año = date(año_planificacion, 1, 1)
            dias_para_lunes = (0 - primer_dia_del_año.weekday() + 7) % 7
            fecha_inicio_plan = primer_dia_del_año + timedelta(days=dias_para_lunes)
            semana_num_total = (fecha_objetivo - fecha_inicio_plan).days // 7 + 1
            dia_semana_num = fecha_objetivo.weekday()
        except Exception:
            return None

        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        bloque_actual = next((b for b in periodizacion if semana_num_total in b.get('semanas', [])), None)
        if not bloque_actual:
            return None
        # Índice calculado ANTES de copiar/modificar bloque_actual más abajo —
        # tras el fix de progresión, bloque_actual deja de ser == al objeto
        # original de la lista, así que periodizacion.index(bloque_actual)
        # ya no lo encontraría (o encontraría el índice equivocado).
        numero_bloque = periodizacion.index(bloque_actual) + 1

        # Fix: usar el volumen_multiplicador PROGRESIVO de esta semana concreta
        # dentro del bloque (semanas_detalle), no el vol_fin fijo del bloque
        # entero. Sin esto, la primera semana de un bloque de 7 recibía el
        # mismo volumen que la última — la progresión de carga no existía en
        # este camino (generar_plan_anual sí lo hacía bien, este no).
        semanas_del_bloque_actual = bloque_actual.get('semanas', [])
        idx_semana_en_bloque = (
            semanas_del_bloque_actual.index(semana_num_total)
            if semana_num_total in semanas_del_bloque_actual else 0
        )
        semanas_detalle_actual = bloque_actual.get('semanas_detalle', [])
        bloque_actual = bloque_actual.copy()
        if idx_semana_en_bloque < len(semanas_detalle_actual):
            detalle_semana = semanas_detalle_actual[idx_semana_en_bloque]
            bloque_actual['volumen_multiplicador'] = detalle_semana.get(
                'vol_mult', bloque_actual.get('volumen_multiplicador', 1.0)
            )
            bloque_actual['intensidad_rpe'] = (
                detalle_semana.get('rpe', bloque_actual.get('intensidad_rpe', (7,))[0]),
            )

        dias_entreno_keys = [f'dia_{i + 1}' for i in range(self.dias_disponibles)]
        if self.dias_disponibles == 3:
            dias_entreno_indices = [0, 2, 4]
        elif self.dias_disponibles == 5:
            dias_entreno_indices = [0, 1, 2, 3, 4]
        elif self.dias_disponibles == 6:
            dias_entreno_indices = [0, 1, 2, 3, 4, 5]
        else:
            dias_entreno_indices = [0, 1, 3, 4]

        if dia_semana_num not in dias_entreno_indices:
            return {"rutina_nombre": "Día de Descanso", "ejercicios": [], "objetivo": "Descanso"}

        idx_en_offset = dias_entreno_indices.index(dia_semana_num)
        clave_dia = dias_entreno_keys[idx_en_offset]
        semana_completa = self._generar_semana_especifica(bloque_actual, numero_bloque)
        ejercicios_del_dia = semana_completa.get(clave_dia)

        if not ejercicios_del_dia:
            return {"rutina_nombre": "Día de Descanso", "ejercicios": [], "objetivo": "Descanso"}

        semanas_del_bloque = bloque_actual.get('semanas', [])
        semana_en_bloque = (semanas_del_bloque.index(semana_num_total) + 1) if semana_num_total in semanas_del_bloque else 1

        return {
            "rutina_nombre": f"{clave_dia.replace('_', ' ').title()} - {bloque_actual['nombre']}",
            "ejercicios": ejercicios_del_dia,
            "objetivo": bloque_actual['fase'].replace('_', ' ').title(),
            "bloque": bloque_actual['nombre'],
            "dia": idx_en_offset + 1,
            "semana_nombre": f"Semana {semana_en_bloque}",
            "semana_en_bloque": semana_en_bloque,
        }

    def _generar_entrenamiento_dinamico(self, fecha_objetivo: date, info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Igual que el camino por calendario, pero con la semana ya resuelta."""
        from entrenos.services.periodizacion_dinamica_service import bloque_para_semana

        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        semana_num_total = info['semana_plan']
        bloque_actual, numero_bloque = bloque_para_semana(info, periodizacion)
        if not bloque_actual:
            return None
        semanas_del_bloque = bloque_actual.get('semanas', [])
        if semana_num_total in semanas_del_bloque:
            idx_semana_en_bloque = semanas_del_bloque.index(semana_num_total)
        else:
            idx_semana_en_bloque = 0  # descarga intercalada: su única semana
        detalle = bloque_actual.get('semanas_detalle', [])
        bloque_actual = bloque_actual.copy()
        if idx_semana_en_bloque < len(detalle):
            bloque_actual['volumen_multiplicador'] = detalle[idx_semana_en_bloque].get(
                'vol_mult', bloque_actual.get('volumen_multiplicador', 1.0)
            )
            bloque_actual['intensidad_rpe'] = (
                detalle[idx_semana_en_bloque].get('rpe', bloque_actual.get('intensidad_rpe', (7,))[0]),
            )

        dias_entreno_indices = {3: [0, 2, 4], 5: [0, 1, 2, 3, 4], 6: [0, 1, 2, 3, 4, 5]}.get(
            self.dias_disponibles, [0, 1, 3, 4]
        )
        dia_semana_num = fecha_objetivo.weekday()
        if dia_semana_num not in dias_entreno_indices:
            return {"rutina_nombre": "Día de Descanso", "ejercicios": [], "objetivo": "Descanso"}
        idx_en_offset = dias_entreno_indices.index(dia_semana_num)
        clave_dia = f'dia_{idx_en_offset + 1}'
        semana_completa = self._generar_semana_especifica(bloque_actual, numero_bloque)
        ejercicios_del_dia = semana_completa.get(clave_dia)
        if not ejercicios_del_dia:
            return {"rutina_nombre": "Día de Descanso", "ejercicios": [], "objetivo": "Descanso"}
        semana_en_bloque = idx_semana_en_bloque + 1
        return {
            "rutina_nombre": f"{clave_dia.replace('_', ' ').title()} - {bloque_actual['nombre']}",
            "ejercicios": ejercicios_del_dia,
            "objetivo": bloque_actual['fase'].replace('_', ' ').title(),
            "bloque": bloque_actual['nombre'],
            "dia": idx_en_offset + 1,
            "semana_nombre": f"Semana {semana_en_bloque}",
            "semana_en_bloque": semana_en_bloque,
            "semana_plan": semana_num_total,
            "periodizacion": {
                'origen': info.get('origen'),
                'motivo': info.get('motivo'),
                'descarga': bool(info.get('descarga')),
                'proyectada': bool(info.get('proyectada')),
            },
        }

    def generar_plan_anual(self) -> Dict[str, Any]:
        from django.core.cache import cache as _djcache
        _año = getattr(self.perfil, 'año_planificacion', None) or datetime.now().year
        _ck = f'plan_anual_{self.perfil.id}_{self.dias_disponibles}_{self.objetivo_principal}_{_año}'
        _cached = _djcache.get(_ck)
        if _cached is not None:
            return _cached

        self._precargar_historial_ejercicios()
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        entrenos_por_fecha = {}
        plan_por_bloques = []

        if self.dias_disponibles == 3:
            dias_offsets = [0, 2, 4]
        elif self.dias_disponibles == 5:
            dias_offsets = [0, 1, 2, 3, 4]
        elif self.dias_disponibles == 6:
            dias_offsets = [0, 1, 2, 3, 4, 5]
        else:
            dias_offsets = [0, 1, 3, 4]

        año_planificacion = getattr(self.perfil, "año_planificacion", None) or datetime.now().year
        primer_dia_del_año = date(año_planificacion, 1, 1)
        dias_para_lunes = (0 - primer_dia_del_año.weekday() + 7) % 7
        fecha_inicio_plan = primer_dia_del_año + timedelta(days=dias_para_lunes)

        semana_global = 0
        for num_bloque_idx, bloque in enumerate(periodizacion, 1):
            semanas_resumen = []
            semanas_detalle = bloque.get("semanas_detalle", [])

            for idx_sem, sem_num in enumerate(bloque["semanas"]):
                semana_global += 1
                if semana_global > 52: break

                semanas_resumen.append({"semana_num_total": semana_global})

                bloque_semana = bloque.copy()
                if idx_sem < len(semanas_detalle):
                    detalle = semanas_detalle[idx_sem]
                    bloque_semana["volumen_multiplicador"] = detalle.get("vol_mult",
                                                                         bloque.get("volumen_multiplicador", 1.0))
                    bloque_semana["intensidad_rpe"] = (detalle.get("rpe", bloque.get("intensidad_rpe", (7,))[0]),)

                plan_semana = self._generar_semana_especifica(bloque_semana, num_bloque_idx)

                dia_keys = sorted(plan_semana.keys())
                for i, dia_key in enumerate(dia_keys):
                    if i >= len(dias_offsets): break
                    offset = dias_offsets[i]
                    dias_desde_inicio = ((semana_global - 1) * 7) + offset
                    fecha = fecha_inicio_plan + timedelta(days=dias_desde_inicio)
                    entrenos_por_fecha[fecha.isoformat()] = {
                        "nombre_rutina": f"Día {i + 1} - {bloque['nombre']}",
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
            if semana_global > 52: break

        self._aplicar_semanas_dinamicas(entrenos_por_fecha, fecha_inicio_plan, dias_offsets, periodizacion)

        _result = {
            "cliente_id": self.perfil.id,
            "plan_por_bloques": plan_por_bloques,
            "entrenos_por_fecha": entrenos_por_fecha,
            "metadata": {
                "generado_por": "helms_refactored",
                "periodizacion_completa": periodizacion,
                "año_planificacion": año_planificacion,
            },
        }
        _djcache.set(_ck, _result, 3600)  # 1 hora
        return _result

    def _aplicar_semanas_dinamicas(self, entrenos_por_fecha, fecha_inicio_plan, dias_offsets, periodizacion):
        """Sustituye en el plan anual las semanas que decide la periodización dinámica.

        Las semanas anteriores al arranque se quedan como en el calendario; desde
        ahí, cada semana usa la que resolvió (o proyecta) el servicio dinámico,
        para que el Plan y el calendario enseñen lo mismo que la sesión del día.
        """
        if self._semana_dinamica(fecha_inicio_plan + timedelta(days=7 * 51)) is None:
            return
        from entrenos.services.periodizacion_dinamica_service import bloque_para_semana

        for k in range(52):
            lunes = fecha_inicio_plan + timedelta(days=7 * k)
            info = self._semana_dinamica(lunes)
            if info is None:
                continue
            bloque, numero_bloque = bloque_para_semana(info, periodizacion)
            if not bloque:
                continue
            semanas = bloque.get('semanas', [])
            idx = semanas.index(info['semana_plan']) if info['semana_plan'] in semanas else 0
            bloque_semana = bloque.copy()
            detalle = bloque.get('semanas_detalle', [])
            if idx < len(detalle):
                bloque_semana['volumen_multiplicador'] = detalle[idx].get(
                    'vol_mult', bloque.get('volumen_multiplicador', 1.0))
                bloque_semana['intensidad_rpe'] = (
                    detalle[idx].get('rpe', bloque.get('intensidad_rpe', (7,))[0]),)
            plan_semana = self._generar_semana_especifica(bloque_semana, numero_bloque)
            for offset in dias_offsets:
                entrenos_por_fecha.pop((lunes + timedelta(days=offset)).isoformat(), None)
            for i, dia_key in enumerate(sorted(plan_semana.keys())):
                if i >= len(dias_offsets):
                    break
                fecha = lunes + timedelta(days=dias_offsets[i])
                entrenos_por_fecha[fecha.isoformat()] = {
                    "nombre_rutina": f"Día {i + 1} - {bloque['nombre']}",
                    "ejercicios": plan_semana[dia_key],
                    "semana_bloque": idx + 1,
                    "total_semanas_bloque": len(semanas) or 1,
                    "volumen_mult": bloque_semana["volumen_multiplicador"],
                    "rpe_objetivo": bloque_semana["intensidad_rpe"][0],
                    "periodizacion": {'origen': info.get('origen'), 'descarga': bool(info.get('descarga'))},
                }

    def _generar_semana_especifica(self, bloque: Dict[str, Any], numero_bloque: int) -> Dict[str, List[Dict[str, Any]]]:
        ajustes_grupo = self._ajustes_volumen_grupo()
        _cache_key = (
            numero_bloque, bloque.get('fase', ''), bloque.get('volumen_multiplicador', 1.0),
            tuple(sorted(ajustes_grupo.items())),
        )
        if not hasattr(self, '_semana_cache'):
            self._semana_cache = {}
        if _cache_key in self._semana_cache:
            return self._semana_cache[_cache_key]

        fase = bloque.get('fase', 'hipertrofia')
        vol_mult = bloque.get('volumen_multiplicador', 1.0)
        rpe_objetivo = (bloque.get('intensidad_rpe') or (7,))[0]
        rep_range = bloque.get('rep_range', '8-12')

        nivel = self.perfil.calcular_nivel_experiencia()
        objetivo = self.perfil.objetivo_principal
        factor_recuperacion = self.perfil.calcular_factor_recuperacion()
        # Bug 8 fix: pasar objeto cliente para que BioContext filtre ejercicios con lesiones activas
        if not hasattr(self, '_cliente_obj'):
            try:
                from clientes.models import Cliente
                self._cliente_obj = Cliente.objects.get(pk=self.perfil.id)
            except Exception:
                self._cliente_obj = None
        cliente_obj = self._cliente_obj
        ejercicios_bloque = SelectorEjercicios.seleccionar_ejercicios_para_bloque(
            numero_bloque, fase, self.ejercicios_evitar, cliente=cliente_obj
        )
        patron_manager = PatronManager(fase)
        semana_planificada = {}

        # X.4: leer max_ej_por_grupo desde SelectorEjercicios como fuente única
        # (en lugar del [:2] literal que vivía en paralelo al valor de selector.py).
        reglas_fase = SelectorEjercicios.obtener_reglas_por_fase(fase)
        n_ejercicios_grupo = reglas_fase['max_ej_por_grupo']
        tope_por_ejercicio = TOPE_SERIES_POR_EJERCICIO.get(fase, 4)

        # X.7: construir GrupoParaAsignar para cada grupo activo y llamar al motor.
        # El volumen efectivo (vol_base × vol_mult, acotado a MRV) determina la
        # frecuencia deseada. Si el motor lanza AsignacionImposibleError,
        # DISTRIBUCION_DIAS es el fallback — se loggea para detectar perfiles que
        # saturan el motor en producción.
        grupos_para_asignar = {}
        for grupo in VOLUMENES_BASE.get(nivel, VOLUMENES_BASE['avanzado']):
            vol_base_grupo = calcular_volumen_optimo(grupo, nivel, objetivo, factor_recuperacion)
            if vol_base_grupo <= 0:
                continue
            candidatos_grupo = ejercicios_bloque.get(grupo, [])
            if not candidatos_grupo:
                continue
            mrv_g = CalculadoraVolumen.calcular_volumen_maximo_adaptativo(grupo, nivel)
            # Mismo redondeo que el reparto por toques (ceil): si no, el
            # asignador decidía la frecuencia con 8 series y la sesión llevaba 9.
            vol_efectivo = math.ceil(min(vol_base_grupo * vol_mult, mrv_g))
            if grupo in ajustes_grupo:  # paso 5: ajuste del entrenador, acotado a MRV
                vol_efectivo = max(1, min(vol_efectivo + ajustes_grupo[grupo], mrv_g))
            if vol_efectivo <= 0:
                continue
            primer_ej = candidatos_grupo[0]
            patron_dom = primer_ej.get('patron') or patron_manager.obtener_patron_ejercicio(primer_ej['nombre'])
            variante = (
                PatronManager.clasificar_variante_bisagra(primer_ej['nombre'])
                if patron_dom == 'bisagra'
                else None
            )
            grupos_para_asignar[grupo] = GrupoParaAsignar(
                nombre=grupo,
                volumen_objetivo=vol_efectivo,
                mev=CalculadoraVolumen.calcular_volumen_mantenimiento(grupo, nivel),
                es_grande=grupo in GRUPOS_GRANDES,
                patron_dominante=patron_dom,
                variante_peso=variante,
            )

        try:
            resultado = asignar_semana(grupos_para_asignar, self.dias_disponibles)
            distribucion_volumen = resultado.asignacion
            frecuencia_map: dict | None = resultado.frecuencia_efectiva
            volumen_efectivo_map: dict = resultado.volumen_efectivo or {}
        except AsignacionImposibleError as exc:
            logger.warning(
                "Motor de asignación falló (perfil id=%s, dias=%d): %s — "
                "usando DISTRIBUCION_DIAS como fallback.",
                self.perfil.id, self.dias_disponibles, exc,
            )
            distribucion_volumen = DISTRIBUCION_DIAS.get(self.dias_disponibles, DISTRIBUCION_DIAS[4])
            frecuencia_map = None
            volumen_efectivo_map = {}

        # X.14: construir variantes por toque para grupos con frecuencia≥2.
        # Solo se activa cuando el motor resolvió frecuencia_map con éxito.
        # Si frecuencia_map es None (fallback DISTRIBUCION_DIAS tras AsignacionImposibleError),
        # todos los toques usan toque=1 — sin variación intra-semanal.
        plan_variantes: dict = {}
        if frecuencia_map is not None:
            for grupo, freq_grupo in frecuencia_map.items():
                if freq_grupo < 2:
                    continue
                candidatos_grupo_completos = ejercicios_bloque.get(grupo, [])
                if not candidatos_grupo_completos:
                    continue
                ejercicios_toque1 = candidatos_grupo_completos[:n_ejercicios_grupo]
                pool_seguro = SelectorEjercicios.construir_pool_seguro_por_grupo(
                    grupo, fase, cliente=cliente_obj
                )
                plan_variantes[grupo] = construir_variantes_por_toque(
                    grupo, freq_grupo, grupo in GRUPOS_GRANDES, pool_seguro, ejercicios_toque1
                )

        toque_por_grupo: dict = {}
        orden_dias = sorted(distribucion_volumen.keys())
        es_descarga_bloque = (fase == 'descarga')
        for idx_dia, dia_key in enumerate(orden_dias):
            grupos_del_dia = distribucion_volumen[dia_key]

            # Suelo mínimo por grupo: MEV (series/semana) ÷ frecuencia semanal del grupo
            # = mínimo defendible por toque. Evita que GestorFatiga deje un grupo
            # programado en 0 series cuando hay más grupos ese día que presupuesto de
            # series pesadas — el presupuesto pasa a ser un objetivo blando que cede
            # ante el mínimo fisiológico real de cada grupo (ver Helms/RP: MEV/MV son
            # landmarks semanales, no una cifra arbitraria por sesión).
            # En descarga NO se aplica: caer bajo MEV ahí es intencional (ver nota
            # más abajo, "vol_ajustado_bloque"), reintroducir el suelo lo contradiría.
            pisos_minimos_dia = {}
            if not es_descarga_bloque:
                for grupo in grupos_del_dia:
                    frecuencia_grupo = (
                        frecuencia_map.get(grupo, 1)
                        if frecuencia_map is not None
                        else sum(1 for d in distribucion_volumen.values() if grupo in d)
                    )
                    mev_grupo = CalculadoraVolumen.calcular_volumen_mantenimiento(grupo, nivel)
                    pisos_minimos_dia[grupo] = (
                        max(1, math.ceil(mev_grupo / frecuencia_grupo)) if frecuencia_grupo > 0 else mev_grupo
                    )

            gestor_fatiga = GestorFatiga(fase, grupos_dia=grupos_del_dia, pisos_minimos=pisos_minimos_dia)
            ejercicios_dia = []

            for grupo in grupos_del_dia:
                volumen_objetivo_grupo = calcular_volumen_optimo(grupo, nivel, objetivo, factor_recuperacion)
                frecuencia = (
                    frecuencia_map.get(grupo, 1)
                    if frecuencia_map is not None
                    else sum(1 for d in distribucion_volumen.values() if grupo in d)
                )
                mrv_grupo = CalculadoraVolumen.calcular_volumen_maximo_adaptativo(grupo, nivel)
                vol_ajustado_bloque = volumen_objetivo_grupo * vol_mult
                # En descarga (vol_mult < 1.0), el resultado puede caer bajo MEV intencionalmente
                # — no reintroducir el suelo de MEV: el objetivo de la descarga es disipar fatiga,
                # no mantener el estímulo mínimo de adaptación.
                # 12-oct-2026: reparto exacto del volumen semanal entre toques
                # (y luego entre ejercicios). Con ceil en cada toque y en cada
                # ejercicio, un grupo a 3 toques inflaba su volumen por encima
                # del MRV (pecho 20 → 24). Ahora la suma de la semana es el
                # objetivo, repartido lo más parejo posible.
                vol_semana_grupo = math.ceil(min(vol_ajustado_bloque, mrv_grupo))
                if grupo in ajustes_grupo:  # paso 5: ajuste del entrenador, acotado a MRV
                    vol_semana_grupo = max(1, min(vol_semana_grupo + ajustes_grupo[grupo], mrv_grupo))
                if grupo in volumen_efectivo_map:
                    # Grupo sin sitio para todas sus sesiones: se respeta el
                    # límite por sesión y se pierde volumen, no se amontona.
                    vol_semana_grupo = min(vol_semana_grupo, volumen_efectivo_map[grupo])
                toque_previsto = toque_por_grupo.get(grupo, 0) + 1
                if frecuencia > 0:
                    base_toque, resto_toque = divmod(vol_semana_grupo, frecuencia)
                    vol_dia = base_toque + (1 if toque_previsto <= resto_toque else 0)
                else:
                    vol_dia = 0
                if vol_dia <= 0: continue

                candidatos_todos = ejercicios_bloque.get(grupo, [])
                if not candidatos_todos:
                    continue

                toque = toque_por_grupo.get(grupo, 0) + 1
                toque_por_grupo[grupo] = toque

                variantes_grupo = plan_variantes.get(grupo, {})
                candidatos = variantes_grupo.get(toque, candidatos_todos[:n_ejercicios_grupo])

                n_ej_toque = len(candidatos[:n_ejercicios_grupo])
                base_ej, resto_ej = divmod(vol_dia, n_ej_toque) if n_ej_toque else (0, 0)
                for idx_ej, ej in enumerate(candidatos[:n_ejercicios_grupo]):
                    nombre = ej['nombre']
                    patron = ej['patron'] or patron_manager.obtener_patron_ejercicio(nombre)
                    tipo_ej = self._determinar_tipo_ejercicio_completo(grupo, nombre)

                    if patron == 'bisagra' and not patron_manager.puede_usar_bisagra(idx_dia, nombre):
                        continue

                    # Ajustar rep_range según tamaño del músculo (evidencia: pequeños → reps más altas)
                    rep_range_ej = (
                        rep_range if grupo in GRUPOS_GRANDES
                        else REP_RANGE_AJUSTE_PEQUENOS.get(rep_range, rep_range)
                    )

                    # X.14: contraste por toque (toque 1 = identidad; toque ≥2 = reps más altas, RPE −1).
                    # Se aplica DESPUÉS del ajuste por tamaño de músculo para componer sin contradicción.
                    rep_range_ej, rpe_objetivo_toque = derivar_rep_rpe_toque(rep_range_ej, rpe_objetivo, toque)
                    # 18-oct-2026: zancadas y similares, por pierna y con tope de 12.
                    from entrenos.services.peso_semantica_service import rango_unilateral_pierna
                    rep_range_ej = rango_unilateral_pierna(nombre, rep_range_ej)

                    es_pesado = (int((rep_range_ej or '8-12').split('-')[0]) <= 6 or rpe_objetivo_toque >= 9)
                    # Decisión 12-oct-2026: RPE por tipo (multiarticular 7–8,
                    # aislamiento 8–9) y unidad real en tiempo/distancia. Se
                    # aplica después de es_pesado para no cambiar el reparto de
                    # fatiga: un aislamiento a RPE 9 no es una serie "pesada".
                    tipo_progresion_ej = ej.get('tipo_progresion', 'peso_reps')
                    rpe_objetivo_toque = rpe_por_tipo(rpe_objetivo_toque, patron, nombre, es_descarga_bloque)
                    rango_salida = rango_por_tipo(tipo_progresion_ej, rep_range_ej, es_descarga_bloque)
                    series_objetivo = max(2, min(tope_por_ejercicio, base_ej + (1 if idx_ej < resto_ej else 0)))
                    series_ajustadas = gestor_fatiga.ajustar_series_por_limite(
                        nombre, patron, tipo_ej, series_objetivo, es_pesado, grupo=grupo
                    )
                    if series_ajustadas <= 0: continue

                    # Obtener historial real del ejercicio
                    historial = self._obtener_historial_ejercicio(nombre)
                    rpe_real_anterior = historial['rpe_real']
                    peso_real_anterior = historial['peso_real']
                    reps_real_anterior = historial['reps_real']
                    peso_real_bruto_anterior = historial['peso_real_bruto']

                    es_descarga_hoy = (fase == 'descarga')

                    # Phase Gym Peso 2 — decisión dependiente de fase/bucket.
                    # Si el rango de reps de la última sesión real es de un
                    # bucket distinto al de hoy (o si hoy es descarga), el
                    # incremento fijo no tiene sentido: recalcular desde e1RM.
                    decision_fase = resolver_peso_objetivo(
                        peso_anterior=peso_real_anterior,
                        reps_anteriores=reps_real_anterior,
                        rpe_anterior=rpe_real_anterior,
                        rep_range_hoy=rep_range_ej,
                        rpe_objetivo_hoy=rpe_objetivo_toque,
                        es_descarga_hoy=es_descarga_hoy,
                        redondear_fn=lambda p: CalculadorPeso.redondear_peso(p, nombre),
                        peso_ultima_sesion=peso_real_bruto_anterior,
                    )

                    motivo_peso_tipo = 'sin_datos'
                    if decision_fase['aplica']:
                        peso = decision_fase['peso']
                        motivo_peso_tipo = decision_fase['motivo_tipo']
                    elif peso_real_anterior is not None and rpe_real_anterior is not None:
                        diferencia_rpe = rpe_real_anterior - rpe_objetivo
                        from analytics.planificador_helms.calculo.peso import PROGRESION, REDONDEO
                        if diferencia_rpe <= -2:
                            incremento = PROGRESION['fijo_grande']
                            motivo_peso_tipo = 'sube'
                        elif diferencia_rpe <= 0:
                            incremento = PROGRESION['fijo_pequeno']
                            motivo_peso_tipo = 'sube'
                        elif diferencia_rpe <= 2:
                            incremento = 0
                            motivo_peso_tipo = 'mantiene'
                        else:
                            incremento = -PROGRESION['fijo_pequeno']
                            motivo_peso_tipo = 'frenado'
                        peso_nuevo = peso_real_anterior + incremento
                        tipo = CalculadorPeso.inferir_tipo_carga(nombre)
                        inc = REDONDEO.get(tipo, REDONDEO['general'])
                        peso = math.ceil(peso_nuevo / inc) * inc if inc > 0 else round(peso_nuevo, 1)
                    else:
                        peso = CalculadorPeso.calcular_peso_trabajo(nombre, rep_range_ej, rpe_objetivo,
                                                                    self.maximos_actuales, rpe_real_anterior)

                    peso_por_tipo = carga_por_tipo(tipo_progresion_ej, nombre, peso, peso_real_bruto_anterior)
                    if peso_por_tipo != peso:
                        peso = peso_por_tipo
                        motivo_peso_tipo = 'carga_por_tipo'

                    tempo = TEMPOS.get(fase, TEMPOS['hipertrofia'])
                    descanso = self._calcular_descanso_pormenorizado(nombre, rpe_objetivo, tipo_ej, rep_range_ej)

                    motivo_peso_texto = self._construir_motivo_peso(motivo_peso_tipo, nombre)

                    ejercicios_dia.append({
                        'nombre': nombre,
                        'grupo_muscular': grupo,
                        'series': series_ajustadas,
                        'repeticiones': rango_salida,
                        'unidad': unidad_por_tipo(tipo_progresion_ej),
                        'peso_kg': peso,
                        'rpe_objetivo': rpe_objetivo_toque,
                        'tempo': tempo,
                        'descanso_minutos': descanso,
                        'patron': patron,
                        'tipo_progresion': tipo_progresion_ej,
                        'tipo_ejercicio': tipo_ej,
                        'motivo_peso': {
                            'tipo': motivo_peso_tipo,
                            'texto': motivo_peso_texto,
                        },
                    })

                    patron_manager.registrar_uso_patron(patron, idx_dia, grupo, nombre)
                    gestor_fatiga.registrar_fatiga(patron, series_ajustadas, es_pesado, grupo=grupo)

            if ejercicios_dia:
                semana_planificada[dia_key] = ejercicios_dia

        self._semana_cache[_cache_key] = semana_planificada
        return semana_planificada

    def _determinar_tipo_ejercicio_completo(self, grupo: str, nombre: str) -> str:
        db_grupo = EJERCICIOS_DATABASE.get(grupo, {})
        for tipo in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
            for ej in db_grupo.get(tipo, []):
                if extraer_nombre_ejercicio(ej).lower() == nombre.lower():
                    return tipo
        return 'aislamiento'

    def _precargar_historial_ejercicios(self):
        """Carga el historial de ejercicios del cliente con una única consulta DB."""
        try:
            from entrenos.models import EjercicioRealizado
            self._historial_ejercicios_raw = list(
                EjercicioRealizado.objects.filter(
                    entreno__cliente_id=self.perfil.id
                ).order_by('-entreno__fecha', '-id').values(
                    'nombre_ejercicio', 'peso_kg', 'rpe', 'repeticiones', 'entreno__fecha'
                )
            )
        except Exception as e:
            logger.warning("Error precargando historial de ejercicios: %s", e)
            self._historial_ejercicios_raw = []

    def _obtener_historial_ejercicio(self, nombre_ejercicio: str) -> dict:
        """
        Devuelve el peso y RPE de la última sesión del ejercicio.
        Usa la caché en memoria si está disponible (cargada por _precargar_historial_ejercicios).
        """
        resultado = {'peso_real': None, 'rpe_real': None, 'reps_real': None, 'peso_real_bruto': None}
        try:
            nombre_lower = nombre_ejercicio.lower()

            if hasattr(self, '_historial_ejercicios_raw'):
                matches = [
                    e for e in self._historial_ejercicios_raw
                    if nombre_lower in (e['nombre_ejercicio'] or '').lower()
                ]
                if not matches:
                    return resultado

                ref = matches[0]
                if ref['peso_kg']:
                    resultado['peso_real'] = float(ref['peso_kg'])
                    # Snapshot sin suavizar: la última sesión real aislada, antes
                    # de que el ancla de abajo pueda sustituir 'peso_real' por un
                    # promedio ponderado de hasta 3 sesiones. Sirve como techo de
                    # seguridad en descarga (ver resolver_peso_objetivo).
                    resultado['peso_real_bruto'] = resultado['peso_real']
                if ref['rpe'] is not None:
                    resultado['rpe_real'] = float(ref['rpe'])
                if ref.get('repeticiones') is not None:
                    resultado['reps_real'] = int(ref['repeticiones'])

                # Sin reps no se puede determinar bucket → fallback a cruda
                if ref.get('repeticiones') is None:
                    return resultado

                bucket_ref = _bucket_desde_reps(int(ref['repeticiones']))
                sesiones = [
                    {
                        'peso': float(m['peso_kg']),
                        'reps': int(m['repeticiones']),
                        'rpe': float(m['rpe']),
                        'fecha': m['entreno__fecha'],
                    }
                    for m in matches
                    if (
                        m.get('repeticiones') is not None
                        and m['peso_kg']
                        and m['rpe'] is not None
                        and _bucket_desde_reps(int(m['repeticiones'])) == bucket_ref
                    )
                ]

                if not sesiones:
                    # Referencia sin datos completos y sin otras sesiones compatibles
                    return resultado

                ancla = resolver_ancla_historica(sesiones)
                if ancla:
                    resultado['peso_real'] = ancla['peso']
                    resultado['reps_real'] = ancla['reps']
                    resultado['rpe_real'] = ancla['rpe']
                return resultado

            # Fallback: consultas individuales si la precarga no se ejecutó
            from entrenos.models import EjercicioRealizado, SerieRealizada
            ej = EjercicioRealizado.objects.filter(
                nombre_ejercicio__icontains=nombre_lower,
                entreno__cliente_id=self.perfil.id
            ).order_by('-entreno__fecha', '-id').first()

            if ej and ej.peso_kg:
                resultado['peso_real'] = float(ej.peso_kg)
                resultado['peso_real_bruto'] = resultado['peso_real']
            if ej and ej.repeticiones is not None:
                resultado['reps_real'] = int(ej.repeticiones)

            if ej:
                series = SerieRealizada.objects.filter(
                    entreno=ej.entreno,
                    ejercicio__nombre__icontains=nombre_lower,
                    rpe_real__isnull=False
                )
                rpes = [float(s.rpe_real) for s in series if s.rpe_real is not None]
                if rpes:
                    resultado['rpe_real'] = sum(rpes) / len(rpes)
                elif ej.rpe is not None:
                    resultado['rpe_real'] = float(ej.rpe)
        except Exception as e:
            logger.warning("Error al obtener historial del ejercicio '%s': %s", nombre_ejercicio, e)
        return resultado

    def _obtener_rpe_real_anterior(self, nombre_ejercicio: str) -> Optional[float]:
        return self._obtener_historial_ejercicio(nombre_ejercicio)['rpe_real']

    def _construir_motivo_peso(self, motivo_tipo: str, nombre_ejercicio: str) -> str:
        """Construye el texto explicativo del peso recomendado."""
        textos = {
            'sube': f'Sube por: últimas sesiones completadas con margen.',
            'mantiene': f'Carga mantenida: el plan prioriza margen esta semana.',
            'frenado': f'Progresión frenada: hay una señal de carga o margen bajo.',
            'sin_datos': f'Sin historial: el plan calibra desde capacidad actual.',
            'recalculado_fase': 'Recalculado: el rango de hoy cambia de fase — se recalibra desde tu capacidad estimada.',
            'recalculado_descarga': 'Descarga: peso reducido a propósito para esta fase de recuperación activa.',
            'carga_por_tipo': 'Carga según el tipo de ejercicio: se mide en tiempo, distancia o repeticiones.',
        }
        return textos.get(motivo_tipo, 'Peso determinado por el plan.')

    def _calcular_descanso_pormenorizado(self, nombre: str, rpe: int, tipo: str, reps=None) -> float:
        return get_descanso_sugerido(tipo_ejercicio=tipo, rpe_objetivo=rpe, nombre=nombre, reps=reps)['minutos']
