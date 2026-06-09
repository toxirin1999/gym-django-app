---
name: preflight
description: Verificación completa antes de cualquier deploy o sesión de trabajo. Comprueba remote git, dependencias Python, base de datos, migraciones pendientes y estado del repo. Detecta problemas antes de que bloqueen.
---

# Preflight — Verificación Pre-Deploy

Corre esta verificación al inicio de cada sesión importante o antes de cualquier deploy. Detecta los problemas que han bloqueado sesiones anteriores antes de que ocurran.

## Cómo usar

```
/preflight
```

## Checks que ejecuta (en orden)

### 1. Remote git correcto
```bash
git remote -v
git fetch origin --dry-run
```
- Verifica que `origin` apunta a `github.com/toxirin1999/gym-django-app.git`.
- Si apunta a otro sitio: alerta y para. No continuar con remote incorrecto.

### 2. Rama y sincronización
```bash
git status
git log origin/main..HEAD --oneline
git log HEAD..origin/main --oneline
```
- Reporta commits locales sin pushear.
- Reporta commits remotos sin pullear.
- Si hay divergencia: recomienda `git pull` antes de continuar.

### 3. Dependencias Python
```bash
pip3 check
python3 -c "import django; print(django.__version__)"
```
- Verifica que Django y dependencias críticas están instaladas.
- Si falta alguna: sugiere `pip install -r requirements.txt`.

### 4. Base de datos accesible
```bash
python3 manage.py check --database default --settings=gymproject.settings_local
```
- Confirma que la BD SQLite (`db.sqlite333`) está accesible.
- Si no existe o está corrupta: alerta con instrucciones de recuperación.

### 5. Migraciones pendientes
```bash
python3 manage.py showmigrations --settings=gymproject.settings_local | grep "\[ \]"
python3 manage.py makemigrations --check --settings=gymproject.settings_local
```
- Lista migraciones no aplicadas.
- Lista cambios en modelos sin migrar.
- Si hay pendientes: genera y aplica automáticamente (con confirmación).

### 6. Tests base (smoke test)
```bash
python3 manage.py test core clientes --settings=gymproject.settings_local
```
- Corre solo los tests de las apps base para confirmar que el entorno funciona.
- No corre el suite completo (eso lo hace `/ship`).

### 7. Resumen de estado

Al final reporta una tabla:

| Check | Estado |
|---|---|
| Remote git | ✅ / ❌ |
| Sincronización | ✅ / ⚠️ N commits adelante |
| Dependencias | ✅ / ❌ |
| Base de datos | ✅ / ❌ |
| Migraciones | ✅ / ⚠️ N pendientes |
| Tests base | ✅ / ❌ |

Si todo está ✅: "Entorno listo. Puedes trabajar."
Si hay ❌: Para y resuelve antes de continuar.
Si hay ⚠️: Advierte pero permite continuar.

## Cuándo usarlo

- Al inicio de cada sesión de trabajo importante.
- Antes de un deploy a producción (PythonAnywhere).
- Cuando llevas varios días sin tocar el proyecto.
- Si sospechas que el entorno está roto.
