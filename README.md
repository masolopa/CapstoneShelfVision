# REGOVA | Análisis de disponibilidad en góndolas

REGOVA analiza fotografías de góndolas para estimar la disponibilidad visible, identificar espacios vacíos y generar alertas de reposición. La aplicación permite marcar la región de estantes, consultar la evidencia visual y revisar el historial de análisis de un local. La medición corresponde a lo visible en la fotografía.

## Estructura

| Ruta | Contenido |
| --- | --- |
| `src/`, `public/` | Interfaz React con TypeScript y recursos de la aplicación |
| `backend/app/` | API FastAPI, procesamiento de imágenes, disponibilidad y persistencia |
| `backend/training/` | Preparación de datos, entrenamiento e inferencia YOLO |
| `backend/migrations/` | Esquema y migraciones PostgreSQL |
| `backend/tests/`, `src/test/` | Pruebas del backend y de la interfaz |
| `docs/` | Documentación técnica del análisis |

## Algoritmos

- **OpenCV.** Usa textura local, saturación y exposición para estimar ocupación y vacío por píxel.
- **YOLO.** Detecta productos y espacios vacíos. El posprocesamiento filtra detecciones por región, solapamiento y tamaño. También estima filas, huecos y frentes en los modos aplicables.
- **Disponibilidad y alertas.** La disponibilidad superficial se calcula como el porcentaje ocupado del área evaluable. El sistema devuelve la clasificación, la base de cálculo y una imagen con las marcas del análisis.

La [documentación de diseño](docs/diseno.md) explica el frontend y el backend. El [detalle de los algoritmos](docs/algoritmos.md) describe los modos y los umbrales. La [documentación de datos y entrenamiento](docs/datos-y-entrenamiento.md) identifica las fuentes, el checkpoint y sus métricas de evaluación.

## Instalación y ejecución

Se requiere Docker con Compose v2 y contenedores Linux x86-64. El repositorio incluye el checkpoint entrenado en `backend/data/training/yolo_runs/segundo_60_extra10_20261112/weights/best.pt`. Docker Compose lo monta desde esa ruta durante la inicialización.

Desde la raíz del repositorio, copia `.env.docker.example` a `.env.docker` (`Copy-Item .env.docker.example .env.docker` en PowerShell o `cp .env.docker.example .env.docker` en Bash). Define contraseñas distintas en `POSTGRES_PASSWORD`, `REGOVA_DB_PASSWORD` y `REGOVA_ADMIN_PASSWORD`. La contraseña de administración debe tener al menos 10 caracteres. El valor `REGOVA_CHECKPOINT` de la plantilla apunta al checkpoint incluido.

```sh
docker compose --env-file .env.docker build app
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker ps -a
curl --fail http://localhost:8011/api/ready
```

El servicio `setup` debe terminar con código 0 y `app` debe quedar saludable. Abre [REGOVA](http://localhost:8011) e inicia sesión con `ADM-001` y la contraseña configurada. En el formulario de análisis, carga una fotografía de góndola, indica el pasillo, delimita la región de estantes y ejecuta el análisis. El contrato HTTP está disponible en [Swagger](http://localhost:8011/api/docs).

Para detener los servicios conservando los volúmenes, ejecuta `docker compose --env-file .env.docker down`. Los registros de arranque se consultan con `docker compose --env-file .env.docker logs setup app db`.

## Instalación nativa en Windows

Los [ejecutables de Windows](ejecutables/README.md) permiten preparar e iniciar REGOVA con Python y PostgreSQL. Las [herramientas](herramientas/README.md) cubren desarrollo y mantenimiento. El [manual de Docker](Manual_de_instalacion_REGOVA.md) detalla el arranque con contenedores.

## Pruebas

Con Node.js 24, ejecuta `npm ci` y `npm test` desde la raíz. Para comprobar la compilación, ejecuta `npm run build`.

Con Python 3.13, crea y activa un entorno virtual. Desde `backend/`, ejecuta:

```sh
python -m pip install -r requirements-app.lock.txt -r requirements-dev.txt
python -m pytest -q
```

Las pruebas de integración requieren `REGOVA_TEST_DSN` apuntando a una base PostgreSQL desechable cuyo nombre termine en `_TEST`. La suite limpia tablas de esa base. Las pruebas unitarias de visión se pueden ejecutar sin PostgreSQL ni el archivo de pesos.




