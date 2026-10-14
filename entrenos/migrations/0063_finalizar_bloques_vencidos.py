"""Cierra los acuerdos de bloque Gym que vencieron hace más de una semana (14-oct-2026).

Solo se cerraban a mano (comando ``cerrar_bloque_gym``) y el Centro los mostraba
"pendientes de cierre" durante semanas. Desde ahora se cierran al guardar una
sesión; esta migración pone al día los que ya estaban vencidos. Solo cambia el
estado (no toca evaluaciones ni sesiones). No se revierte (no queda marca de qué bloques cerró).
"""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone



def cerrar(apps, schema_editor):
    Bloque = apps.get_model('entrenos', 'ContratoBloqueGym')
    limite = timezone.localdate() - timedelta(days=7)
    Bloque.objects.filter(
        estado__in=['activo', 'pausado'], semana_fin_prevista__lt=limite,
    ).update(estado='finalizado', actualizado_en=timezone.now())


def deshacer(apps, schema_editor):
    # Sin marca persistida (el bloque aprobado es inmutable salvo su estado):
    # no se puede distinguir qué bloques cerró esta migración. No se revierte.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('entrenos', '0062_tope_maquina_gym'),
    ]
    operations = [
        migrations.RunPython(cerrar, deshacer),
    ]
