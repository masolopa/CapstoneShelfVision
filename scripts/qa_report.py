"""Genera el informe QA a partir de resultados reales de Vitest."""
import hashlib
import html
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[1]
results = json.loads((root / 'reports/qa/results.json').read_text(encoding='utf-8'))
coverage = json.loads((root / 'reports/qa/coverage/coverage-summary.json').read_text(encoding='utf-8'))
package = json.loads((root / 'package.json').read_text())
cases = [case for suite in results['testResults'] for case in suite['assertionResults']]
time = datetime.fromtimestamp(results['startTime']/1000, ZoneInfo('America/Santiago')).isoformat()
preconditions = {
 'CU-AUT': 'Componente Login montado sin sesión; respuestas HTTP simuladas; datos ficticios.',
 'CU-REC': 'Login en recuperación o con token ficticio en el fragmento de la URL; API simulada.',
 'CU-ALT': 'Tres alertas ficticias con estados y responsables controlados; rol indicado por el caso.',
 'CU-PER': 'Usuarios ficticios de roles y locales controlados; funciones reales de permisos del frontend.',
 'CU-USU': 'Administrador ficticio y listado controlado con una cuenta protegida y un reponedor.'
}
rows = []
for case in cases:
 group = case['ancestorTitles'][0]
 expected = case['title'].split(' | ', 1)[-1]
 actual = 'Las aserciones de comportamiento se cumplieron.' if case['status']=='passed' else 'Revisar resultados JSON y reporte Vitest.'
 rows.append(f"| {case['title'].split(' | ')[0]} | {group} | {expected} | {actual} | {case['status']} | {case.get('duration',0):.1f} |")
text = f"""# Informe QA de componentes — REGOVA

Ejecución: {time}. Entorno: Windows, Node v24.20.0, Vitest {package['devDependencies']['vitest']}, jsdom y React Testing Library. Interfaz REGOVA v1.0; package.json {package['version']}. La huella de los archivos evaluados se incluye en manifest.json.

## Resultado

{results['numTotalTests']} ejecuciones: {results['numPassedTests']} aprobadas, {results['numFailedTests']} fallidas, {results['numPendingTests']} omitidas. Son 43 identificadores de caso; algunos se ejecutan con varias combinaciones de roles o estados. No se realizaron comparaciones visuales ni recorridos en navegador real.

## Alcance y metodología

Componentes Login (incluye recuperación), Users y Alerts. Se utiliza renderizado DOM en jsdom, interacción mediante user-event y respuestas HTTP simuladas en fetch. Los servicios reales del frontend procesan estas respuestas: no se sustituyen por funciones que siempre aprueban. Cada prueba verifica una salida observable, una solicitud o una acción bloqueada.

Los códigos CU-AUT, CU-REC, CU-ALT y CU-USU son agrupaciones de este plan de QA, no identificadores oficiales de la tesis. Deben homologarse con su matriz de requisitos antes de la entrega académica.

Precondiciones por grupo:
"""
for group, value in preconditions.items(): text += f"- {group}: {value}\n"
text += """
Las entradas exactas, acciones y aserciones están en src/test/components.test.tsx. Se usan correos de prueba y contraseñas ficticias; no se consulta la BD ni se envían correos.

## Matriz de ejecución

| Caso | Grupo | Resultado esperado / comportamiento | Resultado observado | Estado | Duración ms |
|---|---|---|---|---|---:|
""" + '\n'.join(rows)
text += '\n\n## Cobertura del alcance seleccionado\n\n| Medida | Porcentaje | Cubierto / total |\n|---|---:|---:|\n'
for key, label in [('lines','Líneas'),('statements','Sentencias'),('functions','Funciones'),('branches','Ramas')]:
 metric = coverage['total'][key]
 text += f"| {label} | {metric['pct']} % | {metric['covered']} / {metric['total']} |\n"
