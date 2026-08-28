# Despliegue en Hetzner

1. Cree un registro DNS `A` para `linteam.online` que apunte a la IPv4 del servidor. Si tiene IPv6, cree tambiÃ©n el registro `AAAA`.
2. Copie `.env.example` a `.env`, complete secretos aleatorios y defina un correo real para `LINTEAM_ACME_EMAIL`.
3. Abra los puertos TCP 80 y 443 en el firewall de Hetzner y en el firewall del servidor. No exponga el puerto 8000.
4. Ejecute `docker compose up --build -d` y compruebe `docker compose ps`.
5. Abra `https://linteam.online/setup` una vez para crear Lin Group y su administrador. DespuÃ©s use `/invite` para sumar miembros.

Caddy obtiene y renueva automÃ¡ticamente el certificado HTTPS. Los datos de PostgreSQL, adjuntos y certificados persisten en volÃºmenes Docker. Para actualizar: `git pull && docker compose up --build -d`.
