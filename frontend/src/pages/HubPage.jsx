import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import { useAuth } from '../auth/AuthContext'
import { DOMAINS, visibleChildren } from '../config/domains'

// M3 — Trung tâm đào tạo: 4 miền cha (thẻ) → bấm mở ra thẻ con (Card Nesting).
export default function HubPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(null)

  const domains = DOMAINS.map((d) => ({ ...d, kids: visibleChildren(d, user?.role) }))

  return (
    <AppShell>
      <h2 style={{ marginTop: 0 }}>Trung tâm đào tạo</h2>
      <p className="muted-note" style={{ marginTop: -6 }}>Chọn một miền để mở các chức năng bên trong.</p>

      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
        {domains.map((d) => {
          const open = expanded === d.key
          const disabled = d.comingSoon || d.kids.length === 0
          return (
            <div
              key={d.key}
              className="card"
              style={{
                padding: 14, cursor: disabled ? 'default' : 'pointer',
                borderLeft: '4px solid var(--forest)', opacity: disabled ? 0.6 : 1,
                gridColumn: open ? '1 / -1' : 'auto',
                transition: 'grid-column 0.15s',
              }}
              onClick={() => { if (!disabled) setExpanded(open ? null : d.key) }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 26 }}>{d.icon}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>{d.title}</div>
                    <div className="muted-note" style={{ fontSize: 12 }}>{d.desc}</div>
                  </div>
                </div>
                {!disabled && <span style={{ fontSize: 18 }}>{open ? '▾' : '▸'}</span>}
                {d.comingSoon && <span className="badge badge-warning">Sắp có</span>}
              </div>

              {open && (
                <div
                  style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', marginTop: 12 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {d.kids.map((c) => (
                    <div
                      key={c.path + c.label}
                      className="card"
                      style={{ padding: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
                      onClick={() => navigate(c.path)}
                    >
                      <span style={{ fontSize: 18 }}>{c.icon}</span>
                      <span style={{ fontWeight: 600 }}>{c.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </AppShell>
  )
}
