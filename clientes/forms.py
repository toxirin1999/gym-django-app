from django import forms
from .models import Cliente, Medida
from .models import RevisionProgreso
from django.db import models
from .models import ObjetivoCliente
from django import forms

from django import forms

from django import forms
from .models import BitacoraDiaria
from django import forms
# en clientes/forms.py

from django import forms
from .models import BitacoraDiaria  # Asegúrate de que BitacoraDiaria esté en models.py


class CheckinDiarioForm(forms.ModelForm):
    class Meta:
        model = BitacoraDiaria
        # Seleccionamos solo los campos relevantes para el check-in
        fields = ['energia_subjetiva', 'dolor_articular', 'horas_sueno']

        # Widgets para hacerlos más amigables
        widgets = {
            'energia_subjetiva': forms.NumberInput(
                attrs={'type': 'range', 'min': '1', 'max': '10', 'class': 'range-slider'}),
            'dolor_articular': forms.NumberInput(
                attrs={'type': 'range', 'min': '1', 'max': '10', 'class': 'range-slider'}),
            # --- CORRECCIÓN ---
            'horas_sueno': forms.NumberInput(
                attrs={'type': 'range', 'min': '0', 'max': '12', 'step': '0.5', 'class': 'range-slider'}),
        }

        labels = {
            'energia_subjetiva': 'Nivel de Energía Hoy (1-10)',
            'dolor_articular': 'Nivel de Molestias/Dolor (1-10)',
            # --- CORRECCIÓN ---
            'horas_sueno': 'Horas de Sueño Anoche',
        }


EMOCIONES_CHOICES = [
    ('', '---------'),  # opción vacía
    ('feliz', '😊 Feliz'),
    ('contento', '😄 Contento'),
    ('alegria', '😁 Alegría'),
    ('tranquilo', '😌 Tranquilo'),
    ('neutral', '😐 Neutral'),
    ('meh', '😑 Meh'),
    ('estresado', '😣 Estresado'),
    ('triste', '😢 Triste'),
    ('agotado', '🥱 Agotado'),
    ('ansioso', '😰 Ansioso'),
    ('cansado', '😴 Cansado'),
    ('solo', '😔 Solo'),
]


# En forms.py
class PreferenciasClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'dias_disponibles',
            'tiempo_por_sesion',
            'ejercicios_preferidos',
            'ejercicios_evitar',
            'flexibilidad_horario',
            'nivel_estres',
            'calidad_sueño',
            'nivel_energia'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Personalizar widgets
        self.fields['ejercicios_preferidos'].widget = forms.CheckboxSelectMultiple(
            choices=EJERCICIOS_DISPONIBLES
        )
        self.fields['ejercicios_evitar'].widget = forms.CheckboxSelectMultiple(
            choices=EJERCICIOS_DISPONIBLES
        )

        # Añadir clases CSS
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


# forms.py
from django import forms
from .models import Cliente

from django import forms
from .models import Cliente

# Es una buena práctica definir las opciones una sola vez para reutilizarlas
EJERCICIOS_CHOICES = [
    ('sentadilla', 'Sentadilla'),
    ('press_banca', 'Press de Banca'),
    ('peso_muerto', 'Peso Muerto'),
    ('press_militar', 'Press Militar'),
    ('remo_con_barra', 'Remo con Barra'),
    ('dominadas', 'Dominadas'),
    ('fondos', 'Fondos'),
    ('curl_biceps', 'Curl de Bíceps'),
    ('extension_triceps', 'Extensión de Tríceps'),
    ('elevaciones_laterales', 'Elevaciones Laterales'),
    ('peso_muerto_rumano', 'Peso Muerto Rumano'),
]


