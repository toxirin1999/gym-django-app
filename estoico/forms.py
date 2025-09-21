from django import forms
from django.contrib.auth.models import User
from .models import (
    ReflexionDiaria, PerfilEstoico, ConfiguracionNotificacion,
    ContenidoDiario
)

class ReflexionDiariaForm(forms.ModelForm):
    """
    Formulario para crear/editar reflexiones diarias
    """
    class Meta:
        model = ReflexionDiaria
        fields = ['reflexion_personal', 'calificacion_dia', 'marcado_favorito']
        widgets = {
            'reflexion_personal': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Escribe tu reflexión personal aquí...',
                'required': True,
            }),
            'calificacion_dia': forms.Select(attrs={
                'class': 'form-select',
            }, choices=[
                ('', 'Selecciona una calificación'),
                (1, '⭐ - Día difícil'),
                (2, '⭐⭐ - Día regular'),
                (3, '⭐⭐⭐ - Día bueno'),
                (4, '⭐⭐⭐⭐ - Día muy bueno'),
                (5, '⭐⭐⭐⭐⭐ - Día excelente'),
            ]),
            'marcado_favorito': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'reflexion_personal': 'Tu reflexión personal',
            'calificacion_dia': '¿Cómo fue tu día?',
            'marcado_favorito': 'Marcar como favorito',
        }
        help_texts = {
            'reflexion_personal': 'Responde a la pregunta del día con honestidad y profundidad.',
            'calificacion_dia': 'Califica tu día del 1 al 5 basándote en cómo aplicaste los principios estoicos.',
            'marcado_favorito': 'Marca esta reflexión como favorita para encontrarla fácilmente después.',
        }

    def clean_reflexion_personal(self):
        reflexion = self.cleaned_data.get('reflexion_personal')
        if reflexion and len(reflexion.strip()) < 10:
            raise forms.ValidationError('La reflexión debe tener al menos 10 caracteres.')
        return reflexion

class ConfiguracionPerfilForm(forms.ModelForm):
    """
    Formulario para configurar el perfil estoico del usuario
    """
    class Meta:
        model = PerfilEstoico
        fields = [
            'filosofo_favorito', 
            'tema_favorito',
            'notificaciones_activas',
            'hora_notificacion'
        ]
        widgets = {
            'filosofo_favorito': forms.Select(attrs={
                'class': 'form-select',
            }),
            'tema_favorito': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Disciplina, Virtud, Aceptación...',
            }),
            'notificaciones_activas': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'hora_notificacion': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
        }
        labels = {
            'filosofo_favorito': 'Filósofo favorito',
            'tema_favorito': 'Tema de interés',
            'notificaciones_activas': 'Activar notificaciones',
            'hora_notificacion': 'Hora de notificación diaria',
        }
        help_texts = {
            'filosofo_favorito': 'Selecciona tu filósofo estoico favorito.',
            'tema_favorito': 'Indica qué temas estoicos te interesan más.',
            'notificaciones_activas': 'Recibe recordatorios diarios para tu práctica estoica.',
            'hora_notificacion': 'Hora en la que prefieres recibir tu recordatorio diario.',
        }

class ConfiguracionNotificacionForm(forms.ModelForm):
    """
    Formulario para configurar notificaciones detalladas
    """
    DIAS_SEMANA_CHOICES = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    dias_semana_seleccionados = forms.MultipleChoiceField(
        choices=DIAS_SEMANA_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
        }),
        required=False,
        label='Días activos',
        help_text='Selecciona los días en que quieres recibir notificaciones.'
    )
    
    class Meta:
        model = ConfiguracionNotificacion
        fields = [
            'notificacion_matutina',
            'hora_matutina',
            'notificacion_vespertina', 
            'hora_vespertina',
            'recordatorio_reflexion',
            'frecuencia_recordatorio',
        ]
        widgets = {
            'notificacion_matutina': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'hora_matutina': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'notificacion_vespertina': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'hora_vespertina': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'recordatorio_reflexion': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'frecuencia_recordatorio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 24,
            }),
        }
        labels = {
            'notificacion_matutina': 'Notificación matutina',
            'hora_matutina': 'Hora matutina',
            'notificacion_vespertina': 'Notificación vespertina',
            'hora_vespertina': 'Hora vespertina',
            'recordatorio_reflexion': 'Recordatorios de reflexión',
            'frecuencia_recordatorio': 'Frecuencia de recordatorios (horas)',
        }
        help_texts = {
            'notificacion_matutina': 'Recibe la cita y reflexión del día por la mañana.',
            'hora_matutina': 'Hora para la notificación matutina.',
            'notificacion_vespertina': 'Recibe un recordatorio para reflexionar por la noche.',
            'hora_vespertina': 'Hora para la notificación vespertina.',
            'recordatorio_reflexion': 'Recibe recordatorios si no has reflexionado.',
            'frecuencia_recordatorio': 'Cada cuántas horas recibir recordatorios.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['dias_semana_seleccionados'].initial = self.instance.dias_semana
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.dias_semana = self.cleaned_data.get('dias_semana_seleccionados', [])
        if commit:
            instance.save()
        return instance

class BusquedaContenidoForm(forms.Form):
    """
    Formulario para buscar contenido estoico
    """
    AUTORES_CHOICES = [
        ('', 'Todos los autores'),
        ('Marco Aurelio', 'Marco Aurelio'),
        ('Séneca', 'Séneca'),
        ('Epicteto', 'Epicteto'),
        ('Musonio Rufo', 'Musonio Rufo'),
        ('Zenón de Citio', 'Zenón de Citio'),
    ]
    
    TEMAS_CHOICES = [
        ('', 'Todos los temas'),
        ('Claridad y Percepción', 'Claridad y Percepción'),
        ('Pasiones y Emociones', 'Pasiones y Emociones'),
        ('Conciencia y Atención Plena', 'Conciencia y Atención Plena'),
        ('Acción Correcta', 'Acción Correcta'),
        ('Virtud y Carácter', 'Virtud y Carácter'),
        ('Disciplina y Autocontrol', 'Disciplina y Autocontrol'),
        ('Aceptación y Serenidad', 'Aceptación y Serenidad'),
        ('Sabiduría y Discernimiento', 'Sabiduría y Discernimiento'),
        ('Relaciones y Comunidad', 'Relaciones y Comunidad'),
        ('Propósito y Significado', 'Propósito y Significado'),
        ('Gratitud y Abundancia', 'Gratitud y Abundancia'),
        ('Reflexión y Renovación', 'Reflexión y Renovación'),
    ]
    
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar en citas, reflexiones o preguntas...',
        }),
        label='Buscar texto'
    )
    
    autor = forms.ChoiceField(
        choices=AUTORES_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Filtrar por autor'
    )
    
    tema = forms.ChoiceField(
        choices=TEMAS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Filtrar por tema'
    )

class ContenidoDiarioAdminForm(forms.ModelForm):
    """
    Formulario para administrar contenido diario (solo admin)
    """
    class Meta:
        model = ContenidoDiario
        fields = '__all__'
        widgets = {
            'dia': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 366,
            }),
            'mes': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'tema': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'cita': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
            }),
            'autor': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'reflexion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
            }),
            'pregunta': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
            }),
        }
    
    def clean_dia(self):
        dia = self.cleaned_data.get('dia')
        if dia and (dia < 1 or dia > 366):
            raise forms.ValidationError('El día debe estar entre 1 y 366.')
        return dia

