# CU08: revisión de resultados

Implementado el 19 de noviembre de 2026.

## Uso
1. Reinicia el backend con el iniciador habitual y recarga con Ctrl+F5.
2. Ingresa como administrador o supervisor y abre Revisión de resultados.
3. Selecciona un análisis y contrasta sus imágenes y métricas.
4. Elige Confirmado, Corregido o Descartado. La corrección exige una descripción y permite indicar disponibilidad de 0 a 100 % opcionalmente.
5. Guarda la revisión. El historial conserva la decisión, corrección, comentario, autor y fecha al volver a abrir el resultado.

## Alcance
La revisión se guarda separada de la predicción: no modifica detecciones, porcentajes ni imágenes y no cierra alertas. No procede pertenece al flujo CU13. Solo administrador y supervisor tienen acceso; se limita al local y a análisis no eliminados.

No requiere cambios de esquema ni migraciones: reutiliza la tabla revisiones y el POST existente. Se agregó GET /api/analyze/{id}/reviews para consultar el historial.

## Validación
101 pruebas del backend y 56 de interfaz aprobadas. TypeScript y compilación de producción correctos. Se verificaron las tres decisiones, persistencia, autor, fecha, auditoría, permisos, aislamiento entre locales, análisis eliminados y conservación del resultado y de las alertas. En la interfaz se verificó corrección de 0 %, errores de guardado y reintento de consulta tras guardar exitosamente.

Backend probado con PostgreSQL temporal desechable, sin usar la base operativa. La nueva interfaz fue verificada con pruebas automatizadas de componentes; no se realizó una sesión manual con usuarios finales.
