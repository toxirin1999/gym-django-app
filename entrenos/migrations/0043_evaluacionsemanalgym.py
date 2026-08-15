import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0042_alter_gymdecisionlog_motivo_codigo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluacionSemanalGym',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_calculo', models.PositiveSmallIntegerField(default=1)),
                ('estado_cumplimiento', models.CharField(choices=[('objetivo', 'Objetivo'), ('minima_valida', 'Mínima válida'), ('insuficiente', 'Insuficiente')], max_length=16)),
                ('sesiones_completadas', models.PositiveSmallIntegerField(default=0)),
                ('sesiones_reubicadas', models.PositiveSmallIntegerField(default=0)),
                ('evidencia_snapshot', models.JSONField(default=dict)),
                ('estado_revision', models.CharField(choices=[('pendiente', 'Pendiente'), ('aceptada', 'Aceptada'), ('rechazada', 'Rechazada')], db_index=True, default='pendiente', max_length=10)),
                ('respondida_en', models.DateTimeField(blank=True, null=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('actualizada_en', models.DateTimeField(auto_now=True)),
                ('contrato', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='evaluacion', to='entrenos.contratosemanalgym')),
                ('respondida_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluaciones_semanales_gym_respondidas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-contrato__semana', '-id'],
            },
        ),
    ]
