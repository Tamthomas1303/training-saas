export default function StatCard({ label, value, amber, icon, children }) {
  return (
    <div className="card stat-card">
      <div className="stat-card-head">
        <div className="stat-label">{label}</div>
        {icon && <span className="stat-icon">{icon}</span>}
      </div>
      <div className={`stat-num${amber ? ' amber' : ''}`}>{value}</div>
      {children}
    </div>
  )
}
