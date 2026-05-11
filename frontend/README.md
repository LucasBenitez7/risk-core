# RiskCore — Frontend Dashboard

Dashboard Next.js 15 (App Router) que muestra el estado del sistema en tiempo real, conectado al gateway via REST + WebSocket.

## Setup local

```bash
pnpm install
cp .env.local.example .env.local
pnpm dev          # http://localhost:3001
```

Asegurate de que el stack backend esté corriendo (`make dev` desde la raíz) antes de usar el dashboard.

## Estructura de carpetas

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout (html, fonts, Toaster)
│   ├── (dashboard)/
│   │   ├── layout.tsx          # Sidebar + topbar + auth gate
│   │   ├── page.tsx            # Overview dashboard
│   │   ├── policies/           # Pólizas CRUD
│   │   ├── claims/             # Siniestros + state machine
│   │   ├── events/             # Live event feed (WebSocket)
│   │   └── audit/              # Audit log (cursor pagination)
│   ├── login/page.tsx          # Login form
│   └── api/
│       ├── proxy/[...path]/    # Proxy server-to-server al gateway
│       └── auth/               # Login, logout, ws-token (cookies httpOnly)
├── components/
│   ├── ui/                     # MetricCard, StatusBadge, etc.
│   ├── policies/               # PoliciesTable, PolicyFilters
│   ├── claims/                 # ClaimsTable, StatusTransition
│   └── events/                 # EventFeed, LiveEventsView
├── lib/
│   ├── api/                    # API client + Zod schemas + service clients
│   ├── ws/                     # WebSocket client (reconnect, heartbeat)
│   ├── hooks/                  # useAuth, useEventStream
│   └── stores/                 # Zustand: auth, events
├── __tests__/                  # Vitest unit + component tests
├── Dockerfile                  # Multi-stage standalone build
├── next.config.ts              # Next.js config (standalone via env var)
└── package.json                # pnpm scripts + dependencies
```

## Integración con el gateway

- **REST**: todas las peticiones API van por el proxy interno de Next.js (`/api/proxy/[...path]`), que reenvía al gateway (`http://gateway:8080`). Server-to-server, sin CORS.
- **WebSocket**: el browser conecta directo a `ws://localhost:8080/ws/events/?token=<jwt>`. El token se obtiene via `/api/auth/ws-token` que lo lee de la cookie httpOnly.
- **Auth**: login → `/api/auth/login` → el backend responde con JWT → Next.js lo guarda en cookies httpOnly (`access_token`, `refresh_token`). El middleware Next.js protege rutas chequeando la presencia de la cookie.

## Comandos

| Comando       | Descripción                           |
| ------------- | ------------------------------------- |
| `pnpm dev`    | Dev server en `http://localhost:3001` |
| `pnpm build`  | Build de producción                   |
| `pnpm start`  | Arranca el build de producción        |
| `pnpm test`   | Unit + component tests (Vitest)       |
| `pnpm lint`   | ESLint                                |
| `pnpm format` | Prettier                              |

Desde la raíz del monorepo:

```bash
make frontend-dev       # pnpm dev
make frontend-test      # pnpm test
make frontend-lint       # lint + format check
```

## Docker

```bash
# Build
docker compose -f infra/docker-compose.yml build frontend

# Run (con el stack completo)
make dev
```

El Dockerfile usa build multi-stage con `NEXT_OUTPUT_STANDALONE=1` (opt-in via env var). La imagen final solo contiene `.next/standalone/`, `.next/static/`, y `public/`.

## Testing

### Unit tests (Vitest)

```bash
pnpm test
```

Testea el API client, stores de Zustand, WebSocket client, y componentes UI. Mockea `fetch` y `WebSocket`.
