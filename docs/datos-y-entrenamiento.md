# Datos, entrenamiento y evaluación

## Datos de entrada

El detector aprende a partir de fotografías de góndolas anotadas con cajas delimitadoras. El checkpoint incluido en la configuración de la instalación original usa **Retail Shelf Detection (RSD)** y **retail-shelf-object-detection (RSOD)**. Se seleccionaron porque etiquetan productos y espacios vacíos. El [constructor del conjunto combinado](../backend/training/data/build_combined.py) unifica los índices como 0 para producto y 1 para vacío, elimina duplicados exactos mediante SHA-256 y conserva las particiones de las fuentes. Las correcciones manuales en CVAT se aplicaron a 60 imágenes de entrenamiento.

| Partición | Imágenes | Cajas de producto | Cajas de vacío |
| --- | ---: | ---: | ---: |
| Entrenamiento | 1.194 | 122.283 | 3.935 |
| Validación | 254 | 36.254 | 1.141 |
| Prueba | 125 | 17.232 | 523 |

Las cifras corresponden al registro de preparación del conjunto usado para revisar el segundo candidato. Las imágenes corregidas pertenecen a entrenamiento. La clase vacío tiene menos ejemplos en las tres particiones, una diferencia relevante al interpretar las métricas por clase.

## Entrenamiento e inferencia

La versión registrada es **YOLOv8n**, corrida `segundo_60_extra10_20261112`. El [ajuste adicional](../backend/training/finetune_60.py) inicializó el entrenamiento desde el mejor checkpoint del candidato anterior y usó 10 épocas, resolución de 1024 píxeles y AdamW con tasa inicial de aprendizaje de 0,00001. Se eligió el mejor checkpoint según validación y se midió su desempeño en la partición de prueba de 125 imágenes.

En operación, el [script de inferencia](../backend/training/infer_yolo.py) recibe una fotografía, los pesos y el umbral de confianza. La aplicación transforma las cajas detectadas en métricas de disponibilidad mediante el [posprocesamiento](algoritmos.md). Las fotografías nuevas se usan como entradas de inferencia. El entrenamiento se ejecuta por separado.

## Resultados registrados

| Métrica en prueba | Valor |
| --- | ---: |
| mAP50 | 72,04 % |
| mAP50–95 | 38,79 % |
| mAP50 de producto | 89,92 % |
| mAP50 de vacío | 54,15 % |
| Recall de producto a confianza 0,25 e IoU ≥ 0,50 | 82,85 % |
| Recall de vacío a confianza 0,25 e IoU ≥ 0,50 | 42,26 % |

Estas métricas describen las cajas del detector en el conjunto de prueba usado durante el desarrollo. La medición de quiebre de stock visible incorpora además la región marcada, los filtros y las reglas de disponibilidad. Se procesaron también 50 fotografías externas para revisión visual. Esa muestra carecía de anotaciones de referencia para calcular precisión o recall.

## Reproducción

El checkpoint entrenado está incluido en [best.pt](../backend/data/training/yolo_runs/segundo_60_extra10_20261112/weights/best.pt). Los conjuntos de imágenes y las anotaciones se gestionan por separado. Reproducir el entrenamiento requiere además las exportaciones de RSD y RSOD, las etiquetas corregidas en CVAT, el checkpoint previo y el entorno de entrenamiento. El constructor de datos y el script de ajuste describen las rutas y parámetros esperados.


