from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenos', '0008_add_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='ejerciciorealizado',
            name='molestia_reportada',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ejerciciorealizado',
            name='molestia_zona',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='ejerciciorealizado',
            name='molestia_severidad',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='1=Leve, 2=Moderada, 3=Severa/Aguda'
            ),
        ),
        migrations.AddField(
            model_name='ejerciciorealizado',
            name='molestia_descripcion',
            field=models.TextField(blank=True),
        ),
    ]
