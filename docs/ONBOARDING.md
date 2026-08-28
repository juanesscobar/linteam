# Puesta en marcha de Lin Group

## Primer administrador

Antes de desplegar, defina secretos propios en `.env`:

```dotenv
LINTEAM_BOOTSTRAP_TOKEN=<token-aleatorio-largo>
LINTEAM_SECRET_KEY=<secreto-aleatorio-largo>
LINTEAM_WEBHOOK_SECRET=<secreto-aleatorio-largo>
```

En desarrollo Docker, si no existe `.env`, el bootstrap token es `local-bootstrap-token`. Ese valor no debe usarse en Hetzner.

Abra `/setup` una sola vez y cree la organización `Lin Group`. El código público predeterminado es `LINTEAM`; no es un UUID y puede comunicarse a los empleados.

## Incorporar miembros

1. El administrador inicia sesión.
2. Abre `/invite` y genera una invitación para el correo del miembro.
3. Comparte el código `LINTEAM` y el token de invitación por un canal seguro.
4. El miembro abre `/join`, completa sus datos y crea la contraseña.
5. La invitación queda consumida y el miembro puede iniciar sesión normalmente con correo y contraseña.

Una invitación está ligada al correo, vence como máximo en 30 días y no puede reutilizarse. El código de empresa por sí solo nunca concede acceso.
