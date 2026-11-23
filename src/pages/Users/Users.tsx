import { MVP_BRANCH, MVP_BRANCH_LABEL, MVP_ROLES } from '../../services/mvpLocal';
import { useEffect, useState, type FormEvent } from 'react';
import { createUser, deleteUser, listUserActivity, listUsers, updateUser, type User, type UserActivity } from '../../services/auth';
import { hasPermission, roleLabels, type Role } from '../../services/permissions';
import { canActOnUser, canAssignRole, canCreateUser, canUpdateUser } from '../../services/userAccess';
import './Users.css';
import { apiJson, jsonBody } from '../../services/http';

const roles: Role[] = [...MVP_ROLES];
type UserDraft = Pick<User, 'role' | 'scope' | 'branch' | 'active'> & { email?: string };

function displayLocation(value: string): string { void value; return MVP_BRANCH_LABEL; }
function isValidAssignment(scope: string, branch: string): boolean {
  return scope === 'local' && branch === MVP_BRANCH;
}
function LocationFields() {
  return <p className="users-hint">Local: {MVP_BRANCH_LABEL}</p>;
}

export default function Users({ currentUser }: { currentUser: User }) {
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [ownEmail, setOwnEmail] = useState(currentUser.email ?? '');
  const [ownPassword, setOwnPassword] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>('reponedor');
  const [scope] = useState('local');
  const [branch] = useState(MVP_BRANCH);
  const [message, setMessage] = useState('');
  const [deleting, setDeleting] = useState<User | null>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<UserDraft | null>(null);

  const canView = hasPermission(currentUser.role, 'users.view');
  const canCreate = hasPermission(currentUser.role, 'users.create');
  const canEdit = hasPermission(currentUser.role, 'users.edit');
  const canSuspend = hasPermission(currentUser.role, 'users.suspend');
  const canDelete = hasPermission(currentUser.role, 'users.delete');
  const [activity, setActivity] = useState<UserActivity[]>([]);
  const refresh = async () => { const [next, events] = await Promise.all([listUsers(), listUserActivity()]); setUsers(next); setActivity(events); };
  useEffect(() => { let active = true; Promise.all([listUsers(), listUserActivity()]).then(([next, events]) => { if (active) { setUsers(next); setActivity(events); } }).catch(e => { if (active) setMessage(e.message); }); return () => { active = false; }; }, []);
  const assignableRoles = roles.filter(r => canAssignRole(currentUser, r));
  const visibleUsers = users.filter(u => (u.id === 'ADM-001' || (u.scope === 'local' && u.branch === MVP_BRANCH)) && canActOnUser(currentUser, u, 'view'));
  const canCreateHere = canCreate && assignableRoles.length > 0;


  // La interfaz refleja los permisos; FastAPI vuelve a comprobar cada operación.
  if (!canView) {
    return (
      <div className="users-page">
        <section className="users-card">
          <h2>Acceso restringido</h2>
          <p>No tienes permisos para consultar la administración de cuentas.</p>
        </section>
      </div>
    );
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) { setMessage('No tienes permiso para crear cuentas.'); return; }
    if (role === 'admin_principal') {
      setMessage('La cuenta de administrador principal es única en esta demostración.');
      return;
    }
    if (!canCreateUser(currentUser, { role, scope, branch })) {
      setMessage('Tu jerarquía o territorio no permite crear esa cuenta.'); return;
    }
    if (!isValidAssignment(scope, branch)) {
      setMessage('Selecciona una región o sucursal válida del catálogo.'); return;
    }
    try {
      const created = await createUser({ name, email, password, role, scope, branch }, currentUser.id);
      setMessage(`Cuenta ${created.id} creada. Puede iniciar sesión con su ID o con el correo registrado y la contraseña indicada.`);
      setName(''); setEmail(''); setPassword(''); await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo crear la cuenta.');
    }
  }

  function beginEdit(user: User) {
    if (!canEdit || !canActOnUser(currentUser, user, 'edit')) {
      setMessage('No tienes permiso para modificar esta cuenta.');
      return;
    }
    setEditing(user.id);
    setDraft({ role: user.role, scope: 'local', branch: MVP_BRANCH, active: user.active, email: user.email ?? '' });
    setMessage('');
  }

  async function saveEdit(id: string) {
    if (!draft) return;
    const original = users.find(u => u.id === id);
    if (!canEdit || !original || !canUpdateUser(currentUser, original, draft)) {
      setMessage('No tienes permiso para realizar esta modificación.');
      return;
    }
    if (!isValidAssignment(draft.scope, draft.branch)) {
      setMessage('Selecciona una ubicación válida del catálogo antes de guardar.'); return;
    }
    try {
      await updateUser(id, draft, currentUser.id);
      setEditing(null); setDraft(null); await refresh();
      setMessage(`Cuenta ${id} actualizada.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo guardar.');
    }
  }

  async function toggle(user: User) {
    if (!canSuspend || !canActOnUser(currentUser, user, 'suspend')) {
      setMessage('No tienes permiso para cambiar el estado de esta cuenta.');
      return;
    }
    if (user.id === currentUser.id) {
      setMessage('No puedes suspender tu propia sesión.');
      return;
    }
    try {
      await updateUser(user.id, {
        role: user.role, scope: user.scope, branch: user.branch, active: !user.active,
      }, currentUser.id);
      await refresh();
      setMessage(`Cuenta ${user.id} ${user.active ? 'suspendida' : 'reactivada'}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo actualizar.');
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    const target = users.find(u => u.id === deleting.id);
    if (!target || !canDelete || !canActOnUser(currentUser, target, 'delete')) {
      setMessage('No tienes permiso para eliminar esta cuenta.');
      setDeleting(null);
      return;
    }
    try {
      await deleteUser(target.id, currentUser.id);
      setDeleting(null); await refresh();
      setMessage(`Cuenta ${target.id} eliminada. Se conservó el registro de auditoría.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No se pudo eliminar la cuenta.');
    }
  }

  return (
    <div className="users-page">
      <div className="users-intro">
        <div>
          <h2>Administración de cuentas</h2>
          <p>Gestiona las cuentas y los permisos de tu equipo.</p>
        </div>
        <span className="users-demo">CUENTAS DEL LOCAL</span>
      </div>

      <section className="users-card">
        <h3>Mi correo de recuperación</h3>
        <form className="users-form" onSubmit={async e => { e.preventDefault(); try { await apiJson<void>('/api/auth/email', jsonBody({ email: ownEmail, password: ownPassword }, 'PUT')); setOwnPassword(''); setMessage('Correo de recuperación actualizado.'); await refresh(); } catch (error) { setMessage(error instanceof Error ? error.message : 'No se pudo guardar el correo.'); } }}>
          <label>Mi correo electrónico<input name="admin-recovery-email" autoComplete="off" type="email" required maxLength={254} value={ownEmail} onChange={e => setOwnEmail(e.target.value)} /></label>
          <label>Contraseña actual<input type="password" autoComplete="current-password" required value={ownPassword} onChange={e => setOwnPassword(e.target.value)} /></label>
          <button type="submit" className="users-primary">Guardar mi correo</button>
        </form>
      </section>
      <div className="users-stats">
        <div><strong>{visibleUsers.length}</strong><span>Cuentas registradas</span></div>
        <div><strong>{visibleUsers.filter(u => u.active).length}</strong><span>Activas</span></div>
        <div><strong>{visibleUsers.filter(u => !u.active).length}</strong><span>Suspendidas</span></div>
      </div>

      {canCreateHere && (
        <section className="users-card">
          <h3>Crear cuenta</h3>
          <form onSubmit={create} className="users-form" autoComplete="off">
            <label>Nombre del trabajador
              <input name="worker-name" autoComplete="off" value={name} onChange={e => setName(e.target.value)} required placeholder="Nombre y apellido" />
            </label>
            <label>Correo electrónico del trabajador
              <input name="worker-email" autoComplete="off" aria-describedby="worker-email-help" type="email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} placeholder="Correo indicado por el trabajador" />
              <small id="worker-email-help">Se asociará a esta cuenta para iniciar sesión y recuperar sus datos de acceso.</small>
            </label>
            <label>Contraseña temporal
              <input name="worker-initial-password" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)}
                required minLength={10} type="password" placeholder="Mínimo 10 caracteres" />
            </label>
            <label>Rol
              <select value={role} onChange={e => setRole(e.target.value as Role)}>
                {assignableRoles.map(r =>
                  <option key={r} value={r}>{roleLabels[r]}</option>
                )}
              </select>
            </label>
            <LocationFields />
            <button className="users-primary" type="submit">+ Crear cuenta</button>
          </form>
        </section>
      )}

      {message && <p className="users-message" role="status">{message}</p>}

      <section className="users-card">
        <h3>Usuarios registrados</h3>
        <p className="users-hint">
          Puedes editar, suspender o reactivar cuentas. La eliminación cierra el acceso y conserva un registro interno de auditoría.
        </p>
        <div className="users-table-wrap">
          <table className="users-table">
            <thead><tr>
              <th>Cuenta</th><th>Correo de recuperación</th><th>Rol</th><th>Ámbito</th>
              <th>Sucursal / región</th><th>Estado</th><th>Acciones</th>
            </tr></thead>
            <tbody>
              {visibleUsers.map(u => {
                const isEditing = editing === u.id && draft !== null;
                const canEditTarget = canEdit && canActOnUser(currentUser, u, 'edit');
                const canSuspendTarget = canSuspend && canActOnUser(currentUser, u, 'suspend');
                const canDeleteTarget = canDelete && canActOnUser(currentUser, u, 'delete');
                return (
                  <tr key={u.id}>
                    <td><strong>{u.name}</strong><small>{u.id}</small></td>
                    <td>{isEditing && draft ? <input type="email" aria-label={`Correo de ${u.id}`} value={draft.email ?? ''} onChange={e => setDraft({ ...draft, email: e.target.value })} maxLength={254} /> : (u.email || 'Sin correo registrado')}</td>
                    <td>{isEditing && draft
                      ? <select aria-label={`Rol de ${u.id}`} value={draft.role}
                          onChange={e => setDraft({ ...draft, role: e.target.value as Role })}>
                          {assignableRoles.map(r =>
                            <option key={r} value={r}>{roleLabels[r]}</option>
                          )}
                        </select>
                      : u.roleLabel}</td>
                    <td>Local</td>
                    <td>{displayLocation(u.branch)}</td>
                    <td><span className={`users-status ${u.active ? 'is-active' : 'is-inactive'}`}>
                      {u.active ? 'Activo' : 'Suspendido'}
                    </span></td>
                    <td>
                      <div className="users-actions">
                        {isEditing
                          ? <>
                              <button type="button" onClick={() => saveEdit(u.id)}>Guardar</button>
                              <button type="button" onClick={() => { setEditing(null); setDraft(null); }}>Cancelar</button>
                            </>
                          : <>
                              {canEditTarget && <button type="button"
                                onClick={() => beginEdit(u)}>Editar</button>}
                              {canSuspendTarget && <button type="button"
                                onClick={() => toggle(u)}>
                                {u.active ? 'Suspender' : 'Reactivar'}
                              </button>}
                              {canDeleteTarget && <button type="button" onClick={() => setDeleting(u)}>Eliminar</button>}
                              {!canEditTarget && !canSuspendTarget && !canDeleteTarget && <span>Solo lectura</span>}
                            </>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {deleting && <section className="users-card" role="alertdialog" aria-label="Confirmar eliminación de cuenta">
        <h3>Confirmar cierre definitivo de cuenta</h3>
        <p>¿Eliminar la cuenta <strong>{deleting.name} ({deleting.id})</strong>?
          Perderá acceso y desaparecerá del listado. Se conservará un registro interno de auditoría.
          Esta acción no puede deshacerse desde la interfaz.</p>
        <div className="users-actions">
          <button type="button" onClick={() => setDeleting(null)}>Cancelar</button>
          <button type="button" className="users-primary" onClick={confirmDelete}>Confirmar eliminación</button>
        </div>
      </section>}
      {currentUser.role === 'admin_principal' && <section className="users-card">
        <h3>Historial de administración de usuarios</h3>
        <button type="button" onClick={() => setShowAudit(!showAudit)}>
          {showAudit ? 'Ocultar auditoría' : 'Mostrar auditoría'}
        </button>
        {showAudit && <div className="users-table-wrap"><table className="users-table">
          <thead><tr><th>Cuenta</th><th>Rol</th><th>Acción</th><th>Fecha</th><th>Realizada por</th></tr></thead>
          <tbody>{activity.map((entry, index) =>
            <tr key={`${entry.id}-${index}`}>
              <td>{entry.name}<small>{entry.id}</small></td>
              <td>{roleLabels[entry.role]}</td>
              <td>{entry.action}</td>
              <td>{new Date(entry.timestamp).toLocaleString('es-CL')}</td>
              <td>{entry.actorId}</td>
            </tr>)}</tbody>
        </table></div>}
      </section>}
    </div>
  );
}
