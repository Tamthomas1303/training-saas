import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import HeaderSearch from './HeaderSearch'
import NotificationsBell from './NotificationsBell'
import OfflineBadge from './OfflineBadge'
import UserMenu from './UserMenu'

// UI dot 1 (Prompt_UI_Dot1_Theme.md muc 3c): ten he thong doc tu cau hinh thuong hieu (tenant),
// KHONG con hardcode "Training System Manager" - fallback ve chuoi cu neu tenant chua cau hinh.
export default function TopBar({ menu, user, onLogout }) {
  const location = useLocation()
  const { brand } = useAuth()
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/dashboard" className="topbar-brand" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {brand?.logo_url && <img src={brand.logo_url} alt="" style={{ height: 24, width: 'auto' }} />}
          {brand?.system_name || 'Training System Manager'}
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
