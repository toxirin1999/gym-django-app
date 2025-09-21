from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, CalculoNivel1, CalculoNivel2, ConfiguracionNivel4, ConfiguracionNivel5


class UserProfileForm(forms.ModelForm):
    """Formulario para el perfil de usuario nutricional"""

    class Meta:
        model = UserProfile
        fields = ['edad', 'sexo', 'peso', 'altura', 'nivel_actividad', 'objetivo', 'experiencia']
        widgets = {
            'edad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 15,
                'max': 80,
                'placeholder': 'Ej: 25'
            }),
            'sexo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'peso': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 30,
                'max': 200,
                'step': 0.1,
                'placeholder': 'Ej: 70.5'
            }),
            'altura': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 120,
                'max': 220,
                'placeholder': 'Ej: 175'
            }),
            'nivel_actividad': forms.Select(attrs={
                'class': 'form-control'
            }),
            'objetivo': forms.Select(attrs={
                'class': 'form-control'
            }),
            'experiencia': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'edad': 'Edad (años)',
            'sexo': 'Sexo',
            'peso': 'Peso (kg)',
            'altura': 'Altura (cm)',
            'nivel_actividad': 'Nivel de Actividad',
            'objetivo': 'Objetivo Principal',
            'experiencia': 'Experiencia en Entrenamiento',
        }
        help_texts = {
            'edad': 'Tu edad actual en años',
            'peso': 'Tu peso actual en kilogramos',
            'altura': 'Tu altura en centímetros',
            'nivel_actividad': 'Selecciona el nivel que mejor describa tu actividad diaria',
            'objetivo': 'Tu objetivo principal con la nutrición',
            'experiencia': 'Tu nivel de experiencia con el entrenamiento',
        }

    def clean_edad(self):
        edad = self.cleaned_data.get('edad')
        if edad and (edad < 15 or edad > 80):
            raise forms.ValidationError('La edad debe estar entre 15 y 80 años.')
        return edad

    def clean_peso(self):
        peso = self.cleaned_data.get('peso')
        if peso and (peso < 30 or peso > 200):
            raise forms.ValidationError('El peso debe estar entre 30 y 200 kg.')
        return peso

    def clean_altura(self):
        altura = self.cleaned_data.get('altura')
        if altura and (altura < 120 or altura > 220):
            raise forms.ValidationError('La altura debe estar entre 120 y 220 cm.')
        return altura


class Nivel1Form(forms.Form):
    # Solo definimos el campo, sin valores iniciales ni widgets complejos aquí.
    factor_actividad = forms.FloatField(label="Factor de Actividad")

    def clean_factor_actividad(self):
        # Validación robusta
        factor = self.cleaned_data.get('factor_actividad')
        if not factor:
            raise forms.ValidationError("Este campo no puede estar vacío.")
        if not (1.3 <= factor <= 2.2):
            raise forms.ValidationError("El factor de actividad debe estar entre 1.3 y 2.2.")
        return factor


# En nutricion_app_django/forms.py

from django import forms


class Nivel2Form(forms.Form):
    proteina_gramos_kg = forms.FloatField(label="Gramos de Proteína por kg")
    grasa_porcentaje = forms.IntegerField(label="Porcentaje de Calorías de Grasa")

    # (Opcional pero recomendado) Añadir validaciones explícitas
    def clean_proteina_gramos_kg(self):
        data = self.cleaned_data['proteina_gramos_kg']
        if not (1.6 <= data <= 2.6):
            raise forms.ValidationError("El valor debe estar entre 1.6 y 2.6.")
        return data

    def clean_grasa_porcentaje(self):
        data = self.cleaned_data['grasa_porcentaje']
        if not (15 <= data <= 40):
            raise forms.ValidationError("El valor debe estar entre 15 y 40.")
        return data


# En nutricion_app_django/forms.py

class Nivel3Form(forms.Form):
    """Formulario de compromiso para el Nivel 3."""
    acepta_hidratacion = forms.BooleanField(
        label="Me comprometo a beber suficiente agua.",
        required=True
    )
    acepta_variedad = forms.BooleanField(
        label="Me comprometo a incluir variedad de frutas y verduras.",
        required=True
    )
    acepta_alimentos_enteros = forms.BooleanField(
        label="Priorizaré los alimentos enteros sobre los procesados.",
        required=True
    )

    def clean(self):
        cleaned_data = super().clean()
        # Verificamos que todos los checkboxes estén marcados
        if not all(cleaned_data.values()):
            raise forms.ValidationError("Debes aceptar todos los compromisos para continuar.")
        return cleaned_data


