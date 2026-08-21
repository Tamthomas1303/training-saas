import Sparkline from './Sparkline'

// color: 'green'|'yellow'|'red'|'pending' (Dashboard Phan B - to mau theo nguong DashboardIndicator,
// xem indicator_color). Uu tien hon amber neu ca 2 cung truyen.
//
// UI dot 2 (Prompt_UI_Dot2_ConsoleAdmin.md muc C) them 4 prop MOI: delta (so), deltaGood (bool -
// mac dinh: delta>=0 la tot; truyen false/true rieng cho chi so "giam la tot" nhu nghi viec),
// trend (mang so cho sparkline), trendColor (mac dinh '--brand'). CHI kich hoat bo cuc "the tich
// hop" (icon trong o brand-soft + mui ten + sparkline) khi delta HOAC trend duoc truyen - KHONG
// truyen gi moi thi render Y HET nhu truoc. Bat buoc phai vay: component nay dung chung ca o man
// van hanh mobile (HomePage.jsx) - cac man do KHONG duoc doi bo cuc (chi nhan theme dot 1), va
// KHONG truyen delta/trend nen se tu dong giu nguyen giao dien cu, khong can sua HomePage.jsx.
export default function StatCard({
  label, value, amber, color, icon, children, delta, deltaGood, trend, trendColor = 'var(--brand)',
}) {
  const statusClass = color ? `status-${color}` : amber ? 'amber' : ''
  const hasDelta = delta !== undefined && delta !== null
  const hasTrend = Array.isArray(trend) && trend.length >= 2
  const enhanced = hasDelta || hasTrend

  if (!enhanced) {
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

  const isUp = hasDelta ? delta >= 0 : null
  const isGood = hasDelta ? (deltaGood ?? isUp) : null

  return (
    <div className="card stat-card stat-card-v2">
      <div className="stat-card-v2-head">
        {icon && <span className="stat-icon-box">{icon}</span>}
        <div className="stat-label">{label}</div>
      </div>
      <div className="stat-card-v2-num-row">
        <div className={`stat-num${statusClass ? ` ${statusClass}` : ''}`}>{value}</div>
        {hasDelta && (
          <span className={`stat-delta${isGood ? ' good' : ' bad'}`}>
            {isUp ? '▲' : '▼'} {Math.abs(delta)}%
          </span>
        )}
      </div>
      {hasDelta && <div className="stat-caption">so kỳ trước</div>}
      {children}
      {hasTrend && (
        <div className="stat-sparkline">
          <Sparkline data={trend} color={trendColor} />
        </div>
      )}
    </div>
  )
}
