from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('entrenos', '0048_evaluacionbloquegym')]

    operations = [
        migrations.AddField(
            model_name='gymdecisiontrace',
            name='senales_autorizadas',
            field=models.JSONField(default=list),
        ),
        migrations.CreateModel(
            name='SenalEntrenamientoAutorizada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categoria', models.CharField(choices=[('recuperacion', 'Recuperacion'), ('disponibilidad', 'Disponibilidad'), ('continuidad', 'Continuidad'), ('relacion_entrenamiento', 'Relacion Entrenamiento')], db_index=True, max_length=40)),
                ('intensidad', models.CharField(choices=[('suave', 'Suave'), ('moderada', 'Moderada'), ('alta', 'Alta')], max_length=20)),
                ('estado', models.CharField(choices=[('propuesta', 'Propuesta'), ('autorizada', 'Autorizada'), ('revocada', 'Revocada'), ('sustituida', 'Sustituida'), ('expirada', 'Expirada')], db_index=True, default='propuesta', max_length=20)),
                ('vigente_desde', models.DateField(db_index=True)),
                ('vigente_hasta', models.DateField(db_index=True)),
                ('autorizada_en', models.DateTimeField(blank=True, null=True)),
                ('revocada_en', models.DateTimeField(blank=True, null=True)),
                ('evidencia_tecnica', models.JSONField(blank=True, default=dict)),
                ('version', models.PositiveSmallIntegerField(default=1)),
                ('schema_version', models.PositiveSmallIntegerField(default=1)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('actualizada_en', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='senales_entrenamiento_autorizadas', to='clientes.cliente')),
                ('intervencion', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='senal_autorizada', to='entrenos.intervencionplan')),
                ('sugerencia', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='senal_autorizada', to='entrenos.sugerenciaplan')),
            ],
            options={'ordering': ['-creada_en']},
        ),
        migrations.AddIndex(
            model_name='senalentrenamientoautorizada',
            index=models.Index(fields=['cliente', 'estado', 'vigente_hasta'], name='senal_auth_cli_est_fin_idx'),
        ),
    ]