class SeguimientoPesoForm(forms.Form):
    """Formulario para registrar el peso"""

    peso = forms.FloatField(
        min_value=30,
        max_value=200,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': 0.1,
            'placeholder': 'Ej: 70.5'
        }),
        label='Peso Actual (kg)',
        help_text='Registra tu peso actual para hacer seguimiento'
    )

    notas = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notas opcionales sobre tu peso de hoy...'
        }),
        label='Notas (Opcional)',
        help_text='Puedes agregar notas sobre cómo te sientes, cambios en la dieta, etc.'
    )

    def clean_peso(self):
        peso = self.cleaned_data.get('peso')
        if peso and (peso < 30 or peso > 200):
            raise forms.ValidationError('El peso debe estar entre 30 y 200 kg.')
        return peso


# En nutricion_app_django/forms.py

class Nivel4Form(forms.ModelForm):
    """Formulario para la configuración del Nivel 4 - Timing y Frecuencia"""

    # Opciones basadas en tu script de Tkinter
    PRE_ENTRENO_CHOICES = [
        ("carbohidratos", "Carbohidratos principalmente (1-3h antes)"),
        ("proteina_carbohidratos", "Proteína + Carbohidratos (1-3h antes)"),
        ("comida_completa", "Comida completa normal"),
        ("ayunas", "Entrenar en ayunas"),
    ]
    POST_ENTRENO_CHOICES = [
        ("proteina_carbohidratos", "Proteína + Carbohidratos (0-2h después)"),
        ("solo_proteina", "Solo proteína (0-2h después)"),
        ("comida_completa", "Comida completa normal"),
        ("no_prioritario", "No es una prioridad para mí"),
    ]
    DISTRIBUCION_CHOICES = [
        ("uniforme", "Distribución uniforme en todas las comidas"),
        ("post_entreno", "Mayor cantidad post-entrenamiento"),
        ("extremos", "Mayor cantidad en desayuno y cena"),
        ("flexible", "Flexible según preferencias"),
    ]

    # Sobrescribimos los campos para usar widgets de radio en lugar de texto
    timing_pre_entreno = forms.ChoiceField(
        choices=PRE_ENTRENO_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Estrategia Pre-Entrenamiento"
    )
    timing_post_entreno = forms.ChoiceField(
        choices=POST_ENTRENO_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Estrategia Post-Entrenamiento"
    )
    distribucion_macros = forms.ChoiceField(
        choices=DISTRIBUCION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Distribución de Proteína"
    )

    class Meta:
        model = ConfiguracionNivel4
        fields = ['comidas_por_dia', 'timing_pre_entreno', 'timing_post_entreno', 'distribucion_macros']
        widgets = {
            'comidas_por_dia': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 3,
                'max': 6,
            }),
        }
        labels = {
            'comidas_por_dia': 'Número de comidas por día (3-6)',
        }


# En nutricion_app_django/forms.py

class Nivel5Form(forms.ModelForm):
    """Formulario para la configuración del Nivel 5 - Suplementos"""

    # Hacemos que los campos BooleanField no sean obligatorios
    creatina = forms.BooleanField(required=False, label="Creatina Monohidrato")
    proteina_polvo = forms.BooleanField(required=False, label="Proteína en Polvo")
    multivitaminico = forms.BooleanField(required=False, label="Multivitamínico")
    omega3 = forms.BooleanField(required=False, label="Omega-3 (EPA/DHA)")
    vitamina_d = forms.BooleanField(required=False, label="Vitamina D")

    # El campo 'otros_suplementos' ya está en el modelo y se incluirá

    class Meta:
        model = ConfiguracionNivel5
        # Incluimos los campos booleanos y el campo de texto para otros suplementos
        fields = ['creatina', 'proteina_polvo', 'multivitaminico', 'omega3', 'vitamina_d', 'otros_suplementos']
        widgets = {
            # Usamos CheckboxInput para los campos booleanos
            'creatina': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'proteina_polvo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'multivitaminico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'omega3': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'vitamina_d': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'otros_suplementos': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ej: Cafeína, Beta-Alanina, etc.'
            }),
        }
        labels = {
            'otros_suplementos': 'Otros suplementos que consideres'
        }
