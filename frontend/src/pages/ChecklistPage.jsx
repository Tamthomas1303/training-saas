import { useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Pager from '../components/Pager'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const EMPTY_FORM = {
  id: null, brand: '', position: '', day: '', category: '', task_name: '', description: '',
  doc_url: '', level_group: '', order: 0,
}

export default function ChecklistPage() {
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

  const params = { search, brand: brand || undefined, position: position || undefined, page, page_size: PAGE_SIZE, refreshKey }
  const { data, loading, error } = usePaginatedList('/checklist/', params)

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

  function openEdit(c) {
    setForm({
      id: c.id, brand: c.brand || '', position: c.position || '', day: c.day ?? '',
      category: c.category || '', task_name: c.task_name, description: c.description || '',
      doc_url: c.doc_url || '', level_group: c.level_group || '', order: c.order ?? 0,
    })
    setFormError('')
  }

  async function saveForm() {
    setSaving(true)
    setFormError('')
    const payload = {
      brand: form.brand, position: form.position, day: form.day === '' ? null : Number(form.day),
      category: form.category, task_name: form.task_name, description: form.description,
      doc_url: form.doc_url, level_group: form.level_group, order: Number(form.order) || 0,
    }
    try {
      if (form.id) {
        await api.patch(`/checklist/${form.id}/`, payload)
      } else {
        await api.post('/checklist/', payload)
      }
      setForm(null)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được checklist.'
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Checklist đào tạo</h2>
        {isAdmin && <button onClick={openCreate}>+ Thêm checklist</button>}
      </div>

      <FilterBar>
        <input
          style={s.input}
          placeholder="Tìm theo tên đầu việc..."
          value={search}
          onChange={onFilterChange(setSearch)}
        />
        <input style={s.input} placeholder="Lọc theo brand" value={brand} onChange={onFilterChange(setBrand)} />
        <input
          style={s.input}
          placeholder="Lọc theo vị trí"
          value={position}
          onChange={onFilterChange(setPosition)}
        />
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                <th>#</th>
                <th>Brand</th>
                <th>Vị trí</th>
                <th>Ngày</th>
                <th>Danh mục</th>
                <th>Đầu việc</th>
                <th>Cấp</th>
                <th>Tài liệu</th>
                {isAdmin && <th></th>}
              </tr>
            </thead>
            <tbody>
              {data.results.map((c) => (
                <tr key={c.id}>
                  <td>{c.order}</td>
                  <td>{c.brand}</td>
                  <td>{c.position}</td>
                  <td>{c.day}</td>
                  <td>{c.category}</td>
                  <td>{c.task_name}</td>
                  <td>{c.level_group}</td>
                  <td>
                    {c.doc_url ? (
                      <a href={c.doc_url} target="_blank" rel="noreferrer">
                        Xem
                      </a>
                    ) : (
                      ''
                    )}
                  </td>
                  {isAdmin && (
                    <td>
                      <button className="btn-outline btn-sm" onClick={() => openEdit(c)}>
                        Sửa
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={isAdmin ? 9 : 8} className="muted-note">
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
        title={form?.id ? 'Sửa checklist' : 'Thêm checklist'}
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
              Đầu việc
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.task_name}
                onChange={(e) => setForm({ ...form, task_name: e.target.value })}
              />
            </label>
            <label>
              Mô tả
              <textarea
                style={{ display: 'block', width: '100%' }}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
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
              Vị trí
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.position}
                onChange={(e) => setForm({ ...form, position: e.target.value })}
              />
            </label>
            <label>
              Ngày (số thứ tự ngày đào tạo)
              <input
                type="number"
                style={{ display: 'block', width: '100%' }}
                value={form.day}
                onChange={(e) => setForm({ ...form, day: e.target.value })}
              />
            </label>
            <label>
              Danh mục
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              />
            </label>
            <label>
              Cấp (Level_Group)
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.level_group}
                onChange={(e) => setForm({ ...form, level_group: e.target.value })}
              />
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
            <label>
              Đường dẫn tài liệu
              <input
                style={{ display: 'block', width: '100%' }}
                value={form.doc_url}
                onChange={(e) => setForm({ ...form, doc_url: e.target.value })}
              />
            </label>
            {formError && <p style={{ color: 'var(--danger)' }}>{formError}</p>}
          </div>
        )}
      </Modal>
    </AppShell>
  )
}
