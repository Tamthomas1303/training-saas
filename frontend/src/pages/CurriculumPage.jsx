import { useEffect, useMemo, useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

// Khung noi dung dao tao cap O - Buoc 1 (Prompt_KhungNoiDung_CapO_Buoc1.md). Chi Admin vao duoc
// man nay (xem App.jsx::ProtectedRoute). Cap S (checklist core/completion) CHUA lam o buoc nay.
const O_POSITIONS = [
  { value: 'qlnh', label: 'Quản lý nhà hàng' },
  { value: 'giam_sat', label: 'Giám sát' },
  { value: 'bep_truong', label: 'Bếp trưởng' },
  { value: 'bep_pho', label: 'Bếp phó' },
]

function DocumentPickerModal({ open, title, onClose, onConfirm, confirmLabel, extraContent, confirmDisabled }) {
  const [documents, setDocuments] = useState([])
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [selected, setSelected] = useState([])

  useEffect(() => {
    if (!open) return
    api.get('/checklist/documents/', { params: { page_size: 500 } })
      .then(({ data }) => setDocuments(data.results || []))
      .catch(() => setDocuments([]))
    setSelected([])
    setSearch('')
    setCategory('')
  }, [open])

  const categories = useMemo(
    () => [...new Set(documents.map((d) => d.category).filter(Boolean))],
    [documents]
  )
  const filtered = documents.filter((d) => {
    if (category && d.category !== category) return false
    if (search && !d.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  function toggle(id) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <button className="btn-outline" onClick={onClose}>Hủy</button>
          <button onClick={() => onConfirm(selected)} disabled={selected.length === 0 || confirmDisabled}>
            {confirmLabel} ({selected.length})
          </button>
        </>
      }
    >
      {extraContent}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <input
          style={s.input} placeholder="Tìm theo tên tài liệu..."
          value={search} onChange={(e) => setSearch(e.target.value)}
        />
        <select style={s.select} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Tất cả nhóm</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid var(--card-border)', borderRadius: 6 }}>
        {filtered.map((d) => (
          <label key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderBottom: '1px solid var(--card-border)' }}>
            <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
            <span style={{ flex: 1 }}>{d.name}</span>
            {d.category && <span className="muted-note" style={{ fontSize: 12 }}>{d.category}</span>}
          </label>
        ))}
        {filtered.length === 0 && <div className="muted-note" style={{ padding: 10 }}>Không có tài liệu phù hợp.</div>}
      </div>
    </Modal>
  )
}

