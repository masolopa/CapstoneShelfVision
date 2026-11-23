import RegovaLogo from '../../assets/logos/RegovaLogo';
import type { User } from '../../services/auth';
import { canAccess, type Section } from '../../services/permissions';
import './Sidebar.css';

const menuItems: { id: Section; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Panorama general', icon: '⌂' },
  { id: 'analysis', label: 'Análisis de góndola', icon: '▥' },
  { id: 'history', label: 'Reportes', icon: '◷' },
  { id: 'alerts', label: 'Estado y alertas', icon: '♧' },
  { id: 'settings', label: 'Configuración', icon: '⚙' },
  { id: 'users', label: 'Gestión de usuarios', icon: '♙' },
];
export type SidebarSection = Section;
interface SidebarProps {
  activeSection: SidebarSection;
  onNavigate: (section: SidebarSection) => void;
  currentUser: User;
  onLogout: () => void;
}
export default function Sidebar({ activeSection, onNavigate, currentUser, onLogout }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <RegovaLogo size={52} />
        <div className="sidebar-brand-text"><strong>REGOVA</strong><span>Góndolas inteligentes</span></div>
      </div>
      <nav className="sidebar-navigation" aria-label="Navegación principal">
        {menuItems.filter(item => canAccess(currentUser.role, item.id)).map(item => (
          <button key={item.id} type="button" className={`sidebar-link ${activeSection === item.id ? 'active' : ''}`}
            aria-current={activeSection === item.id ? 'page' : undefined} onClick={() => onNavigate(item.id)}>
            <span className="sidebar-link-icon" aria-hidden="true">{item.icon}</span>
            <span className="sidebar-link-label">{item.label}</span>
          </button>
        ))}
      </nav>
      <footer className="sidebar-footer">
        <div className="sidebar-footer-line" />
        <div style={{ padding: '12px 0', display: 'flex', flexDirection: 'column', gap: 5 }}>
          <strong style={{ fontSize: 13, color: '#fff' }}>{currentUser.name}</strong>
          <span style={{ fontSize: 12, opacity: .75 }}>{currentUser.id}</span>
          <button type="button" onClick={onLogout} style={{ marginTop: 8, padding: '9px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,.28)', background: 'rgba(255,255,255,.08)', color: '#fff', cursor: 'pointer', textAlign: 'left', font: 'inherit', fontSize: 13 }}>↪ Cerrar sesión</button>
        </div>
        <span>REGOVA v1.0</span><p>Más disponibilidad, menos quiebres.</p>
      </footer>
    </aside>
  );
}