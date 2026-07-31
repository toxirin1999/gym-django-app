from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('entrenos', '0029_gymdecisionlog_estado_aplicacion_and_more')]

    operations = [
        migrations.AddField(
            model_name='sugerenciaplan',
            name='contrato_snapshot',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
