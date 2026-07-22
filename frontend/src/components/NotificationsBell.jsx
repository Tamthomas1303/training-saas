import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'

export default function NotificationsBell() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  async function load() {
    try {
      const { data } = await api.get('/sourcing/notifications/')
      setItems(data.items || [])
      setUnread(data.unread || 0)
    } catch {
      /* im lặng — thông báo không phải chức năng cốt lõi */
    }
  }
  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  async function markAll() {
    await api.post('/sourcing/notifications/', { all: true })
    load()
  }
  async function openItem(n) {
    if (!n.is_read) {
      await api.post('/sourcing/notifications/', { id: n.id })
    }
    setOpen(false)
    load()
    if (n.link) navigate(n.link)
  }

  return (
    <span ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <span
        className="bell"
        title="Thông báo"
        style={{ cursor: 'pointer', position: 'relative' }}
        onClick={() => setOpen((v) => !v)}
      >
        🔔
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: -6, right: -8, background: 'var(--danger)', color: '#fff',
            borderRadius: 10, fontSize: 10, minWidth: 16, height: 16, lineHeight: '16px',
            textAlign: 'center', padding: '0 3px', fontWeight: 700,
          }}>{unread > 9 ? '9+' : unread}</span>
        )}
      </span>
      {open && (
        <div style={{
          position: 'absolute', right: 0, top: 28, width: 320, maxHeight: 420, overflow: 'auto',
          background: 'var(--card-bg, #fff)', border: '1px solid var(--card-border)', borderRadius: 8,
          boxShadow: '0 8px 24px rgba(0,0,0,0.15)', zIndex: 1000,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', borderBottom: '1px solid var(--card-border)' }}>
            <b>Thông báo</b>
            {unread > 0 && <button className="btn-outline btn-sm" onClick={markAll}>Đọc hết</button>}
          </div>
          {items.length === 0 && <div className="muted-note" style={{ padding: 12 }}>Chưa có thông báo.</div>}
          {items.map((n) => (
            <div
              key={n.id}
              onClick={() => openItem(n)}
              style={{
                padding: '8px 10px', borderBottom: '1px solid var(--card-border)', cursor: 'pointer',
                background: n.is_read ? 'transparent' : 'var(--badge-mint-bg, rgba(0,128,0,0.06))',
              }}
            >
              <div style={{ fontWeight: n.is_read ? 400 : 700, fontSize: 14 }}>{n.title}</div>
              {n.body && <div className="muted-note" style={{ fontSize: 12 }}>{n.body}</div>}
              <div className="muted-note" style={{ fontSize: 11 }}>{new Date(n.created_at).toLocaleString('vi-VN')}</div>
            </div>
          ))}
        </div>
      )}
    </span>
  )
}
