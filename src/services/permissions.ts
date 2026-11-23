/** Roles disponibles en el prototipo REGOVA. */
export type Role = 'admin_principal' | 'admin_global' | 'admin_regional' | 'admin_local' | 'supervisor' | 'reponedor';
export type Section = 'history' | 'dashboard' | 'analysis' | 'gondolas' | 'alerts' | 'review' | 'settings' | 'users';

export const roleLabels: Record<Role, string> = {
  admin_principal: 'Administrador principal',
  admin_global: 'Administrador global',
  admin_regional: 'Administrador regional',
  admin_local: 'Administrador local',
  supervisor: 'Supervisor',
  reponedor: 'Reponedor',
};

// Matriz PROVISIONAL para validar casos de uso; no es política oficial de Walmart.
// Conservamos la navegación actual para no alterar otras pantallas.
const access: Record<Role, readonly Section[]> = {
  admin_principal: ['history', 'dashboard', 'analysis', 'gondolas', 'alerts', 'review', 'settings', 'users'],
  admin_global: ['history', 'dashboard', 'analysis', 'gondolas', 'alerts', 'review', 'settings', 'users'],
  admin_regional: ['history', 'dashboard', 'analysis', 'gondolas', 'alerts', 'review', 'settings', 'users'],
  admin_local: ['history', 'dashboard', 'analysis', 'gondolas', 'alerts', 'review', 'settings', 'users'],
  supervisor: ['history', 'dashboard', 'analysis', 'gondolas', 'alerts', 'review'],
  reponedor: ['history', 'dashboard', 'gondolas', 'alerts'],
};

export function canAccess(role: Role, section: Section): boolean {
  return access[role]?.includes(section) ?? false;
}

export function canManageUsers(role: Role): boolean {
  return canAccess(role, 'users');
}

/** Acciones asociadas a CU01–CU08 y a la gestión de usuarios del prototipo. */
export type Permission =
  | 'gondolas.configure' // CU01
  | 'criteria.configure' // CU02
  | 'analysis.execute'   // CU03
  | 'gondolas.view'      // CU04
  | 'alerts.view'        // CU05
  | 'alerts.resolve'     // CU06
  | 'dashboard.view'     // CU07
  | 'results.review'     // CU08
  | 'users.view'
  | 'users.create'
  | 'users.edit'
  | 'users.suspend'
  | 'users.delete';

const administratorRoles: readonly Role[] = [
  'admin_principal', 'admin_global', 'admin_regional', 'admin_local',
];

// Permisos por ACCIÓN, independientes de la visibilidad de las secciones.
// La restricción por sucursal y jerarquía se implementará en una etapa posterior.
const permissions: Record<Permission, readonly Role[]> = {
  'gondolas.configure': administratorRoles,
  'criteria.configure': administratorRoles,
  'analysis.execute': [...administratorRoles, 'supervisor'],
  'gondolas.view': [...administratorRoles, 'supervisor', 'reponedor'],
  'alerts.view': [...administratorRoles, 'supervisor', 'reponedor'],
  'alerts.resolve': ['reponedor'],
  'dashboard.view': [...administratorRoles, 'supervisor'],
  'results.review': ['supervisor'],
  'users.view': administratorRoles,
  'users.create': administratorRoles,
  'users.edit': administratorRoles,
  'users.suspend': administratorRoles,
  'users.delete': administratorRoles,
};

export function hasPermission(role: Role, permission: Permission): boolean {
  return permissions[permission]?.includes(role) ?? false;
}

export function hasAllPermissions(role: Role, requested: readonly Permission[]): boolean {
  return requested.every(permission => hasPermission(role, permission));
}

export function hasAnyPermission(role: Role, requested: readonly Permission[]): boolean {
  return requested.some(permission => hasPermission(role, permission));
}
