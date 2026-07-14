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

const PAGE_SIZE = 20

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin' },
  { value: 'om', label: 'OM' },
  { value: 'bod', label: 'BOD' },
  { value: 'am', label: 'AM' },
  { value: 'kcs', label: 'KCS' },
  { value: 'bql', label: 'BQL' },
  { value: 'trainer', label: 'Trainer' },
]

const JOB_TITLE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'qlnh', label: 'Quản lý nhà hàng' },
  { value: 'giam_sat', label: 'Giám sát' },
  { value: 'bep_truong', label: 'Bếp trưởng' },
  { value: 'bep_pho', label: 'Bếp phó' },
]

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'locked', label: 'Locked' },
]

const STATUS_VARIANTS = { active: 'success', inactive: 'neutral', locked: 'danger' }

const EMPTY_FORM = {
  id: null, username: '', password: '', full_name: '', role: 'trainer', job_title: '',
  restaurant: '', trainer_zone: '', status: 'active',
}

export default function UsersPage() {
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [areaUser, setAreaUser] = useState(null)
  const [areaSelected, setAreaSelected] = useState([])
  const [areaSaving, setAreaSaving] = useState(false)

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })

  const params = { search, role: role || undefined, page, page_size: PAGE_SIZE, refreshKey }
  const { data, loading, error } = usePaginatedList('/auth/users/', params)

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

  function openEdit(u) {
    setForm({
      id: u.id, username: u.username, password: '', full_name: u.full_name, role: u.role,
      job_title: u.job_title || '', restaurant: u.restaurant || '', trainer_zone: u.trainer_zone || '',
      status: u.status,
    })
    setFormError('')
  }

  async function saveForm() {
    setSaving(true)
    setFormError('')
    const payload = {
      username: form.username, full_name: form.full_name, role: form.role,
      job_title: form.job_title || null, restaurant: form.restaurant || null,
      trainer_zone: form.trainer_zone, status: form.status,
    }
    if (form.password) payload.password = form.password
    try {
      if (form.id) {
        await api.patch(`/auth/users/${form.id}/`, payload)
      } else {
        await api.post('/auth/users/', payload)
      }
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được người dùng.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function openAreas(u) {
    setAreaUser(u)
    try {
      const { data } = await api.get(`/auth/users/${u.id}/areas/`)
      setAreaSelected(data.restaurant_ids)
    } catch {
      setAreaSelected([])
    }
  }

  function toggleArea(id) {
    setAreaSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  async function saveAreas() {
    setAreaSaving(true)
    try {
      await api.post(`/auth/users/${areaUser.id}/areas/`, { restaurant_ids: areaSelected })
      setAreaUser(null)
    } catch {
      // giu popup mo de thu lai
    } finally {
      setAreaSaving(false)
    }
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Người dùng</h2>
        <button onClick={openCreate}>+ Thêm người dùng</button>
      </div>

      <FilterBar>
        <input
          style={s.input}
          placeholder="Tìm theo tài khoản / họ tên..."
          value={search}
          onChange={onFilterChange(setSearch)}
        />
        <select style={s.select} value={role} onChange={onFilterChange(setRole)}>
          <option value="">Tất cả vai trò</option>
          {ROLE_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
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
                <th>Tài khoản</th>
                <th>Họ tên</th>
                <th>Vai trò</th>
                <th>Nhà hàng</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.full_name}</td>
                  <td>{u.role}</td>
                  <td>{u.restaurant_name}</td>
                  <td>
                    <Badge variant={STATUS_VARIANTS[u.status] || 'neutral'}>{u.status}</Badge>
                  </td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button className="btn-outline btn-sm" onClick={() => openEdit(u)}>
                      Sửa
                    </button>
                    {u.role === 'kcs' && (
                      <button className="btn-outline btn-sm" onClick={() => openAreas(u)}>
                        Phân vùng
                      </button>
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
        title={form?.id ? 'Sửa người dùng' : 'Thêm người dùng'}
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
              Tài khoản
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                disabled={!!form.id}
              />
            </label>
            <label>
              Mật khẩu {form.id ? '(để trống nếu không đổi)' : '(để trống dùng mặc định)'}
              <input
                type="password"
                style={{ display: 'block', width: '100%' }}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </label>
            <label>
              Họ tên
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </label>
            <label>
              Vai trò
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Chức danh
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.job_title}
                onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              >
                {JOB_TITLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Nhà hàng
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.restaurant}
                onChange={(e) => setForm({ ...form, restaurant: e.target.value })}
              >
                <option value="">—</option>
                {restaurantOptions.results.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Trạng thái
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>

      <Modal
        open={!!areaUser}
        title={`Phân vùng — ${areaUser?.full_name || ''}`}
        onClose={() => setAreaUser(null)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setAreaUser(null)}>
              Hủy
            </button>
            <button onClick={saveAreas} disabled={areaSaving}>
              Lưu
            </button>
          </>
        }
      >
        <div style={{ display: 'grid', gap: 6, maxHeight: 320, overflowY: 'auto' }}>
          {restaurantOptions.results.map((r) => (
            <label key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={areaSelected.includes(r.id)}
                onChange={() => toggleArea(r.id)}
              />
              {r.name}
            </label>
          ))}
        </div>
      </Modal>
    </AppShell>
  )
}
