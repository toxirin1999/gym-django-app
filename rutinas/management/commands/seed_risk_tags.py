"""
Management command: seed_risk_tags

Populates risk_tags on EjercicioBase based on exercise name and muscle group.
Safe to run multiple times — only sets tags on exercises with empty risk_tags.

Usage:
    python manage.py seed_risk_tags [--settings=...]
    python manage.py seed_risk_tags --overwrite  # also updates non-empty
    python manage.py seed_risk_tags --dry-run    # shows what would change
"""

from django.core.management.base import BaseCommand
from rutinas.models import EjercicioBase


# ── Risk tag mapping ──────────────────────────────────────────────────────────
# Format: (keyword_patterns, tags_to_assign)
# Keyword matching: any pattern present in nombre.lower() OR grupo_muscular.lower()

_REGLAS = [
    # Rodilla — flexión profunda
    (
        ['sentadilla', 'squat', 'prensa de pierna', 'zancada', 'lunge',
         'búlgara', 'bulgara', 'hack', 'sissy', 'pistol'],
        ['flexion_rodilla_profunda'],
    ),
    # Rodilla + extensión explosiva
    (
        ['sentadilla', 'squat', 'hack', 'búlgara', 'bulgara', 'pistol'],
        ['triple_extension_explosiva'],
    ),
    # Impacto vertical (saltos, pliometría, box jump)
    (
        ['salto', 'jump', 'box', 'plio', 'plyometric', 'drop'],
        ['impacto_vertical', 'triple_extension_explosiva'],
    ),
    # Hombro — inestabilidad (movimientos de empuje por encima de la cabeza)
    (
        ['press militar', 'press de hombro', 'overhead press', 'arnold',
         'elevación frontal', 'elevacion frontal', 'push press'],
        ['hombro_inestable'],
    ),
    # Hombro — manguito rotador
    (
        ['elevación lateral', 'elevacion lateral', 'aperturas', 'pájaro',
         'pajaro', 'face pull', 'rotación externa', 'rotacion externa'],
        ['manguito_rotador'],
    ),
    # Espalda baja — carga espinal alta
    (
        ['peso muerto', 'deadlift', 'buenos días', 'buenos dias',
         'good morning', 'rdl', 'romanian'],
        ['carga_espinal_alta'],
    ),
    # Cadera / isquios — tensión isquiofemoral
    (
        ['peso muerto rumano', 'rdl', 'romanian', 'curl femoral',
         'leg curl', 'isquiotibial', 'nordic curl'],
        ['tension_isquiofemoral'],
    ),
    # Carrera / impacto horizontal
    (
        ['sprint', 'carrera', 'running', 'skierg', 'ski erg'],
        ['impacto_horizontal', 'carga_cardio_alta'],
    ),
    # Kettlebell ballistic
    (
        ['swing', 'snatch', 'clean', 'kettlebell'],
        ['triple_extension_explosiva', 'impacto_vertical'],
    ),
]


def _obtener_tags_para(nombre, grupo):
    texto = (nombre + ' ' + (grupo or '')).lower()
    tags = set()
    for patrones, etiquetas in _REGLAS:
        if any(p in texto for p in patrones):
            tags.update(etiquetas)
    return sorted(tags)


class Command(BaseCommand):
    help = 'Populate risk_tags on EjercicioBase based on exercise name/muscle group.'

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true',
                            help='Also update exercises that already have tags.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would change without saving.')

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        dry_run = options['dry_run']

        qs = EjercicioBase.objects.all()
        if not overwrite:
            qs = qs.filter(risk_tags=[])

        actualizados = 0
        sin_match = 0

        for ej in qs:
            tags = _obtener_tags_para(ej.nombre, ej.grupo_muscular)
            if not tags:
                sin_match += 1
                continue
            if dry_run:
                self.stdout.write(f'  {ej.nombre}: {tags}')
            else:
                ej.risk_tags = tags
                ej.save(update_fields=['risk_tags'])
            actualizados += 1

        modo = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{modo}Actualizados: {actualizados} ejercicios. '
            f'Sin match: {sin_match} (permanecen con tags vacíos).'
        ))