export default function CurriculumPage() {
  const [position, setPosition] = useState(O_POSITIONS[0].value)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [sharedOpen, setSharedOpen] = useState(false)
  const [sharedPositions, setSharedPositions] = useState([])

  function load() {
    setLoading(true)
    setError('')
    api.get('/curriculum/', { params: { position } })
      .then(({ data }) => setItems(data.results || data || []))
      .catch(() => setError('Không tải được khung nội dung.'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [position])

  async function addToPosition(documentIds) {
    setMsg('')
    try {
      const { data } = await api.post('/curriculum/bulk/', {
        document_ids: documentIds, positions: [position], is_shared: false,
      })
      setAddOpen(false)
      setMsg(`Đã thêm ${data.created} nội dung.`)
      load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Không thêm được nội dung.')
    }
  }

  async function assignShared(documentIds) {
    setMsg('')
    if (sharedPositions.length === 0) {
      setMsg('Chọn ít nhất 1 vị trí để gán nội dung chung.')
      return
    }
    try {
      const { data } = await api.post('/curriculum/bulk/', {
        document_ids: documentIds, positions: sharedPositions, is_shared: true,
      })
      setSharedOpen(false)
      setMsg(`Đã gán nội dung chung cho ${sharedPositions.length} vị trí (${data.created} dòng mới).`)
      load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Không gán được nội dung chung.')
    }
  }

  async function removeItem(item) {
    if (!window.confirm(`Gỡ "${item.document_name}" khỏi khung?`)) return
    await api.delete(`/curriculum/${item.id}/`)
    load()
  }

  async function move(item, direction) {
    const idx = items.findIndex((i) => i.id === item.id)
    const swapIdx = idx + direction
    if (swapIdx < 0 || swapIdx >= items.length) return
    const other = items[swapIdx]
    await Promise.all([
      api.patch(`/curriculum/${item.id}/`, { order: other.order }),
      api.patch(`/curriculum/${other.id}/`, { order: item.order }),
    ])
    load()
  }

  function toggleSharedPosition(value) {
    setSharedPositions((prev) => (prev.includes(value) ? prev.filter((x) => x !== value) : [...prev, value]))
  }

  return (
    <AppShell>
      <h2>Khung nội dung đào tạo (cấp O)</h2>
      <p className="muted-note">
        Nội dung lấy từ thư viện Tài liệu, gán theo vị trí quản lý bằng tích chọn tay. Vị trí chưa
        cấu hình khung sẽ tạm dùng danh sách mặc định của hệ thống cho "Điều kiện tiên quyết".
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {O_POSITIONS.map((p) => (
          <button
            key={p.value}
            className={`btn-sm ${position === p.value ? '' : 'btn-outline'}`}
            onClick={() => setPosition(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>
          Nội dung của: {O_POSITIONS.find((p) => p.value === position)?.label}
        </h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-outline btn-sm" onClick={() => { setSharedPositions([]); setSharedOpen(true) }}>+ Gán nội dung chung</button>
          <button onClick={() => setAddOpen(true)}>+ Thêm nội dung</button>
        </div>
      </div>

      {msg && <p className="muted-note">{msg}</p>}
      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <Table>
          <thead>
            <tr>
              <th>Thứ tự</th>
              <th>Tài liệu</th>
              <th>Nhóm</th>
              <th></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr key={item.id}>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn-outline btn-sm" disabled={idx === 0} onClick={() => move(item, -1)}>↑</button>
                    <button className="btn-outline btn-sm" disabled={idx === items.length - 1} onClick={() => move(item, 1)}>↓</button>
                  </div>
                </td>
                <td>
                  {item.document_file_url ? (
                    <a href={item.document_file_url} target="_blank" rel="noreferrer">{item.document_name}</a>
                  ) : item.document_name}
                </td>
                <td>{item.document_category}</td>
                <td>{item.is_shared && <Badge variant="neutral">Chung</Badge>}</td>
                <td>
                  <button className="btn-danger btn-sm" onClick={() => removeItem(item)}>Gỡ</button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="muted-note">Chưa có nội dung nào trong khung — dùng danh sách mặc định của hệ thống.</td>
              </tr>
            )}
          </tbody>
        </Table>
      )}

      <DocumentPickerModal
        open={addOpen}
        title={`Thêm nội dung cho ${O_POSITIONS.find((p) => p.value === position)?.label}`}
        onClose={() => setAddOpen(false)}
        onConfirm={addToPosition}
        confirmLabel="Thêm"
      />

      <DocumentPickerModal
        open={sharedOpen}
        title="Gán nội dung chung cho nhiều vị trí"
        onClose={() => setSharedOpen(false)}
        onConfirm={assignShared}
        confirmLabel="Gán chung"
        confirmDisabled={sharedPositions.length === 0}
        extraContent={
          <div style={{ marginBottom: 10 }}>
            <div style={{ marginBottom: 6, fontSize: 13, fontWeight: 'bold' }}>Áp dụng cho vị trí</div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {O_POSITIONS.map((p) => (
                <label key={p.value} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={sharedPositions.includes(p.value)}
                    onChange={() => toggleSharedPosition(p.value)}
                  />
                  {p.label}
                </label>
              ))}
            </div>
          </div>
        }
      />
    </AppShell>
  )
}
