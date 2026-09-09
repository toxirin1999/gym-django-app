from django.db import migrations, models


def pendientes_a_informativas(apps, schema_editor):
    EvaluacionSemanalGym = apps.get_model('entrenos', 'EvaluacionSemanalGym')
    EvaluacionSemanalGym.objects.filter(estado_revision='pendiente').update(
        estado_revision='informativa',
    )


def informativas_a_pendientes(apps, schema_editor):
    EvaluacionSemanalGym = apps.get_model('entrenos', 'EvaluacionSemanalGym')
    EvaluacionSemanalGym.objects.filter(estado_revision='informativa').update(
        estado_revision='pendiente',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('entrenos', '0050_ejerciciorealizado_multiplicador_carga_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evaluacionsemanalgym',
            name='estado_revision',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('informativa', 'Informativa'),
                    ('aceptada', 'Aceptada'),
                    ('rechazada', 'Rechazada'),
                ],
                db_index=True,
                default='informativa',
                max_length=11,
            ),
        ),
        migrations.RunPython(
            pendientes_a_informativas,
            informativas_a_pendientes,
        ),
    ]
