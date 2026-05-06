# Skill: checklist de fase

Muestra el estado actual de la fase de desarrollo y qué falta por completar. Uso: `/phase-checklist [número de fase]`.

Ejemplo: `/phase-checklist 1`

## Qué hacer con este comando

1. Leer `CONTEXT.md` — Sección 4 (Plan detallado) tiene el checklist activo con `[x]` / `[ ]`
2. Leer `docs/PHASES.md` para el checklist detallado de la fase (entregables completos)
3. Para cada ítem, verificar si ya existe en el repositorio:
   - Archivos: usar `ls` o `Glob` para verificar que existen
   - Endpoints: verificar en el código que el ViewSet y URL están implementados
   - Tests: verificar que existen los archivos de test y que pasan con `pytest`
   - Docker: verificar que el servicio está en `docker-compose.yml`
4. Si hay discrepancia entre CONTEXT.md y PHASES.md, **CONTEXT.md manda** (es la fuente de verdad del estado)
5. Mostrar el resumen: ✅ completado / ❌ pendiente / ⚠️ parcial
6. Sugerir cuál es el siguiente ítem más importante a implementar

## Formato de respuesta esperado

```
## Fase [N] — [Nombre]

**Estado general**: X/Y ítems completados ([%]%)

### Completados ✅
- [ítem 1]
- [ítem 2]

### Pendientes ❌
- [ítem 3]
- [ítem 4]

### Parciales ⚠️
- [ítem 5] — falta: [qué falta]

### Siguiente paso recomendado
[Descripción del siguiente ítem a implementar y por qué]
```

## Fases del proyecto (referencia rápida)

| Fase | Nombre | Rama |
|---|---|---|
| 0 | Setup e Infraestructura | `feat/phase-0-setup` |
| 1 | policy-service | `feat/phase-1-policy-service` |
| 2 | claims-service | `feat/phase-2-claims-service` |
| 3 | audit-service + notification-service | `feat/phase-3-consumers` |
| 4 | Observabilidad | `feat/phase-4-observability` |
| 5 | Gateway + Rate Limiting | `feat/phase-5-gateway` |
| 6 | Load Testing | `feat/phase-6-load-testing` |
| 7 | Frontend Dashboard | `feat/phase-7-frontend` |
