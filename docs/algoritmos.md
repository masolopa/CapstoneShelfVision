# Procesamiento de imágenes y disponibilidad

## Flujo de análisis

La interfaz envía la fotografía y los polígonos normalizados de la región de interés, las exclusiones y la estructura de la góndola. La API valida la solicitud. El preprocesamiento decodifica la imagen con OpenCV, prepara la entrada y mide nitidez y brillo para emitir advertencias de calidad. El servicio de análisis guarda la fotografía original y registra la configuración y la versión del modelo asociadas al resultado.

## Métodos

| Método | Implementación y salida |
| --- | --- |
| Heurística OpenCV | La desviación estándar local en escala de grises y la saturación HSV generan evidencia de ocupación. Los píxeles con textura y saturación bajas generan evidencia de vacío. La máscara excluye exposiciones extremas y conserva una categoría desconocida para la evidencia intermedia. |
| Detector YOLO | La inferencia devuelve cajas, confianza y clase. La clase 0 representa un producto y la 1 un espacio vacío. Con una región marcada, se conservan las detecciones cuyo centro cae dentro del polígono. Se descartan cajas de producto con más del 60 % de su área dentro de una caja de vacío y cajas con menos del 10 % del área mediana de los candidatos restantes. |

El detector local llama a `training/infer_yolo.py` como subproceso. El entrenamiento y la preparación de datos se encuentran en `backend/training/`. La inferencia utiliza los pesos registrados por el arranque de la aplicación.

## Medición por superficie y por frentes

En el modo superficial habilitado por defecto, YOLO con región marcada considera ocupados los píxeles cubiertos por cajas de producto. Los vacíos detectados aportan evidencia de área vacía y el resto de la región útil sin evidencia queda desconocido. Las áreas estructurales y las exclusiones se mantienen como categorías separadas. Sin la región marcada, el resultado usa el encuadre completo y genera una advertencia porque puede incorporar piso y techo.

El área evaluable es la suma del área ocupada y la vacía. La disponibilidad es `100 × ocupada / evaluable`. El área desconocida, estructural o excluida queda fuera del cálculo. Si el área evaluable es cero, se devuelve el estado `no_evaluable` con porcentajes nulos.

YOLO también agrupa productos por fila y estima huecos entre detecciones. Cuando se desactiva el piloto superficial con `REGOVA_SURFACE_PILOT=0` y la estimación de espacio útil se puede realizar, el sistema estima frentes libres con dimensiones de referencia de los productos y aplica la misma fórmula a los frentes ocupados y libres. La respuesta identifica la base de cálculo y conserva los porcentajes de superficie.

## Clasificación y evidencia

Con los umbrales iniciales de 30 % y 70 %, el resultado es crítico en o bajo 30 %, bajo por encima de 30 % y por debajo de 70 %, y aceptable desde 70 %. En el piloto superficial, si existe área desconocida y la cobertura de producto sobre la región útil queda en o bajo el umbral crítico, el servicio puede generar una alerta de revisión aunque la disponibilidad calculada sobre el área evaluable no active una alerta.

La respuesta incluye métricas, advertencias y una imagen marcada. Se recomienda leer conjuntamente la base de disponibilidad, el área desconocida y las advertencias de calidad al revisar una captura.

## Referencias en el código

- [Orquestación del análisis visual](../backend/app/services/vision.py)
- [Preprocesamiento y calidad](../backend/app/vision/preprocessing.py)
- [Heurística y filtrado de detecciones](../backend/app/vision/baseline.py)
- [Detector YOLO](../backend/app/vision/yolo_detector.py)
- [Agrupación por filas](../backend/app/shelf_rows.py) y [estimación de espacio útil](../backend/app/vision/useful_space.py)
- [Cálculo de disponibilidad](../backend/app/availability.py)
- [Ejecución y persistencia del análisis](../backend/app/services/analysis.py)
