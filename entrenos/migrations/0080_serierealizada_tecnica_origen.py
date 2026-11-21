from django.db import migrations, models


def marcar_sin_valorar(apps, schema_editor):
    Serie = apps.get_model('entrenos', 'SerieRealizada')
    Serie.objects.filter(tecnica_calidad__isnull=True).update(tecnica_origen='sin_valorar')
    Serie.objects.filter(tecnica_calidad='').update(tecnica_origen='sin_valorar')


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0079_guardado_sesion_token_huella_correccion'),
    ]

    operations = [
        migrations.AddField(
            model_name='serierealizada',
            name='tecnica_origen',
            field=models.CharField(
                choices=[('elegida', 'Elegida por el usuario'), ('sin_valorar', 'Sin valorar'),
                         ('desconocida', 'Anterior al registro de origen')],
                default='desconocida', max_length=12,
                help_text=("21-nov-2026 (etapa 3): 'elegida' solo si el usuario tocó la técnica de esta serie; "
                           "'sin_valorar' si no la eligió; 'desconocida' en series anteriores, cuando «buena» "
                           "podía venir marcada por defecto.")),
        ),
        migrations.RunPython(marcar_sin_valorar, migrations.RunPython.noop),
    ]
