from django import forms

from .models import EpisodioRehab, ProtocoloRehab, RegistroDiarioRehab, SesionRehab


class IniciarEpisodioForm(forms.ModelForm):
    class Meta:
        model = EpisodioRehab
        fields = ['protocolo', 'lateralidad', 'fecha_inicio', 'dolor_basal_inicial', 'notas']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['protocolo'].queryset = ProtocoloRehab.objects.filter(activo=True)
        self.fields['notas'].required = False


class RegistroDiarioForm(forms.ModelForm):
    class Meta:
        model = RegistroDiarioRehab
        fields = ['fecha', 'dolor_manana', 'rigidez_manana', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notas'].required = False


class RegistrarSesionForm(forms.ModelForm):
    class Meta:
        model = SesionRehab
        fields = ['fecha', 'estado', 'dolor_durante', 'dolor_post_24h', 'duracion_min', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dolor_post_24h'].required = False
        self.fields['duracion_min'].required = False
        self.fields['notas'].required = False
