# Herramientas auxiliares de Regova

Los lanzadores de entrega están en [ejecutables](../ejecutables/README.md). Esta carpeta contiene los archivos de desarrollo, pruebas, migraciones antiguas y el antiguo lanzador del piloto. El piloto ya está integrado en el arranque normal.

# REGOVA: qué abrir y en qué orden

Los lanzadores de uso diario, preparación y correo están en la carpeta ejecutables. Los archivos .py siguen en backend y scripts porque son el código, no accesos duplicados. Mantén ejecutables dentro del proyecto: no copies un BAT suelto a otra carpeta; crea un acceso directo si lo quieres en el escritorio.

## Si este PC ya funciona (tu caso)

1. Abre INICIAR_REGOVA.bat.
2. Espera las comprobaciones; se abrirá el navegador en http://127.0.0.1:8011.
3. Mantén abierta la consola mientras usas REGOVA.
4. Para detenerlo, vuelve a la consola y pulsa Ctrl+C. Si pregunta por finalizar, confirma.

Eso es todo para el uso diario. No ejecutes todos los archivos en orden. No repitas preparación ni actualizaciones cada vez que abres el sistema.

## Primera vez en otro PC

1. Copia el proyecto completo, incluidos modelo y almacenamiento si corresponde. El código de GitHub por sí solo no incluye credenciales, imágenes ni pesos privados.
2. Instala Python 3.13 x64 y PostgreSQL. Para desarrollo o pruebas del frontend, instala también Node.js con npm.
3. Ejecuta PREPARAR_EQUIPO.bat. Puede descargar dependencias y pedir el usuario propietario y la contraseña de PostgreSQL. Al escribir contraseñas no verás caracteres: es normal. Si la base no existe con el esquema, el asistente puede restaurar el .dump más reciente de backend/backups/postgresql o crear el esquema si no hay respaldo. No lo uses como restauración manual sin revisar qué respaldo estás llevando.
4. Si es una instalación vacía, define la contraseña de ADM-001 cuando se solicite. Si la cuenta ya existe, se conserva.
5. Revisa backend/.env para la configuración de correo de ese equipo. CONFIGURAR_CLAVE_CORREO.bat guarda únicamente la contraseña de aplicación, no configura todos los datos SMTP.
6. Ejecuta INICIAR_REGOVA.bat y realiza un análisis de prueba.

La preparación necesita el modelo disponible para completar sus comprobaciones. Si falta, hay que copiar o registrar el modelo antes de analizar. Una BD restaurada necesita también sus imágenes y archivos de backend/storage.

## Estoy trabajando en el frontend

1. Inicia EJECUTAR.bat para levantar solo el backend (8011).
2. En otra ventana, abre INICIAR_FRONTEND.bat; Vite mostrará su dirección (normalmente http://localhost:5173).
3. Mantén ambas ventanas abiertas.
4. Para actualizar la interfaz compilada que usa 8011, ejecuta npm run build desde la raíz del proyecto.

No inicies EJECUTAR.bat e INICIAR_REGOVA.bat como dos servidores simultáneos. Son alternativas para el mismo backend: el primero es directo; el segundo comprueba el equipo y abre el navegador.

## Cambié la clave del correo

1. Ejecuta CONFIGURAR_CLAVE_CORREO.bat e ingresa la contraseña de aplicación de Gmail, no la habitual.
2. Detén y vuelve a iniciar REGOVA para cargar el cambio.
3. Solicita una recuperación con un correo registrado y comprueba la recepción.

## Actualizaciones de una instalación antigua (solo si corresponden)

- ACTUALIZAR_UBICACION.bat: agrega o actualiza la ubicación por pasillo.
- ACTUALIZAR_RECUPERACION.bat: agrega la tabla y permisos de recuperación por correo.
- Ambos piden credenciales del propietario de PostgreSQL. Si tu instalación ya tiene esas funciones, no necesitas ejecutarlos para abrir REGOVA.
- PREPARAR_POSTGRESQL.bat: configura el rol de aplicación, migraciones y cuenta inicial sobre una base que ya tiene el esquema. Es una herramienta específica; PREPARAR_EQUIPO.bat ya integra esta preparación. No son dos pasos obligatorios consecutivos.

Después de actualizar, reinicia el backend y recarga la pestaña con Ctrl+F5.

## Ejecutar las pruebas

- EJECUTAR_QA.bat: pruebas frontend con cobertura y generación del informe. Necesita npm y backend/.venv para el generador del informe. Resultados en reports/qa.
- Para backend y algoritmo en PostgreSQL temporal: desde la raíz, backend/.venv/Scripts/python.exe scripts/run_backend_qa.py. No utiliza REGOVA_BD.
- La carpeta testing contiene copias de evidencia de la campaña realizada. Ejecutar QA no vuelve a sincronizar esas copias automáticamente.

## Qué hace cada archivo

| Archivo | Cuándo usarlo |
|---|---|
| INICIAR_REGOVA.bat | Uso diario con comprobaciones y apertura del navegador |
| EJECUTAR.bat | Arranque directo del backend; útil en desarrollo |
| INICIAR_FRONTEND.bat | Desarrollo con recarga automática de React |
| PREPARAR_EQUIPO.bat | Preparar otro equipo o reparar la preparación |
| PREPARAR_POSTGRESQL.bat | Preparación específica de una BD con esquema inicial |
| CONFIGURAR_CLAVE_CORREO.bat | Guardar o reemplazar la credencial SMTP |
| ACTUALIZAR_UBICACION.bat | Instalaciones anteriores al cambio de ubicación |
| ACTUALIZAR_RECUPERACION.bat | Instalaciones anteriores a recuperación por correo |
| EJECUTAR_QA.bat | Ejecutar pruebas frontend e informe |

## Si algo falla

- Puerto 8011 ocupado: revisa si REGOVA ya está abierto; no levantes otro servidor.
- No conecta a PostgreSQL: comprueba que su servicio esté iniciado y que backend/.env corresponda a ese PC.
- Falta Python o .venv: revisa la preparación inicial.
- Falta el modelo: comprueba pesos y almacenamiento; reinstalar Node no lo resuelve.
- Cambié el frontend pero no se ve: compila y recarga con Ctrl+F5.
- Hay un error: conserva el mensaje de la consola para revisarlo; no envíes .env ni contraseñas.

Nunca borres .env, storage, data o backups para intentar corregir un error. Esta reorganización solo cambia dónde están los accesos; no modifica la BD ni las credenciales.
