# Estimación experimental de espacio útil

Prueba reversible del 16 de noviembre de 2026. Se activa por defecto en análisis
YOLO nuevos con región definida. Para desactivarla, establecer
REGOVA_USEFUL_SPACE=0 en el entorno del servidor y reiniciarlo.

La disponibilidad de superficie conserva su fórmula y sus máscaras y se guarda
en surface_availability_pct y surface_empty_pct. En análisis nuevos evaluados
por espacio útil, el porcentaje principal usa frentes ocupados / (ocupados +
libres útiles), con dos decimales; el porcentaje libre es su complemento a 100.
availability_basis=useful_fronts identifica esta semántica. Las alertas usan
este porcentaje principal y los umbrales configurados. La superficie evaluable
continúa expresada en píxeles y no es el denominador del porcentaje por frentes.
La pantalla y el PDF distinguen la medida de superficie y la de capacidad.
No se cambian pesos, número de productos detectados ni análisis históricos.
Sin ROI o referencia útil evaluada, se conserva el porcentaje de superficie
con availability_basis=surface. Los promedios del historial pueden mezclar ambas
bases si hay capturas antiguas: no deben interpretarse como una comparación
experimental homogénea sin separar por availability_basis.

Por cada fila, se calcula la mediana de ancho y alto de las cajas de producto.
Un rectángulo de ese tamaño debe caber completo sobre píxeles clasificados como
vacíos dentro de la región, sin tocar producto, estructura ni exclusión. No se
rota, encoge ni tolera invasión. Las dimensiones se redondean hacia arriba.
Una fila sin productos usa la mediana global y declara ese origen en la salida.

La búsqueda con imagen integral selecciona posiciones de abajo hacia arriba y
de izquierda a derecha, sin solapes entre rectángulos. Es un método voraz,
limitado a 1000 posiciones por fila, no un cálculo óptimo de empaquetado.
Se usa la franja vertical ocupada por los productos de la fila, o la banda de
la fila si no hay productos. La perspectiva no se rectifica.

Las posiciones aceptadas se dibujan en rojo. Se clasifican en vacios si el centro
está dentro de una propuesta original del detector de vacío, o en huecos si son
geométricas. Ambas listas representan posiciones de un frente estimado y no se
suman dos veces. Los frentes libres y totales por fila se actualizan junto con
su ocupación y estado. Los valores previos quedan en campos terminados en
_superficie; las propuestas previas en vacios_visuales y huecos_visuales.
El campo espacio_util contiene versión, referencias y estado de evaluación.

La ocupación por frentes puede ser 100 % mientras la disponibilidad de
superficie sea menor: son medidas distintas. Un espacio residual no utilizable
sigue siendo superficie vacía. Las alertas globales de análisis útiles se calculan a partir de frentes.

La estimación no identifica SKU, profundidad ni capacidad física real. Depende
de las cajas del detector: una omisión puede crear espacio libre falso y una
caja falsa puede ocultar espacio real. La referencia mediana es poco fiable con
productos muy diferentes o perspectivas extremas. Si no hay ningún producto
de referencia, no se evalúa espacio útil y se mantiene el comportamiento previo,
con evaluado=false en espacio_util.

## Validación

58 casos aprobados entre test_useful_space.py, test_roi_detections.py,
test_baseline.py, test_shelf_rows.py, test_availability.py y
test_vision_modules.py. Se comprobaron rendijas, altura insuficiente, ajuste
exacto, falta de solapes, obstáculos, máscaras discontinuas, referencia local
y conservación de superficie y conteo, porcentaje útil, alertas y generación de PDF. La inferencia se simuló en las pruebas;
no se ejecutaron pruebas de PostgreSQL ni una nueva evaluación del modelo.
Queda pendiente la validación manual con fotografías reales por el usuario.

## Reversión

La opción REGOVA_USEFUL_SPACE=0 desactiva la estimación por frentes y conserva el filtro poligonal.

## Referencias por sector versión 2

Prueba del 16 de noviembre de 2026 para filas con productos de tamaños mixtos.
La fila se divide en sectores según la referencia predominante entre las tres
columnas de producto más cercanas horizontalmente. Se agrupan tamaños con una
razón máxima de 1,45 en ancho y alto; se usa la mediana de cada grupo. Las cajas
apiladas votan como una sola columna para evitar que su cantidad imponga una
referencia pequeña al sector de botellas.

La referencia ganadora debe coincidir también con la de la columna más cercana.
Si hay empate o desacuerdo local, no se proponen posiciones en esa franja. El
rectángulo completo debe caber en su sector, además de respetar la máscara vacía.
No se encoge, gira ni reemplaza por el grupo pequeño para hacerlo caber.

Sin productos en una fila sigue vigente la referencia global previa. Continúa
sin comprobar soporte físico ni apilabilidad. La abstención en sectores ambiguos
puede subestimar capacidad libre y elevar la ocupación útil; cero propuestas no
prueba ocupación real completa. La metadata de cada fila registra sectores y
ancho_ambiguo_px para revisión. Los rangos x son orientativos y pueden envolver
sectores no contiguos; el algoritmo usa la máscara de sector completa.

61 pruebas de algoritmo e integración seleccionadas aprobadas, incluidas tres
nuevas sobre mezcla de tamaños, empate de referencias y protección de una columna
alta frente a vecinas pequeñas. No se reentrenó YOLO. Falta validación manual de
esta versión en fotografías reales. No se volvió a ejecutar PostgreSQL porque
no se cambió persistencia, API ni esquema.

Para volver solo a la referencia por fila anterior: establecer
REGOVA_LOCAL_REFERENCE=0 y reiniciar el backend. Para quitar por completo el
experimento útil: REGOVA_USEFUL_SPACE=0. Copia previa del módulo en
C:/Users/NoahWeon/Documents/Codex/2026-11-12/yol/work/local_reference_before/useful_space.py.

