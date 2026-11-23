import { useState, type FormEvent } from 'react';
import './Login.css';
import { apiJson, jsonBody } from '../../services/http';
import RegovaLogo from '../../assets/logos/RegovaLogo';
import { signIn, type User } from '../../services/auth';

interface LoginProps { onLogin: (user: User) => void }

export default function Login({ onLogin }: LoginProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [username, setUsername] = useState('ADM-001');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [token] = useState(() => { const match = window.location.hash.match(/^#recuperar=([A-Za-z0-9_-]+)$/); return match?.[1] ?? ''; });
  const [mode, setMode] = useState<'login' | 'recover' | 'reset'>(() => token ? 'reset' : 'login');
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  async function recover(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true);
    try {
      if (mode === 'recover') {
        const result = await apiJson<{message: string}>('/api/auth/recovery', jsonBody({ email: recoveryEmail })); setNotice(result.message);
      } else {
        if (newPassword !== confirmation) throw new Error('Las contraseñas no coinciden.');
        await apiJson<void>('/api/auth/reset-password', jsonBody({ token, password: newPassword }));
        window.history.replaceState(null, '', window.location.pathname + window.location.search); setPassword(''); setNewPassword(''); setConfirmation(''); setMode('login'); setNotice('Contraseña actualizada. Inicia sesión con tu nueva contraseña.');
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'No se pudo completar la solicitud.'); }
    finally { setBusy(false); }
  }


  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    try { const user = await signIn(username, password); onLogin(user); }
    catch (e) { setError(e instanceof Error ? e.message : 'No se pudo iniciar sesión.'); }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-hud" aria-hidden="true">
          <span className="hud-corner hud-top-left" />
          <span className="hud-corner hud-top-right" />
          <span className="hud-corner hud-bottom-left" />
          <span className="hud-corner hud-bottom-right" />
        </div>
        <header className="login-header">
          <div className="login-brand">
            <span className="login-brand-icon" aria-hidden="true"><RegovaLogo size={76} /></span>
            <div><h1 id="login-title">REGOVA</h1><p>Góndolas inteligentes</p></div>
          </div>
        </header>
        {notice && <p className="login-notice" role="status">{notice}</p>}
        {mode === 'login' ? <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-field">
            <span>Usuario o correo electrónico</span>
            <input type="text" name="username" autoComplete="username" placeholder="Usuario o correo electrónico" value={username} onChange={event => setUsername(event.target.value)} required />
          </label>
          <label className="login-field">
            <span>Contraseña</span>
            <span className="login-password-wrapper">
              <input type={showPassword ? 'text' : 'password'} name="password" autoComplete="current-password" placeholder="Contraseña" value={password} onChange={event => setPassword(event.target.value)} required />
              <button type="button" className="login-password-toggle" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? 'Ocultar' : 'Mostrar'}</button>
            </span>
          </label>
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="login-submit" type="submit"><span className="login-submit-label">Iniciar sesión</span><span className="login-submit-arrow" aria-hidden="true">→</span></button>
          <button type="button" className="login-recovery-link" onClick={() => { setMode('recover'); setError(''); setNotice(''); }}>¿Olvidaste tus datos de acceso?</button>
        </form> : <form className="login-form" onSubmit={recover}>
          <h2>{mode === 'recover' ? 'Recuperar acceso' : 'Crear nueva contraseña'}</h2>
          {mode === 'recover' ? <>
            <p>Ingresa el correo registrado en tu cuenta. Te enviaremos tu ID y un enlace para cambiar la contraseña.</p>
            <label className="login-field"><span>Correo electrónico</span><input type="email" autoComplete="email" required maxLength={254} value={recoveryEmail} onChange={e => setRecoveryEmail(e.target.value)} /></label>
          </> : <>
            <label className="login-field"><span>Nueva contraseña</span><input type="password" autoComplete="new-password" minLength={10} maxLength={256} required value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label>
            <label className="login-field"><span>Confirmar contraseña</span><input type="password" autoComplete="new-password" minLength={10} maxLength={256} required value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>
          </>}
          {error && <p className="login-error" role="alert">{error}</p>}
          <button type="submit" className="login-submit" disabled={busy}>{busy ? 'Procesando…' : mode === 'recover' ? 'Enviar instrucciones' : 'Guardar contraseña'}</button>
          <button type="button" className="login-recovery-link" disabled={busy} onClick={() => { setMode('login'); setError(''); setNotice(''); }}>Volver a iniciar sesión</button>
        </form>}
        <div className="login-system-status" aria-hidden="true"><span className="login-status-dot" /><span>REGOVA / ACCESO AL SISTEMA</span><span className="login-status-line" /><span>01</span></div>
        <footer className="login-footer">REGOVA v1.0</footer>
      </section>
    </main>
  );
}
