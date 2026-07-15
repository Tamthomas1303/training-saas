import { useState } from 'react'
import Badge from './Badge'
import FilterBar from './FilterBar'
import Modal from './Modal'
import Pager from './Pager'
import Table from './Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from '../pages/listPageStyles'

const PAGE_SIZE = 10

const EMPTY_FORM = { id: null, code: '', name: '', brand: '', city: '', district: '', region: '', email: '', status: 'active' }

export default function RestaurantsPanel() {
  const [search, setSearch] = useState('')
  const [brand, setBrand] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const params = { search, brand: brand || undefined, status: status || undefined, page, page_size: PAGE_SIZE, refreshKey }
  const { data, loading, error } = usePaginatedList('/restaurants/', params)

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

  function openEdit(r) {
    setForm({
      id: r.id, code: r.code, name: r.name, brand: r.brand || '', city: r.city || '',
      district: r.district || '', region: r.region || '', email: r.email || '', status: r.status,
    })
    setFormError('')
  }

  async function saveForm() {
    setSaving(true)
    setFormError('')
    const payload = {
      code: form.code, name: form.name, brand: form.brand, city: form.city,
      district: form.district, region: form.region, email: form.email, status: form.status,
    }
    try {
      if (form.id) {
        await api.patch(`/restaurants/${form.id}/`, payload)
      } else {
        await api.post('/restaurants/', payload)
      }
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được nhà hàng.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Nhà hàng</h2>
        <button onClick={openCreate}>+ Thêm nhà hàng</button>
      </div>

      <FilterBar>
        <input style={s.input} placeholder="Tìm theo mã / tên / email..." value={search} onChange={onFilterChange(setSearch)} />
        <input style={s.input} placeholder="Lọc theo brand" value={brand} onChange={onFilterChange(setBrand)} />
        <select style={s.select} value={status} onChange={onFilterChange(setStatus)}>
          <option value="">Tất cả trạng thái</option>
          <option value="active">Đang hoạt động</option>
          <option value="inactive">Ngừng hoạt động</option>
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>Mã</th>
                <th>Tên nhà hàng</th>
                <th>Brand</th>
                <th>Khu vực</th>
                <th>Email</th>
                <th>Trạng thái</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td>
                  <td>{r.name}</td>
                  <td>{r.brand}</td>
                  <td>{[r.city, r.district, r.region].filter(Boolean).join(' · ')}</td>
                  <td>{r.email}</td>
                  <td>
                    <Badge variant={r.status === 'active' ? 'success' : 'neutral'}>
                      {r.status === 'active' ? 'Đang hoạt động' : 'Ngừng hoạt động'}
                    </Badge>
                  </td>
                  <td>
                    <button className="btn-outline btn-sm" onClick={() => openEdit(r)}>
                      Sửa
                    </button>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted-note">
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
        title={form?.id ? 'Sửa nhà hàng' : 'Thêm nhà hàng'}
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
              Mã nhà hàng
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                disabled={!!form.id}
              />
            </label>
            <label>
              Tên nhà hàng
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Brand
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
              />
            </label>
            <label>
              Thành phố
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.city}
                onChange={(e) => setForm({ ...form, city: e.target.value })}
              />
            </label>
            <label>
              Quận/huyện
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.district}
                onChange={(e) => setForm({ ...form, district: e.target.value })}
              />
            </label>
            <label>
              Khu vực
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
              />
            </label>
            <label>
              Email
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </label>
            <label>
              Trạng thái
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
              >
                <option value="active">Đang hoạt động</option>
                <option value="inactive">Ngừng hoạt động</option>
              </select>
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>
    </div>
  )
}
