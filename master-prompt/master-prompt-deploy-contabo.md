Estamos corrigiendo el deployment de LINTEAM en Dokploy/Contabo.

Contexto actual:
- Repo correcto: https://github.com/juanesscobar/linteam
- Branch: master
- Compose usado por Dokploy: ./compose.dokploy.yaml
- El deployment anterior falló por YAML inválido en el healthcheck del servicio app.
- Error de Dokploy:
  "Nested mappings are not allowed in compact mappings at line 50, column 12: retries: 12"
- La aplicación en sí funciona.
- PostgreSQL ya fue restaurado correctamente.
- La DB está en Alembic head: c1d4e8f9a201
- Datos confirmados: 7 users y 13 work_items.
- El endpoint /ready responde correctamente si recibe:
  Host: linteam.linteam.online
- El problema original era que Docker healthcheck llamaba:
  http://127.0.0.1:8000/ready
  sin el Host permitido, por lo que devolvía HTTP 400.
- No debemos tocar, borrar, recrear ni resetear la base de datos.
- No debemos modificar volúmenes persistentes.
- No debemos cambiar secrets.
- No debemos aflojar LINTEAM_TRUSTED_HOSTS a "*".
- No debemos publicar PostgreSQL 5432 ni FastAPI 8000 al host.
- Dokploy/Traefik maneja el acceso público.

Tu tarea:

1. Inspecciona `compose.dokploy.yaml`.

2. Corrige únicamente lo necesario en el healthcheck del servicio `app` para que:
   - el YAML sea 100% válido;
   - siga usando Python/urllib.request;
   - haga GET a:
     http://127.0.0.1:8000/ready
   - envíe el header:
     Host: linteam.linteam.online
   - conserve:
     interval: 10s
     timeout: 3s
     retries: 12

3. Preferí una sintaxis YAML simple y robusta. Esta forma es válida como referencia:

   healthcheck:
     test: ["CMD", "python", "-c", "import urllib.request; r=urllib.request.Request('http://127.0.0.1:8000/ready', headers={'Host':'linteam.linteam.online'}); urllib.request.urlopen(r)"]
     interval: 10s
     timeout: 3s
     retries: 12

4. No cambies el healthcheck de `db` salvo que detectes un error real.

5. No cambies:
   - nombres de servicios;
   - volúmenes;
   - variables de entorno;
   - database URL;
   - puertos;
   - expose;
   - restart policy;
   - Dockerfile;
   - código de aplicación;
   - migraciones Alembic;
   - configuración de producción.

6. Validá obligatoriamente:

   docker compose -f compose.dokploy.yaml config

   Si falla, corregí hasta que pase.

7. Ejecutá también:

   git diff --check

8. Mostrame el diff final de `compose.dokploy.yaml`.

9. Si ambas validaciones pasan, crea un commit:

   git add compose.dokploy.yaml
   git commit -m "fix: valid dokploy healthcheck"

10. Hacé push a:

   origin master

11. Al final devolveme un reporte breve con:
   - qué cambiaste;
   - resultado de `docker compose ... config`;
   - resultado de `git diff --check`;
   - hash del commit;
   - confirmación del push;
   - cualquier advertencia relevante.

Restricciones críticas:
- NO hacer `git push --force`.
- NO hacer reset --hard.
- NO tocar `linteam.db`.
- NO agregar archivos markdown/untracked.
- NO tocar la DB de producción.
- NO ejecutar comandos destructivos de Docker/PostgreSQL.
- NO hacer redeploy desde Dokploy; solo dejar GitHub listo.
- Si hay cambios locales ajenos a esta tarea, preservalos y no los incluyas en el commit.
