# CONTEXT — RiskCore

> Este archivo es la fuente de verdad del estado actual del proyecto.
> Actualizarlo cada vez que se completa una tarea o cambia de fase.
> Lo leen todos los agentes (Claude Code, Cursor, OpenCode) al inicio de cada sesión.

---

## Estado actual

**Fase**: 0 — Setup e Infraestructura  
**Rama activa**: `feat/phase-0-setup`  
**Última tarea completada**: Git init, primer commit, ramas (main/dev/feat/phase-0-setup), .gitignore, COMANDOS.md  
**Próximo paso**: Crear `.pre-commit-config.yaml` y estructura de carpetas del monorepo  

---

## Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|
| 0 | Setup e Infraestructura | ⏳ En curso |
| 1 | policy-service | ❌ No iniciado |
| 2 | claims-service | ❌ No iniciado |
| 3 | audit-service + notification-service | ❌ No iniciado |
| 4 | Observabilidad | ❌ No iniciado |
| 5 | Gateway + Rate Limiting | ❌ No iniciado |
| 6 | Load Testing | ❌ No iniciado |
| 7 | Frontend Dashboard | ❌ No iniciado |

---

## Qué está funcionando

- ✅ Documentación base (`docs/`)
- ✅ Instrucciones para agentes (CLAUDE.md, .cursor/rules, .clinerules)
- ✅ Slash commands (`.claude/commands/`)
- ✅ Skills instalados (`.agents/skills/`)
- ✅ Git init, ramas (main, dev, feat/phase-0-setup)
- ✅ `.gitignore`
- ✅ `COMANDOS.md`
- ✅ Primer commit (`chore(infra): initial project setup with documentation and agent configs`)
- ❌ `.pre-commit-config.yaml`
- ❌ Código del proyecto (no iniciado aún)
- ❌ Docker Compose / infraestructura
- ❌ Servicios Django
- ❌ Frontend

---

## Decisiones tomadas recientemente

_Anotar aquí cualquier decisión importante que no esté en TECHNICAL_DECISIONS.md todavía._

---

## Bloqueos o pendientes importantes

_Ninguno por ahora._

---

## Cómo actualizar este archivo

Al terminar cada tarea significativa, actualizar:
1. `Última tarea completada`
2. `Próximo paso`
3. El estado en la tabla (⏳ En curso / ✅ Completado / ❌ No iniciado)
4. Mover ítems en "Qué está funcionando"

No hace falta actualizar en cada commit — solo cuando cambia algo relevante de contexto.
