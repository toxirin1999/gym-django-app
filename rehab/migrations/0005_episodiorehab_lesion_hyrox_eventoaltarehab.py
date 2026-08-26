import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hyrox', '0027_solicitudhyroxpuntual'),
        ('rehab', '0004_contratoriesgogymfaserehab_execution_enabled'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='episodiorehab',
            name='lesion_hyrox',
            field=models.ForeignKey(
                blank=True,
                help_text='Vínculo explícito opcional; nunca se infiere por texto o zona.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='episodios_rehab',
                to='hyrox.userinjury',
            ),
        ),
        migrations.CreateModel(
            name='EventoAltaRehab',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('nota_evidencia', models.TextField(blank=True)),
                ('motivo', models.CharField(default='confirmacion_usuario', max_length=40)),
                ('confirmacion_usuario', models.BooleanField(default=False)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='altas_rehab_confirmadas', to=settings.AUTH_USER_MODEL)),
                ('episodio', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='evento_alta', to='rehab.episodiorehab')),
                ('lesion_hyrox', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='eventos_alta_rehab', to='hyrox.userinjury')),
            ],
        ),
    ]
