/** Autenticación y cuentas administradas por FastAPI/PostgreSQL. */
import type { Role } from './permissions';
import { apiJson, jsonBody } from './http';
export type { Role } from './permissions';
export type User = { id: string; name: string; role: Role; roleLabel: string; scope: string; branch: string; active: boolean; email?: string };
export type UserActivity = { id: string; name: string; role: Role; action: string; timestamp: string; actorId: string };
export type NewUser = { name: string; role: Role; scope: string; branch: string; password: string; email?: string };
export const listUsers = () => apiJson<User[]>('/api/users');
export const listUserActivity = () => apiJson<UserActivity[]>('/api/users/activity');
export const signIn = (username: string, password: string) => apiJson<User>('/api/auth/login', jsonBody({ username, password }));
export const getSession = () => apiJson<User>('/api/auth/me');
export const signOut = () => apiJson<void>('/api/auth/logout', { method: 'POST' });
export const createUser = (input: NewUser, actorId: string) => {
  void actorId;
  return apiJson<User>('/api/users', jsonBody({ name: input.name, password: input.password, role: input.role, email: input.email }));
};
export const updateUser = (id: string, changes: Pick<User, 'role' | 'scope' | 'branch' | 'active'> & { email?: string }, actorId: string) => {
  void actorId;
  return apiJson<void>(`/api/users/${encodeURIComponent(id)}`, jsonBody({ role: changes.role, active: changes.active, email: changes.email }, 'PATCH'));
};
export const deleteUser = (id: string, actorId: string) => {
  void actorId;
  return apiJson<void>(`/api/users/${encodeURIComponent(id)}`, { method: 'DELETE' });
};
