from django import forms
from .models import Programa, Rutina, RutinaEjercicio
from entrenos.models import EjercicioBase


class RutinaEjercicioForm(forms.ModelForm):
    # Ahora el queryset usa el modelo que importamos de 'entrenos'
    ejercicio = forms.ModelChoiceField(
        queryset=EjercicioBase.objects.all().order_by('grupo_muscular', 'nombre'),
        label="Selecciona un ejercicio",
        empty_label="Elige un ejercicio de la lista...",
        widget=forms.Select(attrs={'class': 'form-select'})  # O 'form-control'
    )

    class Meta:
        model = RutinaEjercicio
        fields = ['ejercicio', 'series', 'repeticiones', 'peso_kg']
        widgets = {
            'series': forms.NumberInput(attrs={'class': 'form-control'}),
            'repeticiones': forms.NumberInput(attrs={'class': 'form-control'}),
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ProgramaForm(forms.ModelForm):
    class Meta:
        model = Programa
        fields = ['nombre', 'tipo', 'icono']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Hipertrofia, Fuerza...'}),
            'icono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'piernas.png'}),
        }


class EjercicioForm(forms.ModelForm):
    class Meta:
        model = EjercicioBase
        fields = ['nombre', 'grupo_muscular', 'equipo']


class RutinaForm(forms.ModelForm):
    ejercicios = forms.ModelMultipleChoiceField(
        queryset=EjercicioBase.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Ejercicios disponibles"
    )

    class Meta:
        model = Rutina
        fields = ['nombre', 'ejercicios']
