# CONTEXT — RiskCore

> Este archivo es la fuente de verdad del estado actual del proyecto.
> Actualizarlo cada vez que se completa una tarea o cambia de fase.
> Lo leen todos los agentes (Claude Code, Cursor, OpenCode) al inicio de cada sesión.

---

## Estado actual

**Fase**: 1 — policy-service  
**Rama activa**: `feat/phase-1-policy-service`  
**Última tarea completada**: Fase 0 mergeada — monorepo, 4 Django services, Docker Compose, Kafka, pre-commit, CI verdes  
**Próximo paso**: Customer model + API endpoint (list, create, retrieve)  

---

## Progreso por fase

| Fase | Nombre | Estado |
|---|---|---|---|
| 0 | Setup e Infraestructura | ✅ Completado |
| 1 | policy-service | ⏳ En curso |
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
- ✅ Git workflow (main, dev, feat branches)
- ✅ `.gitignore` + `.pre-commit-config.yaml` (ruff, detect-secrets, commitizen)
- ✅ `.secrets.baseline`
- ✅ `COMANDOS.md` + `Makefile` + `README.md`
- ✅ Docker Compose (PostgreSQL 16, Redis 7.2, Kafka 3.7 KRaft)
- ✅ Kafka 6 topics creados
- ✅ 4 Django 5.2 service esqueletos con health `/health/` respondiendo
- ✅ CI workflows (5) pasando en verde
- ✅ PR Phase 0 mergeado a dev
- ❌ Modelos y endpoints de policy-service (en curso)

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
