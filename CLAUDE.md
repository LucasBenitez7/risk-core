# CLAUDE.md

> Este archivo lo lee Claude Code automáticamente al iniciar sesión.
> Las reglas del proyecto viven en otro lado.

## Lee primero, en este orden

1. **`CONTEXT.md`** — estado actual, fase activa, plan con checkboxes, reglas críticas de la fase. **SIEMPRE primero.**
2. **`AGENTS.md`** — reglas permanentes del proyecto, stack, patrones, formas de trabajo, "lo que NUNCA hacer", workflow Git, formato de PR.

`AGENTS.md` es la fuente de verdad de las reglas. Este archivo es solo el punto de entrada para Claude Code (sigue la convención open de [agents.md](https://agents.md)).

## Reglas mínimas que no podés saltarte (resumen — el detalle está en `AGENTS.md`)

- **NUNCA** `git commit` o `git push` sin permiso explícito del usuario
- Lógica de negocio en `services.py`, nunca en `views.py`
- `confluent-kafka` nunca `kafka-python` · `uv` nunca `pip` · `Ruff` nunca `flake8`/`black` · `pnpm` nunca `npm`/`yarn`
- Self-audit obligatorio antes del paso de tests (ver §"Self-Audit" en AGENTS.md)
- PR título y descripción siempre en **inglés**, formato listo para copy-paste a GitHub (ver §"Pull Requests" en AGENTS.md)

## Para todo lo demás → `AGENTS.md`