class PreferenciasHelmsForm(forms.ModelForm):
    """
    Formulario para recopilar preferencias de adherencia según metodología Helms
    """
    nivel_experiencia_selector = forms.ChoiceField(
        choices=[
            # (valor_que_recibimos, texto_que_ve_el_usuario)
            ('0.5', 'Principiante (< 1 año)'),
            ('2.0', 'Intermedio (1-3 años)'),
            ('4.0', 'Avanzado (> 3 años)'),
        ],
        label="Selecciona tu nivel de experiencia",
        widget=forms.Select(attrs={'class': 'form-select'})  # Usamos el widget de selector
    )
    # Definición explícita de los campos (¡Esto está perfecto!)
    ejercicios_preferidos = forms.MultipleChoiceField(
        choices=EJERCICIOS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Ejercicios que más disfrutas"
    )

    ejercicios_evitar = forms.MultipleChoiceField(
        choices=EJERCICIOS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Ejercicios a evitar (lesiones, limitaciones, etc.)"
    )

    class Meta:
        model = Cliente
        fields = [
            'nivel_experiencia_selector',  # <-- El nuevo selector
            'dias_disponibles',
            'tiempo_por_sesion',
            'flexibilidad_horario',
            'ejercicios_preferidos',
            'ejercicios_evitar',
            'nivel_estres',
            'calidad_sueño',
            'nivel_energia'
        ]
        exclude = ['experiencia_años']
        # 👇 SECCIÓN DE WIDGETS LIMPIA Y SIN REDUNDANCIAS
        widgets = {
            'dias_disponibles': forms.Select(choices=[
                (2, '2 días - Mínimo efectivo'),
                (3, '3 días - Principiante ideal'),
                (4, '4 días - Intermedio estándar'),
                (5, '5 días - Avanzado activo'),
                (6, '6 días - Muy experimentado'),
                (7, '7 días - Atleta dedicado')
            ]),
            'tiempo_por_sesion': forms.Select(choices=[
                (45, '45 min - Sesión express'),
                (60, '60 min - Estándar'),
                (75, '75 min - Completa'),
                (90, '90 min - Extendida'),
                (120, '120 min - Muy larga')
            ]),
            'nivel_estres': forms.RadioSelect(choices=[
                (1, '1 - Muy relajado'),
                (3, '3 - Poco estrés'),
                (5, '5 - Estrés moderado'),
                (7, '7 - Bastante estresado'),
                (10, '10 - Muy estresado')
            ]),
            'calidad_sueño': forms.RadioSelect(choices=[
                (1, '1 - Muy mala'),
                (3, '3 - Mala'),
                (5, '5 - Regular'),
                (7, '7 - Buena'),
                (10, '10 - Excelente')
            ]),
            'nivel_energia': forms.RadioSelect(choices=[
                (1, '1 - Muy bajo'),
                (3, '3 - Bajo'),
                (5, '5 - Moderado'),
                (7, '7 - Alto'),
                (10, '10 - Muy alto')
            ])
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            años = self.instance.experiencia_años
            if años < 1:
                self.fields['nivel_experiencia_selector'].initial = '0.5'
            elif años < 3:
                self.fields['nivel_experiencia_selector'].initial = '2.0'
            else:
                self.fields['nivel_experiencia_selector'].initial = '4.0'
        # Añadir clases CSS para styling
        for field_name, field in self.fields.items():
            if field_name in ['ejercicios_preferidos', 'ejercicios_evitar']:
                field.widget.attrs.update({'class': 'form-check-input'})
            elif field_name in ['nivel_estres', 'calidad_sueño', 'nivel_energia']:
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

        # Añadir help text educativo
        self.fields['dias_disponibles'].help_text = (
            "Sé realista. Es mejor entrenar 3 días consistentemente "
            "que planear 6 días y fallar."
        )

        self.fields['ejercicios_preferidos'].help_text = (
            "Los ejercicios que disfrutas aumentan tu adherencia al programa. "
            "Selecciona los que realmente te gustan."
        )

        self.fields['nivel_estres'].help_text = (
            "El estrés afecta tu recuperación. Esto nos ayuda a ajustar "
            "la intensidad de tu entrenamiento."
        )


class SugerenciaForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[('aceptar', 'Aplicar sugerencia'), ('ignorar', 'Ignorar')],
        widget=forms.RadioSelect
    )


