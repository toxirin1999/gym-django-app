from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0044_gymdecisionlog_molestia_reciente'),
    ]

    operations = [
        migrations.AddField(
            model_name='entrenorealizado',
            name='gym_decision_emitida_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='entrenorealizado',
            name='gym_decision_estado_causal',
            field=models.CharField(blank=True, choices=[('exacta', 'Exacta'), ('superada_durante_ejecucion', 'Superada durante la ejecución')], max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='entrenorealizado',
            name='gym_decision_version',
            field=models.ForeignKey(blank=True, help_text='Versión exacta de autoridad supervisada mostrada al iniciar la sesión.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='entrenos_ejecutados', to='entrenos.gymdecisionversion'),
        ),
    ]
