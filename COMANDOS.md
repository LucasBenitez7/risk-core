# COMANDOS.md — RiskCore

> Referencia rápida de todos los comandos del proyecto. Actualizar al agregar nuevos targets o herramientas.

---

## Git

### Inicializar el repo

```bash
git init
git remote add origin git@github.com:[usuario]/riskcore.git
git checkout -b main
git checkout -b dev
git checkout -b feat/phase-0-setup
```

### Ramas

```bash
git branch                    # ver rama actual
git checkout -b feat/phase-N-nombre   # crear rama desde la actual
git checkout dev              # cambiar de rama
```

### Commits — Conventional Commits (obligatorio)

```bash
git add policy-service/apps/policies/services.py
git commit -m "feat(policy): add policy creation with Kafka event emission"

# Scopes validos: policy, claims, notifications, audit, infra, frontend, gateway, api
# Tipos validos: feat, fix, chore, test, docs, refactor
```

### Pull Requests

```bash
# PR de una fase (feat/phase-N) hacia dev
gh pr create --base dev --head feat/phase-0-setup --title "Phase 0: Setup e Infraestructura"
```

### Tags de release

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Makefile

> Ejecutar desde la raiz del monorepo.

```bash
make dev              # levanta todo el stack (Docker Compose)
make infra            # solo Kafka + Redis + PostgreSQL + Grafana
make test s=policy    # tests de un servicio especifico
make lint             # ruff + mypy en todos los servicios
make kafka-setup      # crear los 6 topics de Kafka
make logs s=claims    # logs de un servicio especifico
make shell s=audit    # Django shell de un servicio
```

---

## uv — Python Package Manager

> Ejecutar dentro de cada servicio (ej: `policy-service/`).

```bash
uv sync                    # instalar dependencias del pyproject.toml
uv add django==5.2.x       # añadir una dependencia y actualizar uv.lock
uv add --dev pytest        # añadir dependencia de desarrollo
uv lock                    # regenerar uv.lock sin instalar
uv run python manage.py migrate       # correr migraciones
uv run python manage.py shell         # Django shell
uv run python manage.py runserver     # levantar servidor dev (sin Docker)
uv run pytest                         # correr tests
uv run ruff check .                   # linting
uv run ruff format .                  # formatear
uv run mypy .                         # type check
uv run bandit -c pyproject.toml -r .  # security scan
```

### Crear un nuevo servicio

```bash
# En la raiz del monorepo
mkdir [servicio]
cd [servicio]
uv init --python 3.13
uv add django==5.2.* djangorestframework==3.15.* psycopg[binary]==3.3.*
uv add --dev pytest pytest-django factory-boy ruff mypy django-stubs
```

---

## Docker Compose

```bash
docker compose -f infra/docker-compose.yml up -d                    # levantar todo en background
docker compose down                      # bajar todo
docker compose down -v                   # bajar todo + eliminar volumenes (DBs)
docker compose logs -f [servicio]        # logs de un servicio en tiempo real
docker compose logs --tail=100 [servicio]
docker compose restart [servicio]        # reiniciar un servicio
docker compose build --no-cache [servicio]  # rebuild sin cache
docker compose exec [servicio] bash      # shell dentro del contenedor
docker compose ps                        # estado de los contenedores
docker compose up -d --scale web=3      # escalar replicas (si aplica)
```

---

## Kafka CLI

> Todos los comandos se ejecutan dentro del contenedor kafka.

### Listar topics

```bash
docker exec -it kafka kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Crear un topic

```bash
docker exec -it kafka kafka-topics.sh --create \
  --topic policy.created \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --bootstrap-server localhost:9092
```

### Describir un topic

```bash
docker exec -it kafka kafka-topics.sh --describe \
  --topic policy.created \
  --bootstrap-server localhost:9092
```

### Consumir mensajes

```bash
# Desde el ultimo mensaje
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic policy.created

# Desde el principio
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic policy.created \
  --from-beginning

# Con consumer group
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic policy.created \
  --group debug-consumer \
  --from-beginning
```

### Ver consumer groups

```bash
docker exec -it kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list

docker exec -it kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group audit-consumers
```

### Script de creacion de topics (6 topics)

```bash
make kafka-setup
# o manualmente:
bash infra/kafka/create-topics.sh
```

---

## Pre-commit

```bash
pre-commit install                        # instalar hooks (una vez)
pre-commit install --hook-type commit-msg # validar conventional commits

pre-commit run --all-files                # correr todos los hooks manualmente
pre-commit run ruff --all-files           # solo ruff
pre-commit run detect-secrets --all-files # solo detect-secrets

