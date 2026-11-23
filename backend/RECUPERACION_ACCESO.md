# Recuperación de acceso

1. En instalaciones existentes, ejecutar ejecutables/ACTUALIZAR_RECUPERACION.bat con el propietario de PostgreSQL. Agrega únicamente recuperaciones_acceso y permisos; no cambia contraseñas. Las instalaciones nuevas incluyen la migración 003 en ejecutables/PREPARAR_POSTGRESQL.bat.
2. Configurar en backend/.env REGOVA_SMTP_HOST, REGOVA_SMTP_PORT, REGOVA_SMTP_SECURITY (starttls para 587, ssl para 465), REGOVA_SMTP_USER, REGOVA_SMTP_PASSWORD y REGOVA_SMTP_FROM. Utilizar credenciales SMTP o contraseña de aplicación del proveedor. Nunca incluir secretos en el código.
3. Configurar REGOVA_PUBLIC_URL con la dirección de REGOVA accesible desde el equipo que abrirá el correo. 127.0.0.1 solo funciona en el mismo PC. Reiniciar el backend.
4. Registrar correos en Administración de cuentas. ADM-001 puede guardar el suyo en Mi correo de recuperación confirmando su contraseña. Las cuentas existentes sin correo siguen entrando por ID, pero no pueden recuperar acceso por correo hasta registrarlo.
5. Probar con una cuenta y correo propios: solicitar recuperación, recibir ID y enlace, cambiar contraseña y comprobar que el enlace no funciona por segunda vez. Las sesiones anteriores se revocan.

Los enlaces duran 30 minutos. Se almacena solo el hash del token. La respuesta pública no identifica si un correo existe. Se limitan las solicitudes por IP y los envíos repetidos por cuenta. El envío requiere conexión al proveedor SMTP. Un error SMTP no revela si existe la cuenta; revisar la configuración si el mensaje no llega.