class BitacoraDiariaForm(forms.ModelForm):
    energia_subjetiva = forms.IntegerField(min_value=0, max_value=10)
    dolor_articular = forms.IntegerField(min_value=0, max_value=10)
    autoconciencia = forms.IntegerField(min_value=0, max_value=10)
    emocion_dia = forms.ChoiceField(choices=EMOCIONES_CHOICES, required=False,
                                    widget=forms.Select(attrs={'class': 'input'}))

    class Meta:
        model = BitacoraDiaria
        fields = [
            'horas_sueno', 'humor', 'rpe', 'peso_kg', 'energia_subjetiva', 'dolor_articular', 'nota_personal',
            'autoconciencia', 'descarga_cognitiva', 'rumiacion_baja',
            'mindfulness_am', 'mindfulness_pm', 'circunferencia_biceps',
            'emocion_dia', 'cosas_positivas', 'aprendizaje',
            'limito_socialmente', 'check_in_energia',
            'quien_quiero_ser', 'tareas_dia', 'que_puedo_mejorar', 'reflexion_diaria'
        ]

        widgets = {
            'horas_sueno': forms.NumberInput(attrs={'class': 'input', 'step': '0.25'}),
            'rpe': forms.NumberInput(attrs={'class': 'input', 'min': 1, 'max': 10}),
            'humor': forms.Select(attrs={'class': 'input'}),
            'nota_personal': forms.Textarea(attrs={'class': 'input', 'rows': 3}),
            'emocion_dia': forms.TextInput(attrs={'class': 'input'}),
            'cosas_positivas': forms.Textarea(attrs={'class': 'input', 'rows': 3}),
            'aprendizaje': forms.Textarea(attrs={'class': 'input', 'rows': 2}),
            'check_in_energia': forms.Select(attrs={'class': 'input'}),
            'quien_quiero_ser': forms.Textarea(attrs={'class': 'input', 'rows': 2}),
            'tareas_dia': forms.Textarea(attrs={'class': 'input', 'rows': 3}),
            'que_puedo_mejorar': forms.Textarea(attrs={'class': 'input', 'rows': 2}),
            'reflexion_diaria': forms.Textarea(attrs={'class': 'input', 'rows': 3}),
            'descarga_cognitiva': forms.Textarea(attrs={'class': 'input', 'rows': 3}),
            'rumiacion_baja': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'peso_kg': forms.NumberInput(
                attrs={'class': 'input border-2 border-green-400 rounded-xl px-4 py-2 shadow-sm',
                       'placeholder': 'Ej: 85.0',
                       'step': '0.1'}),
            'circunferencia_biceps': forms.NumberInput(
                attrs={'class': 'input border-2 border-green-400 rounded-xl px-4 py-2 shadow-sm',
                       'placeholder': 'Ej: 34.5',
                       'step': '0.1'}),

        }


class DatosNutricionalesForm(forms.Form):
    edad = forms.IntegerField(label="Edad", min_value=1, max_value=120)
    genero = forms.ChoiceField(label="Género", choices=[('M', 'Masculino'), ('F', 'Femenino')])
    altura_cm = forms.DecimalField(label="Altura (cm)", max_digits=5, decimal_places=2, min_value=50)
    peso_kg = forms.DecimalField(label="Peso (kg)", max_digits=5, decimal_places=2, min_value=20)

    NIVEL_ACTIVIDAD_CHOICES = [
        ('sedentario', 'Sedentario (poco o ningún ejercicio)'),
        ('levemente_activo', 'Levemente activo (ejercicio ligero/deporte 1-3 días/semana)'),
        ('moderadamente_activo', 'Moderadamente activo (ejercicio moderado/deporte 3-5 días/semana)'),
        ('muy_activo', 'Muy activo (ejercicio intenso/deporte 6-7 días/semana)'),
        ('extremadamente_activo', 'Extremadamente activo (ejercicio muy intenso/trabajo físico)'),
    ]
    nivel_actividad = forms.ChoiceField(label="Nivel de Actividad Física", choices=NIVEL_ACTIVIDAD_CHOICES)

    OBJETIVO_CHOICES = [
        ('masa_muscular', 'Ganar Masa Muscular'),
        ('definir', 'Definir / Mantener Peso'),
        ('perder_peso', 'Perder Peso'),
    ]
    objetivo = forms.ChoiceField(label="Objetivo", choices=OBJETIVO_CHOICES)

    # Puedes añadir más campos para preferencias dietéticas si lo deseas
    # comidas_dia = forms.IntegerField(label="Número de comidas al día deseadas", min_value=2, max_value=6, required=False)
    # restricciones_dieteticas = forms.CharField(label="Restricciones o preferencias dietéticas (ej. vegetariano, sin lactosa)", widget=forms.Textarea, required=False)


