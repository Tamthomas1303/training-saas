import { useMemo, useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Pager from '../components/Pager'
import Table from '../components/Table'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_LABELS = { done: 'Hoàn thành', update: 'Cần cập nhật', digitize: 'Cần số hóa' }
const STATUS_VARIANTS = { done: 'success', update: 'warning', digitize: 'neutral' }

const EMPTY_FORM = { id: null, name: '', code: '', brand: '', position: '', version: 'v1.0', status: 'done', file_url: '' }

export default function DocumentsPage() {
  const { user } = useAuth()
  const isAdmin = (user.role || '').toLowerCase() === 'admin'

  const [search, setSearch] = useState('')
  const [brand, setBrand] = useState('')
  const [position, setPosition] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })
  const { data: checklistOptions } = usePaginatedList('/checklist/', { page_size: 200 })

  const brandOptions = useMemo(
    () => [...new Set(restaurantOptions.results.map((r) => r.brand).filter(Boolean))],
    [restaurantOptions.results]
  )
  const positionOptions = useMemo(
    () => [...new Set(checklistOptions.results.map((c) => c.position).filter(Boolean))],
    [checklistOptions.results]
  )

  const params = {
    search, brand: brand || undefined, position: position || undefined,
    page, page_size: PAGE_SIZE, refreshKey,
  }
  const { data, loading, error } = usePaginatedList('/checklist/documents/', params)

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
    }
  }

  function openCreate() {
    setForm({ ...EMPTY_FORM })
    setFormError('')
  }

  function openEdit(d) {
    setForm({
      id: d.id, name: d.name, code: d.code || '', brand: d.brand || '', position: d.position || '',
      version: d.version || 'v1.0', status: d.status, file_url: d.file_url,
    })
    setFormError('')
  }

  async function saveForm() {
    setSaving(true)
    setFormError('')
    const payload = {
      name: form.name, code: form.code, brand: form.brand, position: form.position,
      version: form.version, status: form.status, file_url: form.file_url,
    }
    try {
      if (form.id) {
        await api.patch(`/checklist/documents/${form.id}/`, payload)
      } else {
        await api.post('/checklist/documents/', payload)
      }
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được tài liệu.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function removeDoc(d) {
    if (!window.confirm(`Xóa tài liệu "${d.name}"?`)) return
    await api.delete(`/checklist/documents/${d.id}/`)
    setRefreshKey((k) => k + 1)
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Tài liệu</h2>
        {isAdmin && <button onClick={openCreate}>+ Thêm tài liệu</button>}
      </div>

      <FilterBar>
        <input style={s.input} placeholder="Tìm theo tên / mã..." value={search} onChange={onFilterChange(setSearch)} />
        <select style={s.select} value={brand} onChange={onFilterChange(setBrand)}>
          <option value="">Tất cả thương hiệu</option>
          {brandOptions.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <select style={s.select} value={position} onChange={onFilterChange(setPosition)}>
          <option value="">Tất cả vị trí</option>
          {positionOptions.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>Tên tài liệu</th>
                <th>Thương hiệu</th>
                <th>Vị trí</th>
                <th>Phiên bản</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((d) => (
                <tr key={d.id}>
                  <td>
                    <a href={d.file_url} target="_blank" rel="noreferrer">
                      {d.name}
                    </a>
                  </td>
                  <td>{d.brand}</td>
                  <td>{d.position}</td>
                  <td>{d.version}</td>
                  <td>
                    <Badge variant={STATUS_VARIANTS[d.status] || 'neutral'}>{STATUS_LABELS[d.status] || d.status}</Badge>
                  </td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    {isAdmin && (
                      <>
                        <button className="btn-outline btn-sm" onClick={() => openEdit(d)}>
                          Sửa
                        </button>
                        <button className="btn-danger btn-sm" onClick={() => removeDoc(d)}>
                          Xóa
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted-note">
                    Không có dữ liệu.
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
        title={form?.id ? 'Sửa tài liệu' : 'Thêm tài liệu'}
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
              Tên tài liệu
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Mã tài liệu
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
              />
            </label>
            <label>
              Thương hiệu
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
              >
                <option value="">—</option>
                {brandOptions.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Vị trí (tích nhiều — để trống = dùng chung mọi vị trí)
              <div style={{ maxHeight: 140, overflow: 'auto', border: '1px solid var(--card-border)', borderRadius: 6, padding: 6 }}>
                {positionOptions.map((p) => {
                  const selected = (form.position || '').split(';').map((x) => x.trim().toLowerCase())
                  const checked = selected.includes(p.trim().toLowerCase())
                  return (
                    <label key={p} style={{ display: 'block', fontSize: 14 }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          const cur = (form.position || '').split(';').map((x) => x.trim()).filter(Boolean)
                          const next = e.target.checked
                            ? [...cur.filter((x) => x.toLowerCase() !== p.toLowerCase()), p]
                            : cur.filter((x) => x.toLowerCase() !== p.toLowerCase())
                          setForm({ ...form, position: next.join('; ') })
                        }}
                      /> {p}
                    </label>
                  )
                })}
                {positionOptions.length === 0 && <span className="muted-note">Chưa có danh sách vị trí.</span>}
              </div>
            </label>
            <label>
              Phiên bản
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
              />
            </label>
            <label>
              Trạng thái
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Đường dẫn tệp
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.file_url}
                onChange={(e) => setForm({ ...form, file_url: e.target.value })}
              />
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>
    </AppShell>
  )
}
