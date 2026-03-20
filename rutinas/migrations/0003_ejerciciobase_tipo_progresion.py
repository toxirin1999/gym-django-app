from django.db import migrations, models


# Mapa completo: nombre ejercicio → tipo_progresion
TIPOS_EJERCICIOS = {
    # Peso corporal + lastre
    'Dominadas (con lastre)':        'peso_corporal_lastre',
    'Fondos en Paralelas (con lastre)': 'peso_corporal_lastre',
    'Dips (Fondos en Pecho)':        'peso_corporal_lastre',

    # Solo repeticiones
    'Ab Wheel (Rueda Abdominal)':    'progresion_reps',
    'Burpee Broad Jump':             'progresion_reps',
    'Curl Nórdico (Nordic Hamstring Curl)': 'progresion_reps',
    'Elevaciones de Piernas Colgado': 'progresion_reps',
    'Fondos entre Bancos':           'progresion_reps',
    'Sandbag Lunges':                'progresion_reps',
    'Sissy Squat':                   'progresion_reps',
    'Wall Balls':                    'progresion_reps',
    'Y-Raises':                      'progresion_reps',

    # Tiempo
    'Plancha (Plank)':               'progresion_tiempo',
    'Aguante en Barra (Dead Hang)':  'progresion_tiempo',

    # Distancia / metros
    'Farmer Walk (Paseo del Granjero)': 'progresion_distancia',
    'Farmers Carry':                 'progresion_distancia',
    'Rowing':                        'progresion_distancia',
    'SkiErg':                        'progresion_distancia',
    'Sled Pull':                     'progresion_distancia',
    'Sled Push':                     'progresion_distancia',

    # Variante de dificultad
    'Dead Bug':                      'progresion_variante',
}


def asignar_tipos(apps, schema_editor):
    EjercicioBase = apps.get_model('rutinas', 'EjercicioBase')
    for nombre, tipo in TIPOS_EJERCICIOS.items():
        EjercicioBase.objects.filter(nombre__iexact=nombre).update(tipo_progresion=tipo)


def revertir_tipos(apps, schema_editor):
    EjercicioBase = apps.get_model('rutinas', 'EjercicioBase')
    EjercicioBase.objects.all().update(tipo_progresion='peso_reps')


class Migration(migrations.Migration):

    dependencies = [
        ('rutinas', '0002_ejerciciobase_risk_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='ejerciciobase',
            name='tipo_progresion',
            field=models.CharField(
                choices=[
                    ('peso_reps',            'Peso + repeticiones'),
                    ('progresion_reps',       'Solo repeticiones'),
                    ('progresion_tiempo',     'Tiempo'),
                    ('progresion_distancia',  'Distancia / metros'),
                    ('peso_corporal_lastre',  'Peso corporal + lastre'),
                    ('progresion_variante',   'Variante de dificultad'),
                ],
                default='peso_reps',
                max_length=25,
                help_text='Define cómo se mide la progresión de este ejercicio',
            ),
        ),
        migrations.RunPython(asignar_tipos, revertir_tipos),
    ]
