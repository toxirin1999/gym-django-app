from django.db import migrations, models
import django.db.models.deletion


def normalizar_legacy(apps, schema_editor):
    GymDecisionLog = apps.get_model('entrenos', 'GymDecisionLog')
    for log in GymDecisionLog.objects.only('pk', 'ejercicio').iterator():
        normalizado = ' '.join((log.ejercicio or '').split()).casefold()[:120]
        GymDecisionLog.objects.filter(pk=log.pk).update(ejercicio_normalizado=normalizado)


class Migration(migrations.Migration):
    dependencies = [('entrenos', '0031_entrenorealizado_fecha_ejecucion')]
    operations = [
        migrations.AddField(
            model_name='gymdecisionlog', name='entreno_origen',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='decisiones_generadas', to='entrenos.entrenorealizado'),
        ),
        migrations.AddField(
            model_name='gymdecisionlog', name='ejercicio_normalizado',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.RunPython(normalizar_legacy, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='gymdecisionlog',
            constraint=models.UniqueConstraint(
                fields=('cliente', 'entreno_origen', 'ejercicio_normalizado'),
                name='uniq_decision_origen_ejercicio_norm'),
        ),
    ]
