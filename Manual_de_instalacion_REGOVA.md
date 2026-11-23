# Manual de instalación de REGOVA con Docker

## 1. Requisitos

- Windows de 64 bits con Docker Desktop abierto y configurado para usar contenedores Linux.
- Conexión a internet para descargar las imágenes y dependencias durante la primera compilación.
- Una copia del proyecto con `Dockerfile`, `compose.yaml`, `.env.docker.example` y los pesos de YOLO en un archivo `best.pt`.

Docker instala las dependencias de React, FastAPI, PostgreSQL y YOLO. El análisis se ejecuta en CPU.

## 2. Configurar la instalación

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
docker version
docker compose version
```

Comprueba que `docker version` muestre la sección `Server` con el sistema `linux/amd64`.

Crea la configuración local a partir del ejemplo y ábrela para editarla:

```powershell
if (-not (Test-Path .env.docker)) {
    Copy-Item .env.docker.example .env.docker
}
notepad .env.docker
```

| Variable | Valor |
| --- | --- |
| `POSTGRES_PASSWORD` | Contraseña del administrador de PostgreSQL. |
| `REGOVA_DB_PASSWORD` | Contraseña que usa la aplicación para conectarse a PostgreSQL. |
| `REGOVA_ADMIN_PASSWORD` | Contraseña inicial de `ADM-001`. Debe tener al menos 10 caracteres. |
| `REGOVA_CHECKPOINT` | Ruta a los pesos de YOLO. Si usas la copia de Descargas, conserva la ruta del ejemplo. Si recibiste `best.pt` por separado, indica dónde lo guardaste. |

Usa tres contraseñas distintas. Si una contiene `$` o `#`, ponla entre comillas simples. Guarda con **Ctrl+S** y mantén `.env.docker` fuera del repositorio.

## 3. Compilar y arrancar

Desde la raíz del proyecto, construye la imagen:

```powershell
docker compose --env-file .env.docker build app
```

Una vez completada la compilación, inicia los servicios:

```powershell
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker ps -a
Invoke-RestMethod http://localhost:8011/api/ready
```

En el primer arranque, Compose crea una base PostgreSQL nueva. El servicio `setup` aplica las migraciones, crea el usuario `ADM-001` y registra los pesos del modelo. La base de datos, los pesos registrados y las evidencias se guardan en volúmenes de Docker.

## 4. Verificar la instalación

1. Comprueba que `db` figure como `healthy` y `setup` termine con `Exited (0)`. Si `app` aparece como `health: starting`, espera unos segundos y vuelve a ejecutar `docker compose --env-file .env.docker ps -a`.
2. Comprueba que `/api/ready` devuelva `status: ready` y `database: postgresql`.
3. Abre [REGOVA](http://localhost:8011) e inicia sesión como `ADM-001` con la contraseña de `REGOVA_ADMIN_PASSWORD`.
4. Analiza una foto de góndola con YOLO, indica el pasillo y comprueba que el resultado aparezca en el historial. Esto verifica la inferencia y el guardado dentro de Docker.

## 5. Detener y volver a iniciar

Para detener los servicios y conservar la base y los archivos, ejecuta:

```powershell
docker compose --env-file .env.docker down
```

Para volver a iniciarlos, ejecuta:

```powershell
docker compose --env-file .env.docker up -d
```

## 6. Revisar errores de arranque

Consulta los registros de los servicios:

```powershell
docker compose --env-file .env.docker logs --tail 80 setup app db
```

Si `setup` falla al localizar los pesos, comprueba que `REGOVA_CHECKPOINT` apunta a un archivo `best.pt` existente. Si falla la conexión al motor de Docker, abre Docker Desktop y comprueba que `docker version` muestre la sección `Server`.

Para habilitar la recuperación de contraseña por correo, configura las variables `REGOVA_SMTP_*` en `.env.docker`.

