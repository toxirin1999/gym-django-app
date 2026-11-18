"""Qué se puede comparar con qué (18-nov-2026).

Dos marcas de fuerza solo son comparables si salen del mismo tramo de
repeticiones y del mismo bloque de entrenamiento: 3 reps en un bloque de
potencia no se comparan con 14 reps en uno de hipertrofia, y una semana de
descarga no se compara con nada. Cada comparación debe poder enseñar las
fechas y referencias que usó.

También se comprueba el origen de un peso con decimales sin descartarlo por
tenerlos: un 71,3 kg que sube en saltos de 5 kg dentro de la sesión es una
máquina con otra tara, no un error; una media de series sí es una media.
"""
from __future__ import annotations

from datetime import timedelta

TOLERANCIA_KG = 0.05
SALTO_POR_DEFECTO_KG = 2.5


def familia_de_fase(fase):
    fase = str(fase or '').casefold()
    if fase.startswith('hipertrofia'):
        return 'hipertrofia'
    if fase in ('fuerza', 'potencia', 'descarga'):
        return fase
    return 'desconocido'


class Bloques:
    """Bloque del plan al que pertenecía cada fecha (registro semanal o, antes, calendario)."""

    def __init__(self, cliente):
        from entrenos.models import SemanaPlanGym
        from entrenos.services.periodizacion_dinamica_service import _periodizacion

        self._registros = {
            r.lunes: r for r in SemanaPlanGym.objects.filter(cliente=cliente)
        }
        self._periodizacion = _periodizacion()
        self._memo = {}

    def _bloque_de_semana(self, semana_plan):
        for b in self._periodizacion:
            if semana_plan in b.get('semanas', []):
                return b
        return None

    def de(self, fecha):
        lunes = fecha - timedelta(days=fecha.weekday())
        if lunes in self._memo:
            return self._memo[lunes]
        from entrenos.services.periodizacion_dinamica_service import _ciclar, semana_calendario

        registro = self._registros.get(lunes)
        if registro is not None:
            semana, origen = registro.semana_plan, 'registro'
            bloque = self._bloque_de_semana(semana)
            if registro.descarga:
                info = {'familia': 'descarga', 'nombre': 'Descarga', 'semana_plan': semana, 'origen': origen}
            else:
                info = {'familia': familia_de_fase((bloque or {}).get('fase')),
                        'nombre': (bloque or {}).get('nombre') or 'Sin bloque',
                        'semana_plan': semana, 'origen': origen}
        else:
            semana = _ciclar(semana_calendario(lunes))
            bloque = self._bloque_de_semana(semana)
            info = {'familia': familia_de_fase((bloque or {}).get('fase')),
                    'nombre': (bloque or {}).get('nombre') or 'Sin bloque',
                    'semana_plan': semana, 'origen': 'calendario'}
        self._memo[lunes] = info
        return info


def _salto(nombre):
    try:
        from entrenos.services.maquina_service import salto_fisico
        return float(salto_fisico(nombre) or SALTO_POR_DEFECTO_KG)
    except Exception:  # pragma: no cover
        return SALTO_POR_DEFECTO_KG


def _en_escala(peso, salto):
    if salto <= 0:
        return True
    resto = abs(peso / salto - round(peso / salto)) * salto
    return resto <= TOLERANCIA_KG


def revisar_peso(nombre, peso, pesos_sesion=(), fuente='serie', tipo_carga=None):
    """Comprueba de dónde sale un peso. Nunca lo descarta solo por tener decimales.

    Devuelve ``{'estado': 'ok' | 'desfase_constante' | 'a_comprobar', 'nota': str | None}``.

    - ``fuente='media'`` (entreno sin detalle por serie): es una media, no una
      carga montada; vale y se anota su origen.
    - Un peso que no cae en la escala de la máquina pero con otras series de la
      misma sesión separadas por saltos exactos de la escala (61,3 → 66,3 → 71,3
      en saltos de 5): la máquina tiene otra tara o la báscula otro cero; vale.
    - Un peso fuera de escala sin nada que lo respalde en la sesión: a comprobar
      su origen, la unidad (por mano, por lado o total) y la máquina.
    """
    peso = float(peso or 0)
    if peso <= 0:
        return {'estado': 'ok', 'nota': None}
    salto = _salto(nombre)
    if _en_escala(peso, salto):
        return {'estado': 'ok', 'nota': None}
    if fuente == 'media':
        # Una media de series no es una carga montada: que no caiga en escala es normal.
        # Vale (no se excluye por decimales), pero se anota su origen.
        return {'estado': 'ok',
                'nota': f'{peso:g} kg es la media de las series de un entreno sin detalle por serie'}
    distintos = sorted({round(float(p), 2) for p in pesos_sesion if p})
    if len(distintos) >= 2 and all(_en_escala(abs(p - distintos[0]), salto) for p in distintos[1:]):
        return {'estado': 'desfase_constante',
                'nota': (f'{peso:g} kg no cae en la escala de {salto:g} kg, pero toda la sesión sube en saltos '
                         f'de {salto:g} kg desde {distintos[0]:g}: es coherente con otra máquina o tara, pero el origen '
                         f'no está confirmado')}
    return {'estado': 'a_comprobar',
            'nota': (f'{peso:g} kg no encaja en la escala de {salto:g} kg y no hay otras series que lo respalden: '
                     f'comprueba el origen, la unidad (por mano, por lado o total) y la máquina')}
