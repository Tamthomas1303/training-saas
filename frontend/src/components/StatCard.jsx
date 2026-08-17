// color: 'green'|'yellow'|'red'|'pending' (Dashboard Phan B - to mau theo nguong DashboardIndicator,
// xem indicator_color). Uu tien hon amber neu ca 2 cung truyen.
export default function StatCard({ label, value, amber, color, icon, children }) {
  const statusClass = color ? `status-${color}` : amber ? 'amber' : ''
  return (
    <div className="card stat-card">
      <div className="stat-card-head">
        <div className="stat-label">{label}</div>
        {icon && <span className="stat-icon">{icon}</span>}
      </div>
      <div className={`stat-num${statusClass ? ` ${statusClass}` : ''}`}>{value}</div>
      {children}
    </div>
  )
}
