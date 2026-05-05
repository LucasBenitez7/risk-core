# Skill: próximo paso

Analiza el estado actual del proyecto y recomienda exactamente qué implementar ahora. Sin argumentos. Uso: `/next-step`.

## Qué hacer con este comando

1. Leer `PHASES.md` para ver las fases y sus checklists
2. Leer la estructura actual del repositorio (`Glob` en el root)
3. Determinar en qué fase estamos y qué falta
4. Recomendar el próximo ítem concreto con instrucciones de implementación

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
