
import './Header.css';

interface HeaderProps {
  title: string;
  subtitle?: string;
  username?: string;
  role?: string;
}

function Header({
  title,
  subtitle = 'Monitoreo de góndolas',
  username = 'Usuario REGOVA',
  role = 'Operador',
}: HeaderProps) {
  return (
    <header className="regova-header">
      {/* IDENTIFICACIÓN DE LA SECCIÓN */}
      <div className="regova-header-heading">
        <span className="regova-header-eyebrow">
          REGOVA / PANEL DE CONTROL
        </span>

        <h1 className="regova-header-title">
          {title}
        </h1>

        <p className="regova-header-subtitle">
          {subtitle}
        </p>
      </div>

      {/* INFORMACIÓN DEL USUARIO */}
      <div className="regova-header-user">
        <div
          className="regova-header-avatar"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            width="23"
            height="23"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="8" r="4" />
            <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
          </svg>
        </div>

        <div className="regova-header-user-info">
          <strong>{username}</strong>
          <span>{role}</span>
        </div>
      </div>
    </header>
  );
}

export default Header;
