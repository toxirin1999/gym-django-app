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
from .calculo.compatibilidad_fase import resolver_peso_objetivo
from .calculo.fatiga import GestorFatiga
from .ejercicios.selector import SelectorEjercicios
from .ejercicios.patrones import PatronManager
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

    def generar_entrenamiento_para_fecha(self, fecha_objetivo: date) -> Optional[Dict[str, Any]]:
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
        numero_bloque = periodizacion.index(bloque_actual) + 1
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

    def _generar_semana_especifica(self, bloque: Dict[str, Any], numero_bloque: int) -> Dict[str, List[Dict[str, Any]]]:
        _cache_key = (numero_bloque, bloque.get('fase', ''), bloque.get('volumen_multiplicador', 1.0))
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
            vol_efectivo = int(min(vol_base_grupo * vol_mult, mrv_g))
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
        except AsignacionImposibleError as exc:
            logger.warning(
                "Motor de asignación falló (perfil id=%s, dias=%d): %s — "
                "usando DISTRIBUCION_DIAS como fallback.",
                self.perfil.id, self.dias_disponibles, exc,
            )
            distribucion_volumen = DISTRIBUCION_DIAS.get(self.dias_disponibles, DISTRIBUCION_DIAS[4])
            frecuencia_map = None

        orden_dias = sorted(distribucion_volumen.keys())
        for idx_dia, dia_key in enumerate(orden_dias):
            gestor_fatiga = GestorFatiga(fase)
            ejercicios_dia = []

            grupos_del_dia = distribucion_volumen[dia_key]
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
                vol_dia = math.ceil(min(vol_ajustado_bloque, mrv_grupo) / frecuencia) if frecuencia > 0 else 0
                if vol_dia <= 0: continue

                candidatos = ejercicios_bloque.get(grupo, [])
                if not candidatos: continue

                for ej in candidatos[:n_ejercicios_grupo]:
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

                    es_pesado = (int((rep_range_ej or '8-12').split('-')[0]) <= 6 or rpe_objetivo >= 9)
                    series_objetivo = max(2, min(tope_por_ejercicio, math.ceil(vol_dia / len(candidatos[:n_ejercicios_grupo]))))
                    series_ajustadas = gestor_fatiga.ajustar_series_por_limite(
                        nombre, patron, tipo_ej, series_objetivo, es_pesado, grupo=grupo
                    )
                    if series_ajustadas <= 0: continue

                    # Obtener historial real del ejercicio
                    historial = self._obtener_historial_ejercicio(nombre)
                    rpe_real_anterior = historial['rpe_real']
                    peso_real_anterior = historial['peso_real']
                    reps_real_anterior = historial['reps_real']

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
                        rpe_objetivo_hoy=rpe_objetivo,
                        es_descarga_hoy=es_descarga_hoy,
                        redondear_fn=lambda p: CalculadorPeso.redondear_peso(p, nombre),
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

                    tempo = TEMPOS.get(fase, TEMPOS['hipertrofia'])
                    descanso = self._calcular_descanso_pormenorizado(nombre, rpe_objetivo, tipo_ej)

                    motivo_peso_texto = self._construir_motivo_peso(motivo_peso_tipo, nombre)

                    ejercicios_dia.append({
                        'nombre': nombre,
                        'grupo_muscular': grupo,
                        'series': series_ajustadas,
                        'repeticiones': rep_range_ej,
                        'peso_kg': peso,
                        'rpe_objetivo': rpe_objetivo,
                        'tempo': tempo,
                        'descanso_minutos': descanso,
                        'patron': patron,
                        'tipo_progresion': ej.get('tipo_progresion', 'peso_reps'),
                        'tipo_ejercicio': tipo_ej,
                        'motivo_peso': {
                            'tipo': motivo_peso_tipo,
                            'texto': motivo_peso_texto,
                        },
                    })

                    patron_manager.registrar_uso_patron(patron, idx_dia, grupo, nombre)
                    gestor_fatiga.registrar_fatiga(patron, series_ajustadas, es_pesado)

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
                    'nombre_ejercicio', 'peso_kg', 'rpe', 'repeticiones'
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
        resultado = {'peso_real': None, 'rpe_real': None, 'reps_real': None}
        try:
            nombre_lower = nombre_ejercicio.lower()

            if hasattr(self, '_historial_ejercicios_raw'):
                match = next(
                    (e for e in self._historial_ejercicios_raw
                     if nombre_lower in (e['nombre_ejercicio'] or '').lower()),
                    None
                )
                if match:
                    if match['peso_kg']:
                        resultado['peso_real'] = float(match['peso_kg'])
                    if match['rpe'] is not None:
                        resultado['rpe_real'] = float(match['rpe'])
                    if match.get('repeticiones') is not None:
                        resultado['reps_real'] = int(match['repeticiones'])
                return resultado

            # Fallback: consultas individuales si la precarga no se ejecutó
            from entrenos.models import EjercicioRealizado, SerieRealizada
            ej = EjercicioRealizado.objects.filter(
                nombre_ejercicio__icontains=nombre_lower,
                entreno__cliente_id=self.perfil.id
            ).order_by('-entreno__fecha', '-id').first()

            if ej and ej.peso_kg:
                resultado['peso_real'] = float(ej.peso_kg)
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
        }
        return textos.get(motivo_tipo, 'Peso determinado por el plan.')

    def _calcular_descanso_pormenorizado(self, nombre: str, rpe: int, tipo: str) -> int:
        return get_descanso_sugerido(tipo_ejercicio=tipo, rpe_objetivo=rpe)['minutos']
