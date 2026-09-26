# Dashboard silencioso — pack de implementación

Vista previa: `clientes:dashboard_silencioso_preview` (`/clientes/mockup-dashboard-silencioso/`).

La propuesta no elimina paneles ni datos. Cambia su jerarquía: la portada responde
primero qué conviene hacer ahora y convierte el resto en lugares a los que entrar
cuando el usuario decide profundizar.

## Contrato de la portada

La pantalla inicial tiene únicamente:

1. Una decisión soberana y, si procede, una CTA.
2. Un estado semanal compacto: energía, sueño y carga.
3. Un solo aprendizaje que el plan usa para orientar la continuidad.
4. Navegación explícita a los paneles profundos.

La vista es estrictamente de lectura. Reutiliza `_get_dashboard_context_data()` y
la decisión ya calculada por el sistema; no recalcula el plan ni cambia datos.

## Qué ocurre con los paneles actuales

| Panel existente | En la portada silenciosa | Destino / intención |
| --- | --- | --- |
| Hoy / decisión Gym-Hyrox | Permanece, condensado en la decisión soberana | CTA a briefing o recuperación; el detalle vive en Plan/Hyrox |
| Check-in y biometría | Solo el último estado de energía y sueño | Check-in sigue siendo la acción cuando sea necesario |
| Entrenamiento activo | No se duplica | **Entrenamiento** abre el briefing y desde ahí la ejecución |
| Calendario, contrato y trayectoria | No se expanden | **Plan** abre el plan anual: explicación y continuidad |
| ACWR, carga, alertas y tendencias | Una lectura humana de carga | Métricas y gráficas siguen en sus vistas de detalle |
| Resumen semanal, PRs y decisiones | Un solo aprendizaje dominante | El historial completo se conserva en los módulos de entreno y Plan |
| Memoria del entrenador | No se resume como lista | **Memoria** abre lo que el sistema sabe longitudinalmente |
| Diario, vida, nutrición y estoicismo | No compiten con la sesión | **Vida** abre el Diario; los demás módulos mantienen sus rutas propias |
| JOI | No genera otra tarjeta larga | Su presencia canónica continúa en `/joi/habitacion/` |

## Principios para llevarlo a producción

- Si un dato no cambia la acción de hoy, no aparece expandido por defecto.
- Si el sistema ya decidió, explica esa decisión; no obliga al usuario a
  reconstruirla desde gráficos o tarjetas repetidas.
- Una señal o aprendizaje por carga visual. Los detalles son enlaces, no ruido.
- La portada no se convierte en otro motor de decisiones: consume autoridades
  existentes y tiene degradación segura si no están disponibles.

## Validación

Ejecutar:

```bash
python3 manage.py test clientes.tests_dashboard_silencioso --settings=gymproject.settings_local
```
