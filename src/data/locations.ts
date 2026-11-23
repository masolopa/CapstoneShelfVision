/** Catálogo territorial inicial de REGOVA (Chile).
 * Las regiones son divisiones administrativas reales; las sucursales son FICTICIAS
 * y se utilizan exclusivamente para pruebas. No representan locales Walmart.
 * No modifica localStorage ni las cuentas existentes.
 */
export type Region = { id: string; name: string };
export type DemoBranch = { id: string; name: string; regionId: string };

export const COUNTRY = { code: 'CL', name: 'Chile' } as const;

export const regions: readonly Region[] = [
  { id: 'CL-AP', name: 'Arica y Parinacota' },
  { id: 'CL-TA', name: 'Tarapacá' },
  { id: 'CL-AN', name: 'Antofagasta' },
  { id: 'CL-AT', name: 'Atacama' },
  { id: 'CL-CO', name: 'Coquimbo' },
  { id: 'CL-VS', name: 'Valparaíso' },
  { id: 'CL-RM', name: 'Metropolitana de Santiago' },
  { id: 'CL-LI', name: "Libertador General Bernardo O'Higgins" },
  { id: 'CL-ML', name: 'Maule' },
  { id: 'CL-NB', name: 'Ñuble' },
  { id: 'CL-BI', name: 'Biobío' },
  { id: 'CL-AR', name: 'La Araucanía' },
  { id: 'CL-LR', name: 'Los Ríos' },
  { id: 'CL-LL', name: 'Los Lagos' },
  { id: 'CL-AI', name: 'Aysén del General Carlos Ibáñez del Campo' },
  { id: 'CL-MA', name: 'Magallanes y de la Antártica Chilena' },
];

export const demoBranches: readonly DemoBranch[] = [
  { id: 'DEMO-RM-MAIPU', name: 'Maipú', regionId: 'CL-RM' },
  { id: 'DEMO-RM-PROVIDENCIA', name: 'Providencia', regionId: 'CL-RM' },
  { id: 'DEMO-RM-PUENTE-ALTO', name: 'Puente Alto', regionId: 'CL-RM' },
  { id: 'DEMO-VS-VINA', name: 'Viña del Mar', regionId: 'CL-VS' },
  { id: 'DEMO-BI-CONCEPCION', name: 'Concepción', regionId: 'CL-BI' },
  { id: 'DEMO-AN-ANTOFAGASTA', name: 'Antofagasta', regionId: 'CL-AN' },
];

export function getRegion(id: string): Region | undefined {
  return regions.find(region => region.id === id);
}

export function getDemoBranch(id: string): DemoBranch | undefined {
  return demoBranches.find(branch => branch.id === id);
}

export function getBranchesByRegion(regionId: string): DemoBranch[] {
  return demoBranches.filter(branch => branch.regionId === regionId);
}

function normalizeName(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .trim().toLocaleLowerCase('es-CL').replace(/\s+/g, ' ');
}

/** Reconoce nombres antiguos de sucursal sin modificar los datos almacenados.
 * Solo devuelve coincidencias únicas; no adivina sucursales desconocidas.
 */
export function resolveLegacyBranch(value: string): DemoBranch | undefined {
  const normalized = normalizeName(value).replace(/^sucursal\s+/, '');
  const matches = demoBranches.filter(branch => normalizeName(branch.name) === normalized);
  return matches.length === 1 ? matches[0] : undefined;
}

/** Devuelve la región asociada a una sucursal de demostración. */
export function getBranchRegion(branchId: string): Region | undefined {
  const branch = getDemoBranch(branchId);
  return branch ? getRegion(branch.regionId) : undefined;
}