class ObjetivoClienteForm(forms.ModelForm):
    class Meta:
        model = ObjetivoCliente
        fields = ['medida', 'valor']
        error_messages = {
            'medida': {
                'required': 'Selecciona una medida.',
            },
            'valor': {
                'required': 'Debes ingresar un valor objetivo.',
            },
        }

    def __init__(self, *args, **kwargs):
        self.cliente = kwargs.pop('cliente', None)
        self.instancia = kwargs.get('instance')
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        medida = cleaned_data.get('medida')

        if not self.cliente or not medida:
            return

        existe = ObjetivoCliente.objects.filter(cliente=self.cliente, medida=medida)
        if self.instancia:
            existe = existe.exclude(pk=self.instancia.pk)

        if existe.exists():
            raise forms.ValidationError(f"Ya existe un objetivo para {self.cliente.nombre} con la medida '{medida}'.")

        return cleaned_data


class RevisionProgresoForm(forms.ModelForm):
    class Meta:
        model = RevisionProgreso
        fields = '__all__'
        exclude = ['cliente']  # si lo asignas desde la vista
        widgets = {
                      field: forms.NumberInput(attrs={'class': 'form-control'})
                      for field in model._meta.get_fields()
                      if isinstance(field, models.DecimalField) or isinstance(field, models.FloatField)
                  } | {
                      'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                  }


class MedidaForm(forms.ModelForm):
    class Meta:
        model = Medida
        fields = ['nombre', 'valor', 'unidad']


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombre', 'email', 'telefono', 'fecha_nacimiento', 'direccion', 'genero',
            'membresia_activa', 'fecha_vencimiento_membresia', 'programa',  # ✅ añadimos programa aquí
            'peso_corporal', 'grasa_corporal', 'cintura', 'pecho', 'hombro', 'cuello',
            'biceps', 'antebrazos', 'caderas', 'muslos', 'gemelos', 'proximo_registro_peso', 'foto'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'genero': forms.Select(attrs={'class': 'form-select'}),
            'membresia_activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fecha_vencimiento_membresia': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'programa': forms.Select(attrs={'class': 'form-select'}),  # ✅ widget para programa
            'peso_corporal': forms.NumberInput(attrs={'class': 'form-control'}),
            'grasa_corporal': forms.NumberInput(attrs={'class': 'form-control'}),
            'cintura': forms.NumberInput(attrs={'class': 'form-control'}),
            'pecho': forms.NumberInput(attrs={'class': 'form-control'}),
            'hombro': forms.NumberInput(attrs={'class': 'form-control'}),
            'cuello': forms.NumberInput(attrs={'class': 'form-control'}),
            'biceps': forms.NumberInput(attrs={'class': 'form-control'}),
            'antebrazos': forms.NumberInput(attrs={'class': 'form-control'}),
            'caderas': forms.NumberInput(attrs={'class': 'form-control'}),
            'muslos': forms.NumberInput(attrs={'class': 'form-control'}),
            'gemelos': forms.NumberInput(attrs={'class': 'form-control'}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(ClienteForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label


from .models import PesoDiario, ObjetivoPeso


# Formularios para el control de peso y evolución

class PesoDiarioForm(forms.ModelForm):
    class Meta:
        model = PesoDiario
        fields = ['peso_kg']
        widgets = {
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 75.5', 'step': '0.1'})
        }


class ObjetivoPesoForm(forms.ModelForm):
    class Meta:
        model = ObjetivoPeso
        fields = ['peso_objetivo_kg', 'fecha_fin']
        widgets = {
            'peso_objetivo_kg': forms.NumberInput(
                attrs={'class': 'form-control', 'placeholder': 'Ej: 70.0', 'step': '0.1'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        }
