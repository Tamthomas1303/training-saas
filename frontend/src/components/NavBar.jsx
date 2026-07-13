import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { nav } from '../pages/listPageStyles'

export default function NavBar() {
  const { user, logout } = useAuth()

  return (
    <div style={{ ...nav, alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={nav}>
        <Link to="/">Trang chủ</Link>
        <Link to="/restaurants">Nhà hàng</Link>
        <Link to="/employees">Nhân sự</Link>
        <Link to="/checklist">Checklist</Link>
      </div>
      <div>
        <span style={{ marginRight: 12 }}>{user?.full_name || user?.username}</span>
        <button onClick={logout}>Đăng xuất</button>
      </div>
    </div>
  )
}
