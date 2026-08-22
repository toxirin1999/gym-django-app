import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('entrenos', '0048_evaluacionbloquegym'), ('hyrox', '0025_stravaactivityraw_actividad_hub')]
    operations = [
        migrations.CreateModel(
            name='ContratoCampanaHyrox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('estado', models.CharField(choices=[('inactiva','Inactiva'),('exploracion','Exploracion'),('activa','Activa'),('finalizada','Finalizada')], db_index=True, max_length=16)),
                ('objetivo_snapshot', models.JSONField(default=dict)), ('bloque_gym_snapshot', models.JSONField(default=dict)),
                ('limites_snapshot', models.JSONField(default=dict)), ('fingerprint', models.CharField(max_length=64)),
                ('motivo', models.TextField(blank=True)), ('aprobado_en', models.DateTimeField(blank=True, null=True)), ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('aprobado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campanas_hyrox_aprobadas', to='auth.user')),
                ('bloque_gym', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='campanas_hyrox', to='entrenos.contratobloquegym')),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contratos_campana_hyrox', to='clientes.cliente')),
                ('objetivo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='contratos_campana', to='hyrox.hyroxobjective')),
                ('predecesor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sucesores', to='hyrox.contratocampanahyrox')),
            ], options={'ordering': ['cliente_id','version']},
        ),
        migrations.AddConstraint(model_name='contratocampanahyrox', constraint=models.UniqueConstraint(fields=('cliente','version'), name='uniq_campana_hyrox_cliente_version')),
        migrations.AddConstraint(model_name='contratocampanahyrox', constraint=models.UniqueConstraint(fields=('cliente','fingerprint'), name='uniq_campana_hyrox_cliente_fingerprint')),
    ]
