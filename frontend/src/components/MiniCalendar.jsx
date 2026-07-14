export default function MiniCalendar() {
  const today = new Date()
  const year = today.getFullYear()
  const month = today.getMonth()
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div className="card">
      <div className="stat-label" style={{ marginBottom: 8 }}>
        Tháng {month + 1}/{year}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, fontSize: 12 }}>
        {['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'].map((d) => (
          <div key={d} className="muted-note" style={{ textAlign: 'center' }}>
            {d}
          </div>
        ))}
        {cells.map((d, i) => (
          <div
            key={i}
            style={{
              textAlign: 'center',
              padding: '4px 0',
              borderRadius: 999,
              background: d === today.getDate() ? 'var(--forest)' : 'transparent',
              color: d === today.getDate() ? '#fff' : 'var(--text)',
            }}
          >
            {d || ''}
          </div>
        ))}
      </div>
    </div>
  )
}
