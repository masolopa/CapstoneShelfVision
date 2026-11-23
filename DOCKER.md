# REGOVA con Docker

Requiere Docker con Compose v2 y un host Linux x86-64 o Docker Desktop en modo Linux. Desde la raíz del proyecto, copia la configuración:

```powershell
Copy-Item .env.docker.example .env.docker
```

Edita `.env.docker` y define las tres contraseñas. La de `ADM-001` debe tener al menos 10 caracteres. `REGOVA_CHECKPOINT` apunta al `best.pt` entrenado presente en esta copia. Si mueves el proyecto sin los datos, lleva ese archivo por separado y actualiza la ruta. Usa únicamente pesos de una fuente en la que confíes.

```powershell
docker compose --env-file .env.docker build app
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker ps -a
Invoke-RestMethod http://localhost:8011/api/ready
```

Abre **http://localhost:8011** e inicia sesión con `ADM-001` y `REGOVA_ADMIN_PASSWORD`. Prueba un análisis YOLO con una foto de góndola. El contenedor `setup` debe salir con código 0 y `app` debe quedar saludable.

Compose crea una base PostgreSQL nueva y guarda los datos, evidencias y pesos registrados en volúmenes persistentes. La base, las copias y el historial de la instalación Windows se conservan en su ubicación original. La recuperación por correo requiere configurar las variables `REGOVA_SMTP_*` en `.env.docker`.

Para detener los servicios conservando los volúmenes:

```powershell
docker compose --env-file .env.docker down
```

Si un servicio falla, consulta `docker compose --env-file .env.docker logs setup app db`.
