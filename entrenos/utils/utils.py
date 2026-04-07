# Archivo: entrenos/vendor/vendor.py
# VERSIÓN CORREGIDA Y ORGANIZADA

import re


# --- FUNCIONES DE PARSEO Y NORMALIZACIÓN DE EJERCICIOS ---

def normalizar_nombre_ejercicio(nombre):
    """
    Estandariza el nombre de un ejercicio para consistencia en búsqueda y almacenamiento.
    Convierte a una forma canónica para evitar duplicados por mayúsculas, tildes, espacios o puntuación.

    Ej: " PRESS  banca. " -> "press banca"
        "Prèss Báncà"    -> "press banca"
        "Press-Banca"    -> "press banca"
    """
    import unicodedata
    import re

    if not isinstance(nombre, str) or not nombre.strip():
        return nombre

    # 1. Eliminar acentos / diacríticos
    nfkd = unicodedata.normalize('NFKD', nombre)
    sin_acentos = ''.join(c for c in nfkd if not unicodedata.combining(c))

    # 2. Lowercase
    resultado = sin_acentos.lower()

    # 3. Reemplazar separadores no alfanuméricos (guiones, puntos, barras) por espacio
    resultado = re.sub(r'[-_/\\.]', ' ', resultado)

    # 4. Eliminar caracteres no alfanuméricos ni espacios
    resultado = re.sub(r'[^a-z0-9 ]', '', resultado)

    # 5. Colapsar espacios múltiples y strip
    resultado = re.sub(r'\s+', ' ', resultado).strip()

    return resultado


def nombres_ejercicio_equivalentes(a, b):
    """
    Compara dos nombres de ejercicio normalizados de forma tolerante:
    - Ignora diferencias de singular/plural (trailing 's' o 'es')
    - Permite que uno sea prefijo del otro (max 2 chars de diferencia)

    Ej: "face pull" == "face pulls"  → True
        "curl bicep" == "curl biceps" → True
        "press banca" == "press" → False (diferencia > 2)
    """
    na = normalizar_nombre_ejercicio(a)
    nb = normalizar_nombre_ejercicio(b)
    if na == nb:
        return True
    # Normalizar plural: quitar 's' o 'es' final para comparar raíz
    def quitar_plural(s):
        if s.endswith('es') and len(s) > 4:
            return s[:-2]
        if s.endswith('s') and len(s) > 3:
            return s[:-1]
        return s
    if quitar_plural(na) == quitar_plural(nb):
        return True
    # Prefijo: uno contiene al otro con diferencia máxima de 2 caracteres
    if na.startswith(nb) and len(na) - len(nb) <= 2:
        return True
    if nb.startswith(na) and len(nb) - len(na) <= 2:
        return True
    return False


def nombre_ejercicio_display(nombre):
    """
    Versión para mostrar al usuario: Title Case limpio.
    Ej: "press banca" -> "Press Banca"
    """
    if not isinstance(nombre, str):
        return nombre
    return normalizar_nombre_ejercicio(nombre).title()


def parsear_ejercicios_de_notas(notas):
    """
    Parsea un bloque de texto de notas y extrae una lista de diccionarios de ejercicios.
    """
    ejercicios = []
    if not notas:
        return ejercicios

    # Limpieza inicial del texto
    notas_limpias = notas.replace("\\n", "\n")
    if "Ejercicios Detallados:" in notas_limpias:
        notas_limpias = notas_limpias.split("Ejercicios Detallados:")[-1]

    lineas = notas_limpias.strip().splitlines()

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        # Expresión regular para capturar el formato: [✓/✗/N] Nombre: Peso, SeriesxRepeticiones
        match = re.match(r'^[✓✗N]?\s*(.+?):\s*([\d.,PC]+),\s*(\d+x\d+.*)', linea, re.IGNORECASE)
        if match:
            nombre, peso, repeticiones_str = match.groups()
            completado_raw = linea.lstrip()[0] if linea.lstrip()[0] in '✓✗N' else ''

            ejercicios.append({
                'nombre': normalizar_nombre_ejercicio(nombre),
                'peso': peso.strip(),
                'repeticiones': repeticiones_str.strip(),
                'completado': completado_raw == '✓',
            })

    return ejercicios


# Alias para compatibilidad legacy
parsear_ejercicios = parsear_ejercicios_de_notas


def parse_reps_and_series(rep_str):
    """
    ✅ NUEVA FUNCIÓN ROBUSTA
    Parsea un string de repeticiones (ej: "3x10-12" o solo "12") y devuelve
    una tupla (series, repeticiones_promedio).
    Siempre devuelve una tupla para evitar errores de desempaquetado.
    """
    if not rep_str:
        return (1, 0)  # Devuelve valores por defecto si la entrada es vacía

    try:
        # Convertimos a string y limpiamos la entrada
        texto = str(rep_str).lower().replace('×', 'x').replace(' ', '')

        series = 1
        # Extraer series si existen (ej: 3x...)
        if 'x' in texto:
            parts = texto.split('x')
            # Asegurarse de que la parte de las series sea un número válido
            if parts[0].isdigit():
                series = int(parts[0])
            rep_part = parts[1]
        else:
            rep_part = texto

        # Extraer todos los números de la parte de las repeticiones (ej: 10-12 o solo 10)
        numeros = [int(n) for n in re.findall(r'\d+', rep_part)]

        if not numeros:
            return (series, 0)  # Si no se encontraron números, devuelve 0 reps

        # Calcular el promedio de las repeticiones encontradas
        repeticiones = int(sum(numeros) / len(numeros))

        return (series, repeticiones)

    except (ValueError, TypeError, IndexError):
        # Si ocurre cualquier error durante el proceso, devuelve valores seguros.
        return (1, 0)
