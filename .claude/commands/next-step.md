# Skill: próximo paso

Analiza el estado actual del proyecto y recomienda exactamente qué implementar ahora. Sin argumentos. Uso: `/next-step`.

## Qué hacer con este comando

1. Leer `CONTEXT.md` — Sección 3 (Estado actual) y Sección 4 (Plan detallado) son la fuente de verdad
2. Si el plan en CONTEXT.md no tiene suficiente detalle, consultar `docs/PHASES.md` como referencia secundaria
3. Leer la estructura actual del repositorio (`Glob` en el root) para verificar qué existe
4. Determinar qué falta según el plan activo y recomendar el próximo ítem concreto

## Formato de respuesta

```
## Estado actual
Fase [N] — [Nombre] | [X/Y ítems completados]

## Próximo paso: [nombre del ítem]

**Por qué este primero**: [razón — dependencias, orden lógico, etc.]

**Cómo implementarlo**:
1. [paso 1 concreto]
2. [paso 2 concreto]
3. ...

**Archivos a crear/modificar**:
- `[ruta/archivo.py]` — [qué cambiar]

**Verificación**:
```bash
[comandos para verificar que está hecho]
```

**Cuando esté listo, el siguiente paso será**: [próximo ítem]
```
