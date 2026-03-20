# planificador_helms/core.py
"""
Planificador principal basado en la metodología de Eric Helms.
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set
import math

from .config import DISTRIBUCION_DIAS, VOLUMENES_BASE, TEMPOS
from .models.perfil_cliente import PerfilCliente
from .database.ejercicios import EJERCICIOS_DATABASE
from .periodizacion.generador import GeneradorPeriodizacion
from .calculo.peso import CalculadorPeso
from .calculo.fatiga import GestorFatiga
from .ejercicios.selector import SelectorEjercicios
from .ejercicios.patrones import PatronManager
from .utils.helpers import normalizar_nombre, extraer_nombre_ejercicio, extraer_patron_ejercicio


class PlanificadorHelms:
    def __init__(self, perfil_cliente: PerfilCliente):
        self.perfil = perfil_cliente
        self.dias_disponibles = self.perfil.dias_disponibles if self.perfil.dias_disponibles in [3, 4, 5] else 4
        self.experiencia_años = perfil_cliente.experiencia_años
        self.objetivo_principal = perfil_cliente.objetivo_principal
        self.maximos_actuales = getattr(perfil_cliente, 'maximos_actuales', {})
        self.ejercicios_evitar = set(normalizar_nombre(e) for e in (perfil_cliente.ejercicios_evitar or []))

    def generar_entrenamiento_para_fecha(self, fecha_objetivo: date) -> Optional[Dict[str, Any]]:
        try:
            semana_num_total = fecha_objetivo.isocalendar()[1]
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

        return {
            "rutina_nombre": f"{clave_dia.replace('_', ' ').title()} - {bloque_actual['nombre']}",
            "ejercicios": ejercicios_del_dia,
            "objetivo": bloque_actual['fase'].replace('_', ' ').title(),
            "bloque": bloque_actual['nombre'],
        }

    def generar_plan_anual(self) -> Dict[str, Any]:
        periodizacion = GeneradorPeriodizacion.generar_periodizacion_anual()
        entrenos_por_fecha = {}
        plan_por_bloques = []

        if self.dias_disponibles == 3:
            dias_offsets = [0, 2, 4]
        elif self.dias_disponibles == 5:
            dias_offsets = [0, 1, 2, 3, 4]
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

        return {
            "cliente_id": self.perfil.id,
            "plan_por_bloques": plan_por_bloques,
            "entrenos_por_fecha": entrenos_por_fecha,
            "metadata": {
                "generado_por": "helms_refactored",
                "periodizacion_completa": periodizacion,
                "año_planificacion": año_planificacion,
            },
        }

    def _generar_semana_especifica(self, bloque: Dict[str, Any], numero_bloque: int) -> Dict[str, List[Dict[str, Any]]]:
        fase = bloque.get('fase', 'hipertrofia')
        vol_mult = bloque.get('volumen_multiplicador', 1.0)
        rpe_objetivo = (bloque.get('intensidad_rpe') or (7,))[0]
        rep_range = bloque.get('rep_range', '8-12')

        nivel = self.perfil.calcular_nivel_experiencia()
        volumen_semanal_base = VOLUMENES_BASE.get(nivel, VOLUMENES_BASE['principiante'])
        distribucion_volumen = DISTRIBUCION_DIAS.get(self.dias_disponibles, DISTRIBUCION_DIAS[4])
        ejercicios_bloque = SelectorEjercicios.seleccionar_ejercicios_para_bloque(numero_bloque, fase,
                                                                                  self.ejercicios_evitar)
        patron_manager = PatronManager(fase)
        semana_planificada = {}

        orden_dias = sorted(distribucion_volumen.keys())
        for idx_dia, dia_key in enumerate(orden_dias):
            gestor_fatiga = GestorFatiga(fase)
            ejercicios_dia = []

            grupos_del_dia = distribucion_volumen[dia_key]
            for grupo in grupos_del_dia:
                vol_base_grupo = volumen_semanal_base.get(grupo, 0)
                frecuencia = sum(1 for d in distribucion_volumen.values() if grupo in d)
                vol_dia = math.ceil((vol_base_grupo / frecuencia) * vol_mult) if frecuencia > 0 else 0
                if vol_dia <= 0: continue

                candidatos = ejercicios_bloque.get(grupo, [])
                if not candidatos: continue

                for ej in candidatos[:2]:
                    nombre = ej['nombre']
                    patron = ej['patron'] or patron_manager.obtener_patron_ejercicio(nombre)
                    tipo_ej = self._determinar_tipo_ejercicio_completo(grupo, nombre)

                    if patron == 'bisagra' and not patron_manager.puede_usar_bisagra(idx_dia):
                        continue

                    es_pesado = (int(rep_range.split('-')[0]) <= 6 or rpe_objetivo >= 9)
                    series_objetivo = max(2, min(4, math.ceil(vol_dia / len(candidatos[:2]))))
                    series_ajustadas = gestor_fatiga.ajustar_series_por_limite(nombre, patron, tipo_ej, series_objetivo,
                                                                               es_pesado)
                    if series_ajustadas <= 0: continue

                    # Obtener historial real del ejercicio
                    historial = self._obtener_historial_ejercicio(nombre)
                    rpe_real_anterior = historial['rpe_real']
                    peso_real_anterior = historial['peso_real']

                    if peso_real_anterior and rpe_real_anterior is not None:
                        diferencia_rpe = rpe_real_anterior - rpe_objetivo
                        from analytics.planificador_helms.calculo.peso import PROGRESION, REDONDEO
                        if diferencia_rpe <= -2:
                            incremento = PROGRESION['fijo_grande']
                        elif diferencia_rpe <= 0:
                            incremento = PROGRESION['fijo_pequeno']
                        elif diferencia_rpe <= 2:
                            incremento = 0
                        else:
                            incremento = -PROGRESION['fijo_pequeno']
                        peso_nuevo = peso_real_anterior + incremento
                        tipo = CalculadorPeso.inferir_tipo_carga(nombre)
                        inc = REDONDEO.get(tipo, REDONDEO['general'])
                        peso = math.ceil(peso_nuevo / inc) * inc if inc > 0 else round(peso_nuevo, 1)
                    else:
                        peso = CalculadorPeso.calcular_peso_trabajo(nombre, rep_range, rpe_objetivo,
                                                                    self.maximos_actuales, rpe_real_anterior)

                    tempo = TEMPOS.get(fase, TEMPOS['hipertrofia'])
                    descanso = self._calcular_descanso_pormenorizado(nombre, rpe_objetivo, tipo_ej)

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
                        'tipo_progresion': ej.get('tipo_progresion', 'peso_reps'),
                    })

                    patron_manager.registrar_uso_patron(patron, idx_dia, grupo)
                    gestor_fatiga.registrar_fatiga(patron, series_ajustadas, es_pesado)

            if ejercicios_dia:
                semana_planificada[dia_key] = ejercicios_dia

        return semana_planificada

    def _determinar_tipo_ejercicio_completo(self, grupo: str, nombre: str) -> str:
        db_grupo = EJERCICIOS_DATABASE.get(grupo, {})
        for tipo in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
            for ej in db_grupo.get(tipo, []):
                if extraer_nombre_ejercicio(ej).lower() == nombre.lower():
                    return tipo
        return 'aislamiento'

    def _obtener_historial_ejercicio(self, nombre_ejercicio: str) -> dict:
        """
        Devuelve el peso medio ponderado real (EjercicioRealizado)
        y el RPE medio real (SerieRealizada) de la última sesión del ejercicio.
        Filtra por cliente para evitar mezclar datos entre usuarios.
        """
        resultado = {'peso_real': None, 'rpe_real': None}
        try:
            from entrenos.models import EjercicioRealizado, SerieRealizada
            nombre_lower = nombre_ejercicio.lower()

            # Peso: media ponderada de la última sesión (EjercicioRealizado)
            ej = EjercicioRealizado.objects.filter(
                nombre_ejercicio__icontains=nombre_lower,
                entreno__cliente_id=self.perfil.id
            ).order_by('-entreno__fecha', '-id').first()

            if ej and ej.peso_kg:
                resultado['peso_real'] = float(ej.peso_kg)

            # RPE: media de las series de ese mismo entreno
            if ej:
                series = SerieRealizada.objects.filter(
                    entreno=ej.entreno,
                    ejercicio__nombre__icontains=nombre_lower,
                    rpe_real__isnull=False
                )
                rpes = [float(s.rpe_real) for s in series if s.rpe_real is not None]
                if rpes:
                    resultado['rpe_real'] = sum(rpes) / len(rpes)
        except Exception:
            pass
        return resultado

    def _obtener_rpe_real_anterior(self, nombre_ejercicio: str) -> Optional[float]:
        return self._obtener_historial_ejercicio(nombre_ejercicio)['rpe_real']

    def _calcular_descanso_pormenorizado(self, nombre: str, rpe: int, tipo: str) -> int:
        if tipo == 'compuesto_principal':
            return 4 if rpe >= 8 else 3
        return 2 if rpe >= 8 else 1
