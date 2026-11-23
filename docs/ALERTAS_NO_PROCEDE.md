# Cierre de alertas como No procede

Implementado el 16 de noviembre de 2026. En Estado y alertas, la acción No
procede abre un formulario con motivo obligatorio de 3 a 1000 caracteres,
sin contar espacios al principio o al final. Permite cancelar sin enviar.

La alerta pasa internamente a descartada, estado ya previsto en el esquema.
Se conservan motivo original, análisis y predicción. Se registran el motivo de
cierre en eventos_auditoria y el autor y la fecha en cerrada_por y cerrada_en.
El listado devuelve motivo_cierre, revisado_por y cerrada_en y ofrece el filtro
No procede. Una alerta cerrada no se reabre ni se marca como atendida.

Los reponedores pueden descartar alertas sin asignar o propias. Supervisores y
administradores pueden descartar alertas de su local, incluso asignadas a otro
reponedor, sin reemplazar al responsable original. Tomar y atender reposiciones
sigue reservado al reponedor. El servidor valida estas reglas, el aislamiento
por local, la existencia del motivo y el cierre bajo bloqueo de fila.

Contrato PATCH /api/alerts/{id}: estado=descartada y motivo obligatorio.
Los estados en_atencion y atendida conservan su contrato sin motivo.
No fue necesaria una migración. No se cambian predicciones históricas ni pesos.

Verificación: 91 pruebas de backend y algoritmo aprobadas sobre PostgreSQL
temporal independiente de REGOVA_BD. Incluye motivo vacío, longitud excesiva,
cierre persistente, autor, fecha, alerta ya cerrada, supervisor, administrador,
reponedor ajeno y aislamiento por local. También aprobaron las 53 pruebas de interfaz, incluidas las tres nuevas de
No procede. TypeScript y la compilación de producción finalizaron correctamente.

Para usarlo: reiniciar backend y recargar navegador con Ctrl+F5. La interfaz
compilada está en dist. Copia previa de módulos modificados en
C:/Users/NoahWeon/Documents/Codex/2026-11-12/yol/work/no_procede_before.
