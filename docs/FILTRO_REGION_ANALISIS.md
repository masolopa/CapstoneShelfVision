# Filtro de detecciones por región de análisis

Corrección del 16 de noviembre de 2026 aplicada al backend de REGOVA.

Cuando existe un polígono de región, los productos y los vacíos detectados se
seleccionan por pertenencia de su centro al polígono, incluyendo el borde. Esta
regla conserva una unidad cuyo centro está dentro aunque su caja cruce el límite.
El filtro ocurre antes de descartar productos por tamaño o solapamiento con un
vacío, para evitar que detecciones exteriores influyan en las interiores.

Los espacios detectados y los huecos geométricos se intersectan con la máscara
de la región. Los espacios sin intersección se eliminan del resumen; los que
cruzan el borde se limitan a la parte interior y sus frentes se estiman según el
ancho interior. El bbox del resultado encierra la intersección, por lo que puede
contener área exterior en polígonos inclinados o cóncavos. El dibujo se recorta
adicionalmente con la máscara exacta del polígono. La línea cyan es una guía de
la región y puede extenderse unos píxeles por su grosor y antialiasing.

Sin región, se conserva el análisis de toda la imagen y la advertencia de que
suelo y techo pueden contar como vacío. Los huecos geométricos siguen
desactivados en ese caso, como antes de esta corrección.

La superficie ya se calculaba dentro de la máscara. El filtro temprano puede
cambiarla al eliminar cajas cuyo centro está fuera pero que antes intersectaban
el interior. No se modificaron los pesos, el entrenamiento ni la base de datos.
Las exclusiones y las estructuras mantienen su comportamiento previo; esta
corrección se refiere al límite exterior de la región de análisis.

Los análisis históricos y sus imágenes no se regeneran automáticamente. Se
requiere reiniciar el backend y generar un análisis nuevo.

## Verificación

Se ejecutaron 49 casos aprobados entre test_roi_detections.py,
test_baseline.py, test_shelf_rows.py, test_availability.py y
test_vision_modules.py. La inferencia se sustituyó por detecciones controladas
en las pruebas nuevas; no se entrenó ni se midió de nuevo la precisión del
modelo. Se comprobaron ambas clases, alineación de confianzas, efectos de cajas
exteriores, polígonos cóncavos, recorte visual inclinado, resúmenes y ausencia de
región. No se ejecutaron las pruebas que requieren PostgreSQL.