# Validar un mensaje de commit manualmente
echo "feat(policy): add cancellation endpoint" | pre-commit run commitizen --hook-stage commit-msg
```

---

## Testing

### pytest — Unitarios e Integracion

```bash
# Dentro de un servicio (usando uv)
uv run pytest                                    # todos los tests
uv run pytest apps/policies/tests/               # tests de un modulo
uv run pytest -k "test_create_policy"            # test especifico por nombre
uv run pytest -v                                 # verbose
uv run pytest --cov=apps --cov-report=term       # coverage en terminal
uv run pytest --cov=apps --cov-report=html       # coverage report HTML
```

### pytest con DB real

```bash
uv run pytest -m "django_db"                     # solo tests con DB
uv run pytest --reuse-db                         # reusar DB entre tests (mas rapido)
uv run pytest --create-db                        # forzar recrear DB de test
```

### Mockear en tests unitarios

```python
from unittest.mock import patch

# Kafka producer
with patch("apps.policies.events.PolicyEventProducer.produce_policy_created") as m:
    ...

# HTTP inter-service
with patch("apps.claims.clients.PolicyServiceClient.verify_policy") as m:
    m.return_value = {"status": "ACTIVE", "is_valid": True}

# Email
with patch("django.core.mail.send_mail") as m:
    ...
```

### locust — Load Testing

```bash
cd infra/load-testing
locust -f scenario_1_policy_creation.py --host http://localhost:80
# Abrir http://localhost:8089 para la UI de locust
```

### Frontend — Vitest

```bash
cd frontend
pnpm test                  # todos los tests
pnpm test:watch            # watch mode
pnpm test:coverage         # coverage
```

---

## Lint / Type Check / Security

### Backend — ruff

```bash
# Dentro de un servicio
uv run ruff check .           # solo errores
uv run ruff check . --fix     # auto-fix
uv run ruff format .          # formatear
uv run ruff format . --check  # verificar sin escribir
```

### Backend — mypy

```bash
uv run mypy .                                    # type check completo
uv run mypy apps/policies/services.py            # archivo especifico
uv run mypy --ignore-missing-imports .           # ignorar imports faltantes
```

### Backend — bandit (security)

```bash
uv run bandit -c pyproject.toml -r .
```

### Backend — detect-secrets

```bash
# Generar baseline inicial (una vez)
detect-secrets scan > .secrets.baseline

# Auditar baseline
detect-secrets audit .secrets.baseline

# Escanear sin baseline
detect-secrets scan
```

### Frontend — ESLint + Prettier

```bash
cd frontend
pnpm lint              # ESLint check
pnpm lint:fix          # ESLint auto-fix
pnpm format            # Prettier format
pnpm format:check      # Prettier check
```

---

## Frontend (pnpm)

```bash
cd frontend

pnpm install           # instalar dependencias
pnpm dev               # servidor dev (http://localhost:3001)
pnpm build             # build de produccion
pnpm start             # servir build de produccion
pnpm lint              # ESLint
pnpm format            # Prettier

pnpm add react-hook-form zod       # añadir dependencia
pnpm add -D vitest @testing-library/react  # añadir dev dependency
```

---

## Base de Datos / Migraciones

### Dentro de un servicio (via uv)

```bash
uv run python manage.py makemigrations          # crear migraciones
uv run python manage.py migrate                 # aplicar migraciones
uv run python manage.py showmigrations          # ver estado de migraciones
uv run python manage.py migrate apps 0001       # migrar a una migracion especifica
uv run python manage.py sqlmigrate apps 0001    # ver SQL de una migracion
uv run python manage.py dbshell                 # shell de PostgreSQL
uv run python manage.py flush                   # vaciar todas las tablas
```

### Dentro de un servicio (via Docker)

```bash
docker compose exec policy-web uv run python manage.py migrate
docker compose exec policy-web uv run python manage.py shell
```

---

## Verificacion de Salud

```bash
# Health checks de todos los servicios
curl http://localhost:8001/health/   # policy-service
curl http://localhost:8002/health/   # claims-service
curl http://localhost:8003/health/   # notification-service
curl http://localhost:8004/health/   # audit-service

# Verificar topics Kafka
docker exec -it kafka kafka-topics.sh --list --bootstrap-server localhost:9092
# Debe mostrar: policy.created, policy.updated, policy.cancelled, claim.filed, claim.status_changed, claim.resolved

# Grafana
# Abrir http://localhost:3000 (admin/admin)

# Flower (Celery monitor)
# Abrir http://localhost:5555
```

---

## Puertos Locales

| Servicio | Puerto |
|---|---|
| policy-service | 8001 |
| claims-service | 8002 |
| notification-service | 8003 |
| audit-service | 8004 |
| Grafana | 3000 |
| Flower | 5555 |
| Frontend | 3001 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Kafka | 9092 |

---

## Variables de Entorno

Copia el `.env.example` de cada servicio a `.env` antes de empezar:

```bash
cp policy-service/.env.example policy-service/.env
cp claims-service/.env.example claims-service/.env
cp notification-service/.env.example notification-service/.env
cp audit-service/.env.example audit-service/.env
cp frontend/.env.local.example frontend/.env.local
```
