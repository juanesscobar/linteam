# Modelo de seguridad

## Identidad y sesión

Producción usará OIDC/OAuth 2.1 con Authorization Code + PKCE. En web se
prefiere cookie `HttpOnly`, `Secure`, `SameSite=Lax`, sesión corta y rotación de
refresh token. La identidad temporal por headers sólo existe en desarrollo y
debe fallar al arrancar fuera de ese entorno.

## Autorización

Cada solicitud produce un `ActorContext` con usuario, organización, roles y
permisos. La presentación autentica; el caso de uso autoriza; el repositorio
aplica otra vez el alcance del tenant. Los permisos siguen el formato
`recurso.acción` y pueden limitarse por pertenencia, departamento o asignación.
Ser administrador de una organización no otorga acceso a otra.

## Controles

- Validación estricta y límites de tamaño en el borde.
- Rate limiting por identidad/IP y cuotas específicas para webhooks.
- Cifrado TLS en tránsito y cifrado administrado en disco/objetos.
- Secretos fuera del repositorio, rotables y separados por ambiente.
- Descargas mediante autorización y URLs firmadas breves.
- Webhooks con firma, timestamp, replay protection e idempotency key.
- Logs estructurados con request ID y redacción de tokens/PII.
- Auditoría append-only de actor, origen, acción, before/after seguro e IP.
- Agentes con herramientas allowlist, permisos efectivos del solicitante,
  propuestas revisables y aprobación humana para acciones de impacto.

## Amenazas prioritarias

IDOR entre organizaciones, escalada de privilegios, archivos maliciosos,
repetición de webhooks, inyección en integraciones/prompts y filtración en logs.
Las pruebas de autorización negativa son obligatorias en cada endpoint.

