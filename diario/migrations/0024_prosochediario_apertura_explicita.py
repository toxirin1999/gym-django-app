from django.db import migrations, models
from django.db.models import F, Q


def marcar_aperturas_historicas(apps, schema_editor):
    ProsocheDiario = apps.get_model('diario', 'ProsocheDiario')
    ProsocheDiario.objects.filter(
        Q(persona_quiero_ser__gt='') |
        Q(gratitud_1__gt='') | Q(gratitud_2__gt='') | Q(gratitud_3__gt='') |
        Q(gratitud_4__gt='') | Q(gratitud_5__gt='')
    ).update(apertura_confirmada_en=F('fecha_actualizacion'))


class Migration(migrations.Migration):
    dependencies = [('diario', '0023_alter_gesto_fecha_inicio')]

    operations = [
        migrations.AddField(
            model_name='prosochediario',
            name='apertura_confirmada_en',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Momento en que la apertura diaria quedó persistida con éxito',
            ),
        ),
        migrations.AddField(
            model_name='prosochediario',
            name='respuesta_joi_apertura',
            field=models.TextField(
                blank=True,
                help_text='Respuesta breve de JOI al registro consciente de la apertura',
            ),
        ),
        migrations.RunPython(marcar_aperturas_historicas, migrations.RunPython.noop),
    ]
