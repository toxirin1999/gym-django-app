# planificador_helms/utils/helpers.py
"""
Funciones auxiliares reutilizables del sistema Helms.

CAMBIOS v2:
- [BUG FIX] buscar_ejercicio_por_nombre y obtener_sustituto_en_caliente usaban
  imports absolutos hardcodeados ('from analytics.planificador_helms...') que
  rompen si el paquete se mueve o renombra. Convertidos a imports relativos
  dentro del paquete, consistentes con el resto de módulos.
- [BUG FIX] obtener_sustituto_en_caliente duplicaba la lógica del Hot-Pivot
  Engine de selector.py (_pivotar_a_universal_safe). Refactorizado para
  delegar en _pivotar_a_universal_safe cuando es necesario, eliminando la
  duplicación. La lógica de búsqueda en mismo grupo se mantiene aquí porque
  tiene contexto (nombre_original) que selector.py no tiene en ese punto.
- [MEJORA] pick_rotado: añadida validación de tipo para evitar TypeError
  si se pasa un objeto no indexable.
- [LIMPIEZA] import random movido al nivel de módulo en las funciones que
  lo necesitan, eliminando imports dentro de funciones.
"""

import random
from typing import Any, Dict, List, Optional


def normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre de ejercicio para comparaciones (lowercase, sin espacios extra)."""
    if not nombre:
        return ''
    return str(nombre).strip().lower()


def extraer_nombre_ejercicio(ejercicio: Any) -> str:
    """Extrae el nombre de un ejercicio (compatible con dict o string)."""
    if isinstance(ejercicio, dict):
        return ejercicio.get('nombre', '').strip()
    return str(ejercicio).strip()


def extraer_patron_ejercicio(ejercicio: Any) -> str:
    """Extrae el patrón de un ejercicio (compatible con dict o string)."""
    if isinstance(ejercicio, dict):
        return ejercicio.get('patron', '').strip()
    return ''


def ejercicio_a_dict(ejercicio: Any) -> Dict[str, Any]:
    """
    Convierte un ejercicio a formato dict estándar, preservando
    metadatos de seguridad biológica para la capa de transparencia.
    """
    result: Dict[str, Any] = {
        'nombre': extraer_nombre_ejercicio(ejercicio),
        'patron': '',
    }
    if isinstance(ejercicio, dict):
        result['patron'] = extraer_patron_ejercicio(ejercicio)
        if ejercicio.get('risk_tags'):
            result['risk_tags'] = ejercicio['risk_tags']
        if ejercicio.get('was_bio_substituted'):
            result['was_bio_substituted'] = True
            result['bio_substitution_reason'] = ejercicio.get('bio_substitution_reason', {})
        if ejercicio.get('estabilidad'):
            result['estabilidad'] = ejercicio['estabilidad']
        if ejercicio.get('perfil'):
            result['perfil'] = ejercicio['perfil']
    return result


def es_ejercicio_seguro(ej: Any, restricted_tags: set) -> bool:
    """
    Comprueba si un ejercicio es compatible con las restricciones activas,
    incluyendo filtros estrictos de postura para lesiones de tren inferior.
    """
    if not restricted_tags:
        return True
    if not isinstance(ej, dict):
        return True

    tags_del_ejercicio = set(ej.get('risk_tags', []))
    if tags_del_ejercicio.intersection(restricted_tags):
        return False

    # Filtro estricto de postura para lesiones de gemelo/tobillo o agudas de tren inferior
    calf_injured = (
            'estabilidad_gemelo' in restricted_tags
            or 'flexion_plantar' in restricted_tags
    )
    tren_inferior_aguda = '__aguda_tren_inferior' in restricted_tags

    if calf_injured or tren_inferior_aguda:
        posicion = ej.get('posicion')
        cadena = ej.get('cadena')

        if posicion == 'pie' or cadena == 'cerrada':
            return False

        nombre = ej.get('nombre', '').lower()
        unsafe_keywords = [
            'de pie', 'sentadilla', 'sissy', 'zancada', 'peso muerto',
            'buenos días', 'push press', 'paseo del granjero', 'multipower',
            'militar con barra',
        ]
        if any(bad in nombre for bad in unsafe_keywords):
            return False

    return True


def buscar_ejercicio_por_nombre(nombre: str) -> Optional[Dict[str, Any]]:
    """
    Busca un ejercicio por su nombre en la base de datos de Helms.

    CORRECCIÓN: Import absoluto hardcodeado reemplazado por import relativo.
    """
    from ..database.ejercicios import EJERCICIOS_DATABASE  # import relativo

    nombre_norm = normalizar_nombre(nombre)
    if not nombre_norm:
        return None

    for grupo, categorias in EJERCICIOS_DATABASE.items():
        for cat, ejs in categorias.items():
            for ej in ejs:
                if normalizar_nombre(extraer_nombre_ejercicio(ej)) == nombre_norm:
                    return ej if isinstance(ej, dict) else {'nombre': str(ej)}
    return None


def obtener_sustituto_en_caliente(
        nombre_original: str,
        tags_bloqueados: set,
) -> Optional[Dict[str, Any]]:
    """
    Busca un sustituto seguro para un ejercicio bloqueado por la capa biológica.

    Estrategia:
      1. Localiza el grupo muscular del ejercicio original.
      2. Busca en aislamiento/compuesto_secundario del mismo grupo.
      3. Si no hay, delega al Hot-Pivot Engine de selector.py (universal_safe).
      4. Devuelve None si no encuentra nada seguro.

    CORRECCIÓN: Import absoluto reemplazado por import relativo.
    CORRECCIÓN: La lógica de búsqueda global (pasos 3 y 4) estaba duplicada
    con _pivotar_a_universal_safe en selector.py. Ahora delega en ella.
    """
    from ..database.ejercicios import EJERCICIOS_DATABASE  # import relativo
    from ..ejercicios.selector import _pivotar_a_universal_safe  # reusar lógica existente

    nombre_norm = normalizar_nombre(nombre_original)
    if not nombre_norm or not tags_bloqueados:
        return None

    # 1. Encontrar el grupo muscular del ejercicio original
    grupo_muscular = None
    for grupo, categorias in EJERCICIOS_DATABASE.items():
        for _, ejs in categorias.items():
            for ej in ejs:
                if normalizar_nombre(extraer_nombre_ejercicio(ej)) == nombre_norm:
                    grupo_muscular = grupo
                    break
            if grupo_muscular:
                break
        if grupo_muscular:
            break

    if not grupo_muscular:
        return None

    # 2. Buscar sustituto en el mismo grupo (aislamiento primero, luego secundario)
    pool_seguro = []
    for cat in ('aislamiento', 'compuesto_secundario'):
        for ej in EJERCICIOS_DATABASE[grupo_muscular].get(cat, []):
            if es_ejercicio_seguro(ej, tags_bloqueados):
                pool_seguro.append(ej if isinstance(ej, dict) else {'nombre': str(ej)})

    if pool_seguro:
        return random.choice(pool_seguro)

    # 3. Nada en el grupo → delegar al Hot-Pivot Engine (universal_safe)
    pivot = _pivotar_a_universal_safe(tags_bloqueados, grupo_muscular)
    if pivot:
        pivot = dict(pivot)
        pivot['is_hot_substituted'] = True
    return pivot


def pick_rotado(lista: List[Any], indice_rotacion: int) -> Any:
    """
    Selecciona un elemento de una lista con rotación circular.

    MEJORA: Añadida validación de tipo para evitar TypeError si se pasa
    un objeto no indexable.
    """
    if not lista or not hasattr(lista, '__len__'):
        return None
    idx = indice_rotacion % len(lista)
    return lista[idx]


def es_mancuerna(nombre_ejercicio: str) -> bool:
    """Detecta si un ejercicio usa mancuernas."""
    keywords = ['mancuerna', 'mancuernas', 'db ', 'dumbbell']
    return any(kw in nombre_ejercicio.lower() for kw in keywords)


def es_ejercicio_principal(nombre_ejercicio: str) -> bool:
    """Detecta si un ejercicio es un movimiento principal."""
    principales = [
        'sentadilla', 'peso muerto', 'press banca',
        'press militar', 'hip thrust', 'dominadas',
    ]
    return any(p in nombre_ejercicio.lower() for p in principales)


def eliminar_duplicados_ejercicios(ejercicios: List[Any]) -> List[Any]:
    """Elimina ejercicios duplicados manteniendo el orden."""
    vistos: set = set()
    resultado = []
    for ej in ejercicios:
        nombre = normalizar_nombre(extraer_nombre_ejercicio(ej))
        if nombre and nombre not in vistos:
            vistos.add(nombre)
            resultado.append(ej)
    return resultado


def calcular_progreso_lineal(
        inicio: float,
        fin: float,
        paso_actual: int,
        pasos_totales: int,
) -> float:
    """Calcula un valor en progresión lineal entre inicio y fin."""
    if pasos_totales <= 1:
        return fin
    progreso = paso_actual / max(pasos_totales - 1, 1)
    return inicio + (fin - inicio) * progreso


def agrupar_por_clave(items: List[Dict], clave: str) -> Dict[Any, List[Dict]]:
    """Agrupa una lista de diccionarios por una clave."""
    resultado: Dict[Any, List[Dict]] = {}
    for item in items:
        valor = item.get(clave)
        resultado.setdefault(valor, []).append(item)
    return resultado
