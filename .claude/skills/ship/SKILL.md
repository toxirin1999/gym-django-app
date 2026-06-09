---
name: ship
description: Workflow completo de entrega para el proyecto Django gym. Verifica remote git, corre los tests, y si pasan: genera migraciones pendientes, hace commit y push.
---

# Ship

Ejecuta el ciclo completo test → commit → push para este proyecto Django.

## Pasos que sigue siempre

1. **Verificar el remote** — confirma que `origin` apunta al repo correcto en GitHub y hace `git pull` para sincronizar.
2. **Tests** — corre `python3 manage.py test --settings=gymproject.settings_local`. Si falla algún test, para aquí y reporta los fallos. No hace commit.
3. **Migraciones** — comprueba si hay cambios en modelos sin migrar (`makemigrations --check`). Si las hay, las genera y las incluye en el commit.
4. **Commit** — hace `git add` de los archivos modificados (nunca `.env`, nunca credenciales) y crea un commit con mensaje descriptivo.
5. **Push** — hace `git push origin main`. Confirma que el push fue exitoso leyendo el output de git.
6. **Resumen** — informa: tests pasados, archivos commiteados, hash del commit, resultado del push.

## Cuándo parar y preguntar

- Si hay archivos en staging que parecen credenciales (`.env`, `settings.py` con contraseñas hardcoded).
- Si los tests fallan — nunca commitear código roto.
- Si el push es rechazado por divergencia — no hacer force push, investigar primero.

## Comandos de referencia

```bash
# Verificar remote
git remote -v
git status

# Tests
python3 manage.py test --settings=gymproject.settings_local

# Migraciones
python3 manage.py makemigrations --check --settings=gymproject.settings_local
python3 manage.py makemigrations --settings=gymproject.settings_local

# Commit y push
git add <archivos_específicos>
git commit -m "mensaje"
git push origin main
```
