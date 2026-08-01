from django.db import migrations, models
import django.db.models.deletion


def backfill_version_cierres_confirmados(apps, schema_editor):
    """Solo el marcador explícito previo es evidencia nocturna inequívoca."""
    ProsocheDiario = apps.get_model('diario', 'ProsocheDiario')
    ProsocheDiario.objects.filter(
        cierre_confirmado_en__isnull=False, cierre_version=0,
    ).update(cierre_version=1)


class Migration(migrations.Migration):
    dependencies = [('diario', '0024_prosochediario_apertura_explicita')]
    operations = [
        migrations.AddField(model_name='prosochediario', name='estado_animo_noche', field=models.IntegerField(blank=True, choices=[(1, 1), (2, 2), (4, 4), (5, 5)], help_text='Estado de ánimo elegido conscientemente al cierre', null=True)),
        migrations.AddField(model_name='prosochediario', name='cierre_version', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='prosochediario', name='cierre_payload_hash', field=models.CharField(blank=True, max_length=64, null=True)),
        migrations.RunPython(backfill_version_cierres_confirmados, migrations.RunPython.noop),
        migrations.CreateModel(
            name='CierreNocturnoOperacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('idempotency_key', models.UUIDField()), ('expected_version', models.PositiveIntegerField()),
                ('result_version', models.PositiveIntegerField(blank=True, null=True)), ('payload_hash', models.CharField(max_length=64)),
                ('estado', models.CharField(choices=[('pending', 'Pendiente'), ('processing', 'Procesando'), ('completed', 'Completada'), ('failed', 'Fallida'), ('superseded', 'Reemplazada'), ('noop', 'Sin cambios')], default='pending', max_length=16)),
                ('enrichment_payload', models.JSONField(blank=True, default=dict)), ('resultado', models.JSONField(blank=True, default=dict)),
                ('error', models.TextField(blank=True)), ('processing_started_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)), ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('entrada', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operaciones_cierre', to='diario.prosochediario')),
            ],
        ),
        migrations.AddConstraint(model_name='cierrenocturnooperacion', constraint=models.UniqueConstraint(fields=('entrada', 'idempotency_key'), name='uniq_cierre_entrada_key')),
        migrations.AddConstraint(model_name='cierrenocturnooperacion', constraint=models.UniqueConstraint(fields=('entrada', 'result_version'), name='uniq_cierre_entrada_version')),
    ]
