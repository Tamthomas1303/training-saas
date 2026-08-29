import { useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Pager from '../components/Pager'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

// Muc 16 Phase 1 phan A (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md) - man quan tri danh muc
// Vi tri chuc danh (thay the go tay chuoi tu do o Employee.position/Checklist.position/...).
// CHI Admin vao duoc man nay (xem App.jsx::ProtectedRoute); API doc mo cho moi vai tro dang
// nhap, ghi chi Admin (xem employees/views.py::PositionViewSet).
const PAGE_SIZE = 20

const ZONE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'FOH', label: 'FOH (mặt tiền)' },
  { value: 'BOH', label: 'BOH (hậu trường)' },
]

const LEVEL_GROUP_OPTIONS = [
  { value: '', label: '—' },
  { value: 'S', label: 'Nhân viên (S)' },
  { value: 'O', label: 'Giám sát/Quản lý (O)' },
  { value: 'P', label: 'Cấp trung (P)' },
]

const EMPTY_FORM = { id: null, name: '', zone: '', level_group: '', is_active: true, order: 0 }

export default function PositionsPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const params = { search, page, page_size: PAGE_SIZE, refreshKey }
  const { data, loading, error } = usePaginatedList('/employees/positions-catalog/', params)

  function openCreate() {
    setForm({ ...EMPTY_FORM })
    setFormError('')
  }

  function openEdit(p) {
    setForm({
      id: p.id, name: p.name, zone: p.zone || '', level_group: p.level_group || '',
      is_active: p.is_active, order: p.order,
    })
    setFormError('')
  }

  async function saveForm() {
    setSaving(true)
    setFormError('')
    const payload = {
      name: form.name, zone: form.zone, level_group: form.level_group,
      is_active: form.is_active, order: Number(form.order) || 0,
    }
    try {
      if (form.id) {
        await api.patch(`/employees/positions-catalog/${form.id}/`, payload)
      } else {
        await api.post('/employees/positions-catalog/', payload)
      }
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được vị trí.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(p) {
    try {
      await api.patch(`/employees/positions-catalog/${p.id}/`, { is_active: !p.is_active })
      setRefreshKey((k) => k + 1)
    } catch {
      // giu nguyen danh sach, thu lai sau
    }
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Vị trí chức danh</h2>
        <button onClick={openCreate}>+ Thêm vị trí</button>
      </div>
      <p className="muted-note">
        Danh mục dùng cho các dropdown chọn vị trí (thêm nhân sự, checklist, khung năng lực). Ẩn
        thay vì xóa nếu vị trí đã có dữ liệu nhân sự cũ tham chiếu tới.
      </p>

      <FilterBar>
        <input
          style={s.input}
          placeholder="Tìm theo tên vị trí..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
        />
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>Tên vị trí</th>
                <th>Khu vực</th>
                <th>Nhóm cấp</th>
                <th>Thứ tự</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{ZONE_OPTIONS.find((o) => o.value === p.zone)?.label || '—'}</td>
                  <td>{LEVEL_GROUP_OPTIONS.find((o) => o.value === p.level_group)?.label || '—'}</td>
                  <td>{p.order}</td>
                  <td>
                    <Badge variant={p.is_active ? 'success' : 'neutral'}>
                      {p.is_active ? 'Đang dùng' : 'Đã ẩn'}
                    </Badge>
                  </td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button className="btn-outline btn-sm" onClick={() => openEdit(p)}>
                      Sửa
                    </button>
                    <button className="btn-outline btn-sm" onClick={() => toggleActive(p)}>
                      {p.is_active ? 'Ẩn' : 'Khôi phục'}
                    </button>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted-note">
                    Chưa có vị trí nào.
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
          <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
        </>
      )}

      <Modal
        open={!!form}
        title={form?.id ? 'Sửa vị trí' : 'Thêm vị trí'}
        onClose={() => setForm(null)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setForm(null)}>
              Hủy
            </button>
            <button onClick={saveForm} disabled={saving}>
              Lưu
            </button>
          </>
        }
      >
        {form && (
          <div style={{ display: 'grid', gap: 10 }}>
            <label>
              Tên vị trí
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Khu vực
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.zone}
                onChange={(e) => setForm({ ...form, zone: e.target.value })}
              >
                {ZONE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
            <label>
              Nhóm cấp
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.level_group}
                onChange={(e) => setForm({ ...form, level_group: e.target.value })}
              >
                {LEVEL_GROUP_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
            <label>
              Thứ tự hiển thị
              <input
                type="number"
                style={{ display: 'block', width: '100%' }}
                value={form.order}
                onChange={(e) => setForm({ ...form, order: e.target.value })}
              />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Đang dùng (hiện trong dropdown chọn vị trí)
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>
    </AppShell>
  )
}
