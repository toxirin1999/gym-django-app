# planificador_helms/ejercicios/selector.py
"""
Lógica para la selección inteligente de ejercicios.
Integra seguridad biológica vía BioContextProvider.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from ..database.ejercicios import EJERCICIOS_DATABASE
from ..config import UNIVERSAL_SAFE_EXERCISE_NAMES
from ..utils.helpers import normalizar_nombre, extraer_nombre_ejercicio, pick_rotado, ejercicio_a_dict, es_ejercicio_seguro
from .patrones import PatronManager

logger = logging.getLogger(__name__)


def _ejercicio_es_seguro(ej: Any, restricted_tags: Set[str]) -> bool:
    """Wrapper local para mantener compatibilidad."""
    return es_ejercicio_seguro(ej, restricted_tags)


def _filtrar_pool_seguro(pool: List[Any], restricted_tags: Set[str]) -> List[Any]:
    """Filtra un pool de ejercicios eliminando los que tengan tags prohibidos."""
    if not restricted_tags:
        return pool
    return [ej for ej in pool if _ejercicio_es_seguro(ej, restricted_tags)]


def _pivotar_a_universal_safe(restricted_tags: Set[str], original_group: str) -> Optional[Dict[str, Any]]:
    """Busca un comodín seguro en otros grupos musculares."""
    universal_safe_pool = []
    for g_name, g_tipos in EJERCICIOS_DATABASE.items():
        if g_name == original_group: continue
        for cat in ['compuesto_principal', 'compuesto_secundario', 'aislamiento']:
            for ej in g_tipos.get(cat, []):
                if isinstance(ej, dict) and ej.get('universal_safe', False):
                    tags_ej = set(ej.get('risk_tags', []))
                    if not tags_ej.intersection(restricted_tags):
                        universal_safe_pool.append(ej)
                        
    if universal_safe_pool:
        import random
        core_safes = [e for e in universal_safe_pool if normalizar_nombre(extraer_nombre_ejercicio(e)) in UNIVERSAL_SAFE_EXERCISE_NAMES]
        otros_safes = [e for e in universal_safe_pool if e not in core_safes]
        
        if core_safes:
            return random.choice(core_safes)
        elif otros_safes:
            return random.choice(otros_safes)
        else:
            return random.choice(universal_safe_pool)
    return None


class SelectorEjercicios:
    """Clase encargada de seleccionar ejercicios óptimos para un bloque de entrenamiento."""

    @staticmethod
    def obtener_reglas_por_fase(fase: str) -> Dict[str, Any]:
        """Define reglas de selección según la fase."""
        fase = fase.lower()
        if "hipertrofia" in fase:
            return {
                "evitar_contiene": ["peso muerto"],
                "permitir_variantes": ["rumano"],
                "max_ej_por_grupo": 2
            }
        if "fuerza" in fase:
            return {
                "evitar_contiene": [],
                "permitir_variantes": [],
                "max_ej_por_grupo": 2
            }
        if "potencia" in fase:
            return {
                "evitar_contiene": ["peso muerto"],
                "permitir_variantes": ["sumo"],
                "max_ej_por_grupo": 1
            }
        if "descarga" in fase:
            return {
                "evitar_contiene": ["peso muerto", "sentadilla", "press banca"],
                "permitir_variantes": [],
                "max_ej_por_grupo": 1
            }
        return {
            "evitar_contiene": [],
            "permitir_variantes": [],
            "max_ej_por_grupo": 2
        }

    @classmethod
    def seleccionar_ejercicios_para_bloque(
        cls,
        numero_bloque: int,
        fase: str,
        evitados: Set[str] = None,
        cliente=None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Selecciona los ejercicios para cada grupo muscular en un bloque dado,
        aplicando criterios de estabilidad según la fase y filtros de
        seguridad biológica vía BioContextProvider.

        Args:
            numero_bloque: índice del bloque (1-based)
            fase: fase de periodización ('hipertrofia', 'fuerza', etc.)
            evitados: set de nombres de ejercicios a evitar
            cliente: instancia de Cliente (opcional). Si se pasa, se
                     consultan restricciones de lesión en tiempo real.
        """
        evitados = evitados or set()
        reglas = cls.obtener_reglas_por_fase(fase)
        ejercicios_seleccionados = {}
        es_hipertrofia = "hipertrofia" in fase.lower()

        # ── Seguridad biológica: obtener tags prohibidos ───────
        restricted_tags: Set[str] = set()
        if cliente is not None:
            try:
                from core.bio_context import BioContextProvider
                bio = BioContextProvider.get_current_restrictions(cliente)
                restricted_tags = bio.get('tags', set())
                if restricted_tags:
                    logger.info(
                        "BioContext: %d tags restringidos activos → %s",
                        len(restricted_tags), restricted_tags,
                    )
            except Exception as e:
                logger.warning("BioContext no disponible: %s", e)

        def ponderar_estabilidad(ej: Any) -> int:
            """Otorga más peso a ejercicios estables en fase de hipertrofia."""
            if not isinstance(ej, dict): return 0
            est = ej.get('estabilidad', 'media')
            if es_hipertrofia:
                mapping = {'alta': 10, 'media': 5, 'baja': 0}
                return mapping.get(est, 5)
            return 0

        for grupo, tipos in EJERCICIOS_DATABASE.items():
            pool_principal = list(tipos.get('compuesto_principal', []))
            pool_secundario = list(tipos.get('compuesto_secundario', []))
            pool_aislamiento = list(tipos.get('aislamiento', []))

            # Pre-filtrar pools por seguridad biológica
            pool_principal_safe = _filtrar_pool_seguro(pool_principal, restricted_tags)
            pool_secundario_safe = _filtrar_pool_seguro(pool_secundario, restricted_tags)
            pool_aislamiento_safe = _filtrar_pool_seguro(pool_aislamiento, restricted_tags)

            # Ordenar por estabilidad si es hipertrofia para que pick_rotado tenga mejores opciones al inicio
            if es_hipertrofia:
                pool_principal_safe = sorted(pool_principal_safe, key=ponderar_estabilidad, reverse=True)
                pool_secundario_safe = sorted(pool_secundario_safe, key=ponderar_estabilidad, reverse=True)
                pool_aislamiento_safe = sorted(pool_aislamiento_safe, key=ponderar_estabilidad, reverse=True)

            seleccion_grupo = []
            
            # Lógica especial para Espalda (Horizontal + Vertical)
            if grupo == "espalda":
                kw_vertical = ["dominad", "jalón", "jalon"]
                kw_horizontal = ["remo", "polea baja", "gironda", "pendlay", "mancuerna"]

                pool_full = pool_principal_safe + pool_secundario_safe + pool_aislamiento_safe
                verticales = [e for e in pool_full if any(k in extraer_nombre_ejercicio(e).lower() for k in kw_vertical)]
                horizontales = [e for e in pool_full if any(k in extraer_nombre_ejercicio(e).lower() for k in kw_horizontal)]

                ej1 = pick_rotado(verticales, numero_bloque - 1) or pick_rotado(pool_full, numero_bloque - 1)
                if ej1:
                    seleccion_grupo.append(ej1)
                    # Forzar el opuesto
                    ej2 = None
                    nombre_ej1 = extraer_nombre_ejercicio(ej1).lower()
                    if any(k in nombre_ej1 for k in kw_vertical):
                        ej2 = pick_rotado(horizontales, numero_bloque - 1)
                    else:
                        ej2 = pick_rotado(verticales, numero_bloque - 1)
                    
                    if ej2 and extraer_nombre_ejercicio(ej2).lower() != nombre_ej1:
                        seleccion_grupo.append(ej2)
            else:
                # Otros grupos: 1 principal + (secundario o aislamiento)
                ej1 = pick_rotado(pool_principal_safe, numero_bloque - 1)

                # ── Sustitución bio-segura: si el principal fue bloqueado,
                #    buscar obligatoriamente en secundario/aislamiento ────
                blocked_principal = None
                if not ej1 and pool_principal and restricted_tags:
                    # Guardar el nombre del principal bloqueado para transparencia
                    blocked_principal = pool_principal[0] if pool_principal else None
                    blocked_name = extraer_nombre_ejercicio(blocked_principal) if blocked_principal else '?'
                    # Identificar qué tags causaron el bloqueo
                    blocked_ex_tags = set(blocked_principal.get('risk_tags', [])) if isinstance(blocked_principal, dict) else set()
                    matching_tags = list(blocked_ex_tags.intersection(restricted_tags))

                    logger.info(
                        "BioContext: principal '%s' bloqueado en '%s' por tags %s, buscando sustituto",
                        blocked_name, grupo, matching_tags,
                    )
                    # Intentar secundario primero
                    ej1 = pick_rotado(pool_secundario_safe, numero_bloque - 1)
                    if not ej1:
                        ej1 = pick_rotado(pool_aislamiento_safe, numero_bloque - 1)

                    # ── Anotar metadata de sustitución en el ejercicio sustituto ──
                    if ej1 and isinstance(ej1, dict):
                        # Obtener fase de la lesión si está disponible
                        injury_fase = ''
                        injury_zona = ''
                        if cliente is not None:
                            try:
                                from core.bio_context import BioContextProvider
                                bio_data = BioContextProvider.get_current_restrictions(cliente)
                                if bio_data.get('injuries'):
                                    injury_fase = bio_data['injuries'][0].get('fase', '')
                                    injury_zona = bio_data['injuries'][0].get('zona', '')
                            except Exception:
                                pass
                        ej1['was_bio_substituted'] = True
                        ej1['metadata_adaptacion'] = {
                            'ejercicio_original': blocked_name,
                            'risk_tags': matching_tags,
                            'injury_phase': injury_fase,
                            'injury_zone': injury_zona,
                        }

                # ── PROTOCOLO DE PIVOTAJE (Hot-Pivot Engine) ──
                # Si no hay NADA seguro en ninguna categoría de este grupo muscular (bloqueo total)
                if not ej1 and not pool_principal_safe and not pool_secundario_safe and not pool_aislamiento_safe and pool_principal:
                    logger.warning("BioContext: Bloqueo TOTAL en grupo '%s'. Iniciando Pivotaje Sistémico.", grupo)
                    
                    pivot_ej = _pivotar_a_universal_safe(restricted_tags, grupo)
                    if pivot_ej:
                        ej1 = dict(pivot_ej)
                        # Obtener metadata de la restricción del principal bloqueado
                        blocked_principal = pool_principal[0] if pool_principal else None
                        blocked_name = extraer_nombre_ejercicio(blocked_principal) if blocked_principal else '?'
                        blocked_ex_tags = set(blocked_principal.get('risk_tags', [])) if isinstance(blocked_principal, dict) else set()
                        matching_tags = list(blocked_ex_tags.intersection(restricted_tags))

                        injury_fase = ''
                        injury_zona = ''
                        if cliente is not None:
                            try:
                                from core.bio_context import BioContextProvider
                                bio_data = BioContextProvider.get_current_restrictions(cliente)
                                if bio_data.get('injuries'):
                                    injury_fase = bio_data['injuries'][0].get('fase', '')
                                    injury_zona = bio_data['injuries'][0].get('zona', '')
                            except Exception:
                                pass

                        ej1['is_pivot_substituted'] = True
                        ej1['was_bio_substituted'] = True
                        ej1['metadata_adaptacion'] = {
                            'ejercicio_original': f"Bloque Integro de {grupo.capitalize()}",
                            'risk_tags': matching_tags,
                            'injury_phase': injury_fase,
                            'injury_zone': injury_zona,
                            'pivot_group': grupo
                        }
                        logger.info("BioContext: Pivotaje exitoso a '%s' (universal_safe)", extraer_nombre_ejercicio(ej1))

                if ej1:
                    seleccion_grupo.append(ej1)
                
                ej2 = None
                calf_injured = restricted_tags and ('estabilidad_gemelo' in restricted_tags or 'flexion_plantar' in restricted_tags)
                is_lower_body = grupo in ['cuadriceps', 'isquios', 'gluteos', 'gemelos']

                # Pivotaje Real a Tren Superior: Si el primer ejercicio fue de pierna y hay lesión
                # de gemelo, pivotar obligatoriamente el segundo bloque a un comodín seguro.
                if ej1 and is_lower_body and calf_injured and not ej1.get('is_pivot_substituted'):
                    logger.warning("BioContext: Forzando Pivotaje para 2º bloque de %s por lesión de gemelo.", grupo)
                    pivot_ej2 = _pivotar_a_universal_safe(restricted_tags, grupo)
                    if pivot_ej2:
                        ej2 = dict(pivot_ej2)
                        
                        injury_fase = ''
                        injury_zona = ''
                        if cliente is not None:
                            try:
                                from core.bio_context import BioContextProvider
                                bio_data = BioContextProvider.get_current_restrictions(cliente)
                                if bio_data.get('injuries'):
                                    injury_fase = bio_data['injuries'][0].get('fase', '')
                                    injury_zona = bio_data['injuries'][0].get('zona', '')
                            except Exception:
                                pass
                                
                        ej2['is_pivot_substituted'] = True
                        ej2['was_bio_substituted'] = True
                        ej2['metadata_adaptacion'] = {
                            'ejercicio_original': f"Segundo Ejercicio de {grupo.capitalize()}",
                            'risk_tags': ['estabilidad_gemelo', 'flexion_plantar'],
                            'injury_phase': injury_fase,
                            'injury_zone': injury_zona,
                            'pivot_group': grupo
                        }
                else:
                    opciones2 = pool_secundario_safe + pool_aislamiento_safe
                    ej2 = pick_rotado(opciones2, numero_bloque - 1)
                    
                if ej2 and (not ej1 or extraer_nombre_ejercicio(ej2) != extraer_nombre_ejercicio(ej1)):
                    seleccion_grupo.append(ej2)

            # Filtrar por evitados y reglas de fase
            filtrados = []
            for ej in seleccion_grupo:
                nombre = extraer_nombre_ejercicio(ej).lower()
                if nombre in evitados:
                    continue
                
                # Reglas de "contiene"
                if any(bad in nombre for bad in reglas["evitar_contiene"]):
                    if any(ok in nombre for ok in reglas["permitir_variantes"]):
                        filtrados.append(ej)
                else:
                    filtrados.append(ej)
            
            # Limitar por fase y convertir a dict
            max_ej = reglas["max_ej_por_grupo"]
            ejercicios_seleccionados[grupo] = [ejercicio_a_dict(e) for e in filtrados[:max_ej]]

        return ejercicios_seleccionados

