from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('diario', '0027_personaimportante_archivada'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personaimportante',
            name='salud_relacion',
            field=models.IntegerField(
                blank=True,
                default=None,
                help_text='Salud percibida de la relación (1=Mala, 5=Excelente)',
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(5)],
            ),
        ),
    ]
