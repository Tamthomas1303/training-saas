import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import BackButton from '../components/BackButton'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'

const CATEGORY = { common: 'Chung / Nền tảng', foh: 'FOH', boh: 'BOH', management: 'Quản lý' }
const EMPTY = { name: '', code: '', category: 'common', target_roles: '', is_prerequisite: false, is_active: true, note: '', order: 0 }

export default function TrainingCatalogPage() {
  const { user } = useAuth()
  const canManage = ['admin', 'om'].includes((user?.role || '').toLowerCase())
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(null)
  const [catFilter, setCatFilter] = useState('')

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get('/sourcing/training-contents/')
      setRows(data)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function save() {
    if (form.id) await api.patch(`/sourcing/training-contents/${form.id}/`, form)
    else await api.post('/sourcing/training-contents/', form)
    setForm(null); load()
  }
  async function del(r) {
    if (!window.confirm(`Xoá nội dung "${r.name}"?`)) return
    await api.delete(`/sourcing/training-contents/${r.id}/`)
    load()
  }

  const shown = catFilter ? rows.filter((r) => r.category === catFilter) : rows

  return (
    <AppShell>
      <BackButton />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Danh mục nội dung đào tạo</h2>
        {canManage && <button onClick={() => setForm({ ...EMPTY, order: rows.length + 1 })}>+ Thêm nội dung</button>}
      </div>
      <p className="muted-note" style={{ marginTop: 4 }}>Thêm/bớt nội dung đào tạo theo thay đổi vận hành. Dùng khi tạo chương trình/đợt đào tạo BQL.</p>

      <div style={{ margin: '8px 0' }}>
        <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)}>
          <option value="">Tất cả nhóm</option>
          {Object.entries(CATEGORY).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {loading ? <p className="muted-note">Đang tải...</p> : (
        <Table>
          <thead>
            <tr><th>Nội dung</th><th>Mã</th><th>Nhóm</th><th>Áp dụng vai</th><th>Tiên quyết</th><th>Trạng thái</th>{canManage && <th></th>}</tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td>{r.name}{r.note && <div className="muted-note" style={{ fontSize: 12 }}>{r.note}</div>}</td>
                <td>{r.code}</td>
                <td>{CATEGORY[r.category]}</td>
                <td>{r.target_roles}</td>
                <td>{r.is_prerequisite ? '✅' : ''}</td>
                <td>{r.is_active ? <Badge variant="success">Đang dùng</Badge> : <Badge variant="neutral">Ngừng</Badge>}</td>
                {canManage && (
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button className="btn-outline btn-sm" onClick={() => setForm(r)}>Sửa</button>
                    <button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => del(r)}>Xoá</button>
                  </td>
                )}
              </tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={canManage ? 7 : 6} className="muted-note">Chưa có nội dung nào.</td></tr>}
          </tbody>
        </Table>
      )}

      {form && (
        <Modal open title={form.id ? 'Sửa nội dung' : 'Thêm nội dung'} onClose={() => setForm(null)}
          footer={<><button className="btn-outline" onClick={() => setForm(null)}>Hủy</button><button onClick={save}>Lưu</button></>}>
          <div style={{ display: 'grid', gap: 10 }}>
            <label>Tên nội dung *<input style={{ display: 'block', width: '100%' }} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <div style={{ display: 'flex', gap: 8 }}>
              <label style={{ flex: 1 }}>Mã<input style={{ display: 'block', width: '100%' }} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="vd KH-2025-..." /></label>
              <label style={{ flex: 1 }}>Nhóm
                <select style={{ display: 'block', width: '100%' }} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                  {Object.entries(CATEGORY).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
            </div>
            <label>Áp dụng cho vai (ngăn bằng ";")<input style={{ display: 'block', width: '100%' }} value={form.target_roles} onChange={(e) => setForm({ ...form, target_roles: e.target.value })} placeholder="vd GS; BP hoặc QL; BTr" /></label>
            <label>Ghi chú<textarea style={{ display: 'block', width: '100%' }} rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={form.is_prerequisite} onChange={(e) => setForm({ ...form, is_prerequisite: e.target.checked })} /> Nội dung tiên quyết (vd Train the trainer)</label>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Đang áp dụng</label>
          </div>
        </Modal>
      )}
    </AppShell>
  )
}
