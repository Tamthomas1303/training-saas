import { Link, useLocation } from 'react-router-dom'
import OfflineBadge from './OfflineBadge'

export default function TopBar({ menu, user, onLogout }) {
  const location = useLocation()
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="topbar-brand">Training System Manager</div>
        <nav className="topbar-nav">
          {menu.map((item) => (
            <Link
              key={item.key}
              to={item.path}
              className={`nav-link${location.pathname === item.path ? ' active' : ''}`}
            >
              <span>{item.icon}</span> {item.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-actions">
          <OfflineBadge />
          <span className="bell" title="Thông báo">
            🔔
          </span>
          <span className="topbar-user">{user?.full_name || user?.username}</span>
          <button className="btn-outline btn-sm" onClick={onLogout}>
            Đăng xuất
          </button>
        </div>
      </div>
    </header>
  )
}