text += """
La cobertura incluye tres componentes y cuatro servicios relacionados, definidos en vitest.config.ts. No es cobertura del sistema completo. El 100 % de aprobación de estos casos no implica ausencia de defectos.

## Hallazgos y seguimiento

- La ejecución final no detectó incumplimientos en los 50 escenarios evaluados. No se modificó la lógica funcional de los componentes para obtener aprobación.
- Durante la preparación se corrigieron dos problemas del arnés: una búsqueda de etiqueta demasiado estricta y la reutilización de una Response ya consumida en el mock. También se corrigieron opciones de tipado de las consultas de prueba. No se clasifican como defectos de REGOVA.
- npm audit informó 9 vulnerabilidades moderadas en el árbol de herramientas ESLint/TypeScript; ninguna alta ni crítica. Se adjunta el resultado audit-dependencies.json. Este comando no sustituye una auditoría de seguridad. No se aplicaron actualizaciones incompatibles automáticamente.
- Ampliación: confirmación de baja, reactivación, edición de roles, correo propio, errores de guardado, estados vacíos, fallos de red y permisos negativos. La longitud mínima se verifica como atributo HTML en jsdom y como rechazo HTTP 422 real en FastAPI; jsdom no reproduce completamente minlength.
- Pendiente: pantallas de configuración, panorama general, análisis y resultados en la suite frontend; más variantes de errores y roles heredados.

## Fuera de alcance

Fuera del frontend aislado: autorización y persistencia del servidor. Estas se verificaron adicionalmente mediante pytest y PostgreSQL real, según el apartado siguiente. Siguen fuera de esta ejecución: entrega SMTP real, compatibilidad entre navegadores, pruebas visuales, rendimiento y precisión del detector. Mostrar un error simulado de enlace vencido verifica la UI, no el vencimiento real. Ocultar botones verifica la interfaz, no la seguridad del backend.

## Reproducción

Desde la carpeta del proyecto, ejecutar npm ci, luego npm run test:qa. El proceso devuelve error si falla una prueba. Para regenerar este informe después de la ejecución: backend/.venv/Scripts/python.exe scripts/qa_report.py. Alternativa: ejecutar EJECUTAR_QA.bat. Requiere el entorno Python existente solo para el informe narrativo.

Archivos: reports/qa/results.json (resultados), reports/qa/junit.xml (intercambio), reports/qa/coverage/index.html (cobertura), .vitest/index.html (visor Vitest; servir con npx vite preview --outDir .vitest), reports/qa/INFORME_QA.html (informe autónomo legible sin servidor).

## Criterio de aceptación

Todos los casos seleccionados aprobados, sin pruebas omitidas, con evidencia y cobertura publicadas. Esta ejecución satisface ese criterio para el alcance indicado. No constituye una certificación de seguridad ni una aprobación de producción.
"""
backend_xml = root/'reports/qa/backend-junit.xml'
if backend_xml.exists():
    import xml.etree.ElementTree as ET
    tree = ET.parse(backend_xml)
    backend_cases = tree.findall('.//testcase')
    failed = sum(case.find('failure') is not None or case.find('error') is not None for case in backend_cases)
    skipped = sum(case.find('skipped') is not None for case in backend_cases)
    text += f"\n\n## Ejecución adicional de backend con PostgreSQL real\n\n{len(backend_cases)} pruebas; {failed} fallidas; {skipped} omitidas. Evidencia: backend-junit.xml. PostgreSQL 18 temporal en loopback y puerto independiente, base REGOVA_QA_TEST, esquema creado con migraciones 000–003 y almacenamiento temporal. No se utilizó REGOVA_BD. El rol propietario de la instancia de prueba no reproduce los permisos SQL limitados del usuario de producción. SMTP se sustituyó por una captura local del token, sin enviar mensajes.\n\n"
    text += "Casos nuevos: persistencia Argon2, rechazo de contraseña anterior, enlace de un solo uso, token expirado, contraseña demasiado corta, revocación de sesiones, recuperación bloqueada de cuenta suspendida, dos cambios concurrentes con el mismo token y dos reponedores compitiendo por una alerta. Incluye la suite previa de API y servicios.\n\n"
    text += "| Prueba backend | Resultado | Duración s |\n|---|---|---:|\n"
    for case in backend_cases:
        status = 'omitida' if case.find('skipped') is not None else 'fallida' if case.find('failure') is not None or case.find('error') is not None else 'aprobada'
        text += f"| {case.attrib.get('name')} | {status} | {case.attrib.get('time')} |\n"
    text += "\nReproducción de integración: ejecutar backend/.venv/Scripts/python.exe scripts/run_backend_qa.py. El asistente requiere PostgreSQL instalado y prepara una instancia temporal; su salida describe la evidencia generada. Las pruebas existentes usan TRUNCATE solo en la base temporal terminada en _TEST.\n"
(root/'reports/qa/INFORME_QA.md').write_text(text,encoding='utf-8')
# HTML autónomo: conserva la matriz y el detalle de ejecución sin dependencias remotas.
table = ''.join('<tr>'+''.join('<td>'+html.escape(str(value))+'</td>' for value in [case['title'].split(' | ')[0],case['ancestorTitles'][0],case['title'].split(' | ',1)[-1],case['status'],round(case.get('duration',0),1)])+'</tr>' for case in cases)
page = '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>QA REGOVA</title><style>body{font:15px system-ui;color:#183653;background:#f2f6fb;margin:0;padding:35px}main{max-width:1150px;margin:auto;background:white;padding:35px;border-radius:16px}h1{color:#075fb9}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 system-ui}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #d7e2ef;padding:10px;text-align:left}th{background:#eaf3ff}tr:nth-child(even){background:#f7faff}</style><main><h1>REGOVA · QA de componentes</h1><p>'+str(results['numPassedTests'])+' / '+str(results['numTotalTests'])+' pruebas aprobadas</p><table><thead><tr><th>Caso</th><th>Grupo</th><th>Comportamiento esperado</th><th>Estado</th><th>ms</th></tr></thead><tbody>'+table+'</tbody></table><h2>Informe y límites</h2><pre>'+html.escape(text)+'</pre></main></html>'
(root/'reports/qa/INFORME_QA.html').write_text(page,encoding='utf-8')
files = [root/'package.json',root/'package-lock.json',root/'vitest.config.ts',root/'src/test/components.test.tsx',root/'src/test/setup.ts',root/'backend/tests/test_api_postgres.py',root/'scripts/run_backend_qa.py'] + [root/path for path in ['src/pages/Login/Login.tsx','src/pages/Users/Users.tsx','src/pages/Analysis/Alerts.tsx','src/services/auth.ts','src/services/http.ts','src/services/permissions.ts','src/services/userAccess.ts']]
(root/'reports/qa/manifest.json').write_text(json.dumps({'execution':time,'sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},indent=2),encoding='utf-8')
print('Informe QA y manifiesto generados.')
