import { Link, useLocation } from 'react-router-dom'

export default function BottomNav({ menu }) {
  const location = useLocation()
  return (
    <nav className="bottom-nav">
      {menu.map((item) => (
        <Link
          key={item.key}
          to={item.path}
          className={`bottom-nav-item${location.pathname === item.path ? ' active' : ''}`}
        >
          <span className="bottom-nav-icon">{item.icon}</span>
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
  )
}
