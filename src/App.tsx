import { SessionContext } from './services/session';
import { useEffect, useState, useSyncExternalStore } from 'react';
import Login from './pages/Login/Login';
import { signOut, getSession, type User } from './services/auth';

import DashboardLayout from './layouts/DashboardLayout';

import Dashboard from './pages/Dashboard/Dashboard';
import Analysis from './pages/Analysis/Analysis';
import AnalysisFlow from './features/analysis/AnalysisFlow';
import Settings from './pages/Settings/Settings';
import Alerts from './pages/Analysis/Alerts';
import Users from './pages/Users/Users';
import { canAccess } from './services/permissions';

import type { SidebarSection } from './components/Sidebar/Sidebar';

const sectionTitles: Record<SidebarSection, string> = {
  dashboard: 'Panorama general',
  analysis: 'Análisis de góndola',
  history: 'Reportes',
  gondolas: 'Historial de análisis',
  alerts: 'Estado y alertas',
  review: 'Revisión de resultados',
  settings: 'Configuración',
  users: 'Gestión de usuarios',
};

function subscribeToNavigation(onChange: () => void) {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

function readSection(): SidebarSection {
  const section = window.location.hash.slice(1).replace(/^\//, '').split('?')[0];
  return Object.prototype.hasOwnProperty.call(sectionTitles, section)
    ? section as SidebarSection
    : 'dashboard';
}

function updateSection(section: SidebarSection) {
  window.location.hash = `/${section}`;
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [sessionError, setSessionError] = useState('');
  useEffect(() => {
    let active = true;
    getSession().then(value => { if (active) setUser(value); }).catch(() => {}).finally(() => { if (active) setChecking(false); });
    const expired = () => { setUser(null); setSessionError('Tu sesión terminó. Inicia sesión nuevamente.'); };
    window.addEventListener('regova:session-expired', expired);
    return () => { active = false; window.removeEventListener('regova:session-expired', expired); };
  }, []);
  const recoveryRequested = useSyncExternalStore(subscribeToNavigation, () => window.location.hash.startsWith('#recuperar='));
  const requestedSection = useSyncExternalStore(subscribeToNavigation, readSection);
  const activeSection = user && canAccess(user.role, requestedSection) ? requestedSection : 'dashboard';

  function navigate(section: SidebarSection) {
    if (user && canAccess(user.role, section)) updateSection(section);
  }

  function renderSection() {
    if (!user || !canAccess(user.role, activeSection)) return <p>No tienes permiso para acceder a esta sección.</p>;
    switch (activeSection) {
      case 'dashboard':
        return <Dashboard />;
      case 'analysis':
        return <Analysis />;
      case 'history':
      case 'gondolas':
        return <AnalysisFlow history />;
      case 'review':
        return <AnalysisFlow history review />;
      case 'alerts':
        return <Alerts user={user} />;
      case 'settings':
        return <Settings />;
      case 'users':
        return <Users currentUser={user} />;
      default:
        return <p>La sección {sectionTitles[activeSection]} está en construcción.</p>;
    }
  }

  async function logout() {
    try { await signOut(); } catch (e) { setSessionError(e instanceof Error ? e.message : 'No se pudo cerrar la sesión.'); return; }
    setUser(null);
    updateSection('dashboard');
  }

  if (checking) return <p role="status">Comprobando sesión…</p>;
  if (!user || recoveryRequested) return <>{sessionError && <p role="status">{sessionError}</p>}<Login onLogin={(nextUser) => { setUser(nextUser); setSessionError(''); updateSection('dashboard'); }} /></>;

  return (
    <SessionContext.Provider value={user}><DashboardLayout
      activeSection={activeSection}
      onNavigate={navigate}
      currentUser={user}
      onLogout={logout}
      title={sectionTitles[activeSection]}
      subtitle="Monitoreo de góndolas"
    >
      {sessionError && <p role="alert">{sessionError}</p>}
      {renderSection()}
    </DashboardLayout></SessionContext.Provider>
  );
}

export default App;
