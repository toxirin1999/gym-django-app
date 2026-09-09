from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('entrenos', '0052_alter_sesionprogramada_estado_ausenciaplanificadagym_and_more')]
    operations = [
        migrations.AddField(
            model_name='ausenciaplanificadagym', name='cancelada_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ausenciaplanificadagym', name='fecha_cancelacion_efectiva',
            field=models.DateField(blank=True, null=True),
        ),
    ]
