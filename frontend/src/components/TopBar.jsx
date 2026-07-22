import { Link, useLocation } from 'react-router-dom'
import HeaderSearch from './HeaderSearch'
import NotificationsBell from './NotificationsBell'
import OfflineBadge from './OfflineBadge'
import UserMenu from './UserMenu'

export default function TopBar({ menu, user, onLogout }) {
  const location = useLocation()
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/dashboard" className="topbar-brand">
          Training System Manager
        </Link>
        <nav className="topbar-nav">
          {menu.map((item) => (
            <Link
              key={item.key}
              to={item.path}
              className={`nav-link${location.pathname === item.path ? ' active' : ''}`}
            >
              <span className="nav-link-icon">{item.icon}</span> {item.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-actions">
          <HeaderSearch />
          <OfflineBadge />
          <NotificationsBell />
          <UserMenu />
          <button className="btn-outline btn-sm" onClick={onLogout}>
            Đăng xuất
          </button>
        </div>
      </div>
    </header>
  )
}
