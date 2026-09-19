Prepare LINTEAM for deployment on an existing Dokploy server.

IMPORTANT:
- Do not modify the existing compose.yaml used by the current Hetzner deployment.
- Create a new file at the repository root:

compose.dokploy.yaml

Dokploy already provides its own reverse proxy and domain/HTTPS management,
so this deployment MUST NOT run Caddy.

The Dokploy compose should contain only:

1. db
   - postgres:17-alpine
   - persistent named volume
   - internal only
   - no public 5432 port
   - healthcheck
   - POSTGRES_DB
   - POSTGRES_USER
   - POSTGRES_PASSWORD from environment

2. app
   - build the existing LINTEAM Dockerfile
   - depend on healthy db
   - expose port 8000 internally
   - do NOT publish 8000 directly to the host unless Dokploy requires it
   - use PostgreSQL through Docker service hostname "db"
   - run Alembic migrations before application startup using the existing
     canonical startup mechanism
   - preserve the existing FastAPI + React production build
   - preserve persistent LINTEAM file storage
   - add/use the existing healthcheck

Use environment variables rather than hardcoded production secrets.

Required production variables should remain compatible with the application,
including as applicable:

POSTGRES_PASSWORD
LINTEAM_SECRET_KEY
LINTEAM_BOOTSTRAP_TOKEN
LINTEAM_WEBHOOK_SECRET
LINTEAM_ENVIRONMENT

Do not put secrets in compose.dokploy.yaml.

Do not add Caddy, Nginx or Traefik to this compose.
Dokploy will handle ingress separately.

Review the existing Dockerfile, compose.yaml, .env.example and Settings
implementation before generating the file so variable names and DATABASE_URL
are exactly compatible with the application.

Also ensure:
- PostgreSQL data survives redeploys.
- uploaded LINTEAM files survive redeploys.
- app cannot start before PostgreSQL is healthy.
- database is not publicly exposed.
- compose config is valid.

Run:

docker compose -f compose.dokploy.yaml config

if Docker is available.

Do not change application/domain behavior.

Commit the new deployment file with a concise commit message and push to
origin/master.

At the end report:
- exact compose file created
- services
- volumes
- app internal port
- required environment variables
- validation performed
- resulting commit SHA
