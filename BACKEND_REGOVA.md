# Backend REGOVA

La API está organizada por rutas, seguridad, repositorios, almacenamiento y visión. Usa PostgreSQL y sesiones del servidor; ya no valida cuentas con localStorage ni persiste análisis nuevos en SQLite.

1. Si REGOVA_BD ya tiene el esquema inicial, ejecutar herramientas/PREPARAR_POSTGRESQL.bat una vez para configurar el acceso, sesiones, administrador y modelo. Se solicitan las contraseñas localmente.
2. Ejecutar herramientas/EJECUTAR.bat.
3. Ejecutar herramientas/INICIAR_FRONTEND.bat para desarrollo, o abrir http://127.0.0.1:8011 para la interfaz compilada.
4. Ingresar como ADM-001, crear las cuentas necesarias. Al analizar se indica el pasillo y, opcionalmente, una referencia de ubicación. No se precargan contraseñas de demostración.

Detalle de arquitectura, permisos, archivos, pruebas y límites: backend/API_REGOVA.md.

El historial antiguo queda conservado aparte; no se importa al flujo nuevo. SQLite y sus imágenes existentes se mantienen intactos.

Para una instalación ya preparada con el selector anterior: ejecutar herramientas/ACTUALIZAR_UBICACION.bat, reiniciar herramientas/EJECUTAR.bat y actualizar la página con Ctrl+F5.
