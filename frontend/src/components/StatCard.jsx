export default function StatCard({ label, value, amber, children }) {
  return (
    <div className="card">
      <div className="stat-label">{label}</div>
      <div className={`stat-num${amber ? ' amber' : ''}`}>{value}</div>
      {children}
    </div>
  )
}
