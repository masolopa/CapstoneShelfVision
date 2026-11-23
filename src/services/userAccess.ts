import { MVP_BRANCH } from './mvpLocal';
/** Reglas de administración de cuentas para el prototipo REGOVA.
 * La interfaz refleja reglas que FastAPI vuelve a comprobar en el servidor.
 * Las ubicaciones desconocidas NO conceden acceso territorial.
 */
import type { User } from './auth';
import type { Role } from './permissions';
import {
  getDemoBranch, getRegion, regions, resolveLegacyBranch,
} from '../data/locations';

export type AccountAction = 'view' | 'create' | 'edit' | 'suspend' | 'delete';
export type Assignment = Pick<User, 'role' | 'scope' | 'branch'>;

const rank: Record<Role, number> = {
  admin_principal: 5,
  admin_global: 4,
  admin_regional: 3,
  admin_local: 2,
  supervisor: 1,
  reponedor: 0,
};

function isAdministrator(role: Role): boolean {
  return rank[role] >= rank.admin_local;
}

function resolveRegion(value: string): string | null {
  const byId = getRegion(value);
  if (byId) return byId.id;
  const normalized = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .trim().toLocaleLowerCase('es-CL');
  const matches = regions.filter(r =>
    r.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('es-CL') === normalized,
  );
  return matches.length === 1 ? matches[0].id : null;
}

function resolveBranch(value: string) {
  return getDemoBranch(value) ?? resolveLegacyBranch(value);
}

/** Región efectiva, tanto para asignaciones nuevas como antiguas reconocibles. */
export function assignmentRegion(user: Assignment): string | null {
  if (user.scope === 'regional') return resolveRegion(user.branch);
  if (user.scope === 'local') return resolveBranch(user.branch)?.regionId ?? null;
  return null;
}

/** Código de sucursal efectivo; null si no puede identificarse de forma única. */
export function assignmentBranch(user: Assignment): string | null {
  return user.scope === 'local' ? resolveBranch(user.branch)?.id ?? null : null;
}

/** Comprueba si una asignación se encuentra dentro del territorio del administrador. */
export function isWithinTerritory(actor: User, target: Assignment): boolean {
  if (!isAdministrator(actor.role)) return false;
  if (actor.role === 'admin_principal') return target.scope === 'local' && target.branch === MVP_BRANCH;
  if (actor.role === 'admin_global') return false;
  if (actor.role === 'admin_regional') return false;
  const actorBranch = assignmentBranch(actor);
  const targetBranch = assignmentBranch(target);
  return actorBranch !== null && actorBranch === targetBranch;
}

/** Un administrador solo puede asignar roles estrictamente inferiores al suyo. */
export function canAssignRole(actor: User, proposedRole: Role): boolean {
  return (actor.role === 'admin_principal' || actor.role === 'admin_local') &&
    ['admin_local', 'supervisor', 'reponedor'].includes(proposedRole) && rank[proposedRole] < rank[actor.role];
}

/** Autoriza una operación sobre una cuenta ya existente. */
export function canActOnUser(
  actor: User,
  target: User,
  action: Exclude<AccountAction, 'create'>,
): boolean {
  if (!isAdministrator(actor.role)) return false;
  if (target.id === 'ADM-001' && action !== 'view') return false;
  if (action !== 'view' && target.id === actor.id) return false;
  if (action === 'view') {
    return actor.id === target.id || isWithinTerritory(actor, target);
  }
  return rank[target.role] < rank[actor.role] && isWithinTerritory(actor, target);
}

/** Autoriza la creación de una cuenta en el ámbito y rol propuestos. */
export function canCreateUser(actor: User, proposed: Assignment): boolean {
  return canAssignRole(actor, proposed.role) && isWithinTerritory(actor, proposed);
}

/** Autoriza editar una cuenta y también su asignación de destino. */
export function canUpdateUser(
  actor: User,
  existing: User,
  proposed: Assignment,
): boolean {
  return canActOnUser(actor, existing, 'edit') &&
    canAssignRole(actor, proposed.role) && isWithinTerritory(actor, proposed);
}
