# Diseño de la aplicación

## Interfaz

La interfaz React y TypeScript organiza la operación por tarea. El flujo de análisis guía la carga de la fotografía, la identificación del pasillo, el trazado de la región de interés y la lectura del resultado. Delimitar los estantes antes de ejecutar reduce la influencia del piso y el techo. El resultado combina porcentajes, advertencias y evidencia visual para que el operador pueda contrastar la cifra con la captura.

El [flujo de análisis](../src/features/analysis/AnalysisFlow.tsx), el [editor de polígonos](../src/features/analysis/PolygonEditor.tsx) y la [vista de resultados](../src/features/analysis/Results.tsx) están separados porque manejan decisiones distintas. El [cliente de la API de análisis](../src/features/analysis/api.ts) concentra el intercambio con el servidor. La [navegación](../src/App.tsx) muestra las tareas permitidas para el rol activo. La API comprueba los permisos en cada operación.

## API y persistencia

[FastAPI](../backend/app/main.py) sirve la interfaz compilada y la API. Las [rutas](../backend/app/api/routes.py) y los [esquemas](../backend/app/api/schemas.py) delimitan el contrato HTTP y validan las entradas. El servicio de análisis coordina la ejecución. La capa de visión recibe la imagen y los parámetros, lo que permite probar el algoritmo con datos sintéticos sin abrir una sesión ni conectarse a PostgreSQL.

[PostgreSQL y sus migraciones](../backend/migrations/) mantienen el historial, las alertas, las revisiones y las referencias a parámetros y modelos. El [almacenamiento local](../backend/app/services/storage.py) guarda los archivos de evidencia. Esta separación deja en la base los datos consultables y sus relaciones, y conserva las fotografías originales como archivos. El servidor registra el original y el estado de procesamiento antes de ejecutar visión. Una vez obtenida la salida, persiste el resultado y la alerta correspondiente. Las revisiones humanas se registran por separado para conservar la trazabilidad de la predicción original.

## Recorrido de una captura

1. La interfaz envía la imagen, el pasillo y los parámetros a `POST /api/analyze`.
2. La API valida la sesión, el rol y los datos. El [servicio de análisis](../backend/app/services/analysis.py) conserva el original y ejecuta la [capa de visión](../backend/app/services/vision.py).
3. El servicio devuelve la disponibilidad, las advertencias y la evidencia visual. El historial permite consultar el resultado. La revisión se registra mediante `POST /api/analyze/{id}/reviews`.

El contrato interactivo se sirve en `/api/docs`. Las rutas `/api/health` y `/api/ready` permiten comprobar el estado del proceso y la disponibilidad de la base.
