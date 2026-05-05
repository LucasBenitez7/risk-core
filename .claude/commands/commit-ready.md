# Skill: preparar commit

Revisa los cambios actuales y prepara el commit con mensaje bien formado. El agente NUNCA hace el commit automáticamente — solo prepara y espera confirmación. Uso: `/commit-ready`.

## Qué hace este comando

1. Ejecutar `git status` para ver qué cambió
2. Ejecutar `git diff` para revisar los cambios en detalle
3. Agrupar los cambios por tipo lógico (modelo, endpoint, tests, etc.)
4. Para cada grupo, proponer un mensaje de commit en formato Conventional Commits
5. **Preguntar al usuario cuál grupo commitear primero y esperar su respuesta**
6. El usuario decide cuándo y en qué orden se hacen los commits

## Regla absoluta

**El agente NUNCA ejecuta `git commit` ni `git push` sin que el usuario lo confirme explícitamente.**

El flujo correcto es:
1. `/commit-ready` → agente propone mensajes
2. Usuario dice "sí, commitea el primero" o "commitea con este mensaje: ..."
3. Agente ejecuta el commit solo con ese grupo de archivos
4. Repetir para cada grupo

## Formato de propuesta de commits

```
## Cambios detectados

### Grupo 1: Modelos y migraciones
Archivos:
  apps/policies/models.py
  apps/policies/migrations/0001_initial.py

Mensaje propuesto:
  feat(policy): add Customer and Policy models with migrations

### Grupo 2: API y servicios
Archivos:
  apps/policies/serializers.py
  apps/policies/views.py
  apps/policies/services.py
  apps/policies/urls.py

Mensaje propuesto:
  feat(policy): add CustomerViewSet and PolicyViewSet with CRUD endpoints

### Grupo 3: Tests
Archivos:
  apps/policies/tests/test_services.py
  apps/policies/tests/test_views.py

Mensaje propuesto:
  test(policy): add unit and integration tests for policy service

---
¿Qué grupo quieres commitear primero?
```

## Convenciones de mensajes

```
feat(scope):     nueva funcionalidad
fix(scope):      corrección de bug
chore(scope):    mantenimiento, deps, config
test(scope):     añadir o modificar tests
docs(scope):     documentación
refactor(scope): refactor sin cambio de funcionalidad
style(scope):    formato, linting
ci(scope):       CI/CD workflows
```

Scopes válidos: `policy`, `claims`, `notifications`, `audit`, `infra`, `frontend`, `gateway`, `api`

El mensaje debe estar en **inglés**, en modo imperativo presente: "add X", "fix Y", no "added X" ni "adding X".
