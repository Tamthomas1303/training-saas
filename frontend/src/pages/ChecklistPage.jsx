import { useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import CompetencySelect from '../components/CompetencySelect'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Pager from '../components/Pager'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useCompetencyOptions } from '../hooks/useCompetencyOptions'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

// Khung noi dung cap S - Buoc 2 (Prompt_KhungNoiDung_CapS_Buoc2.md muc 1).
const PHASE_OPTIONS = [
  { value: 'core', label: 'Cơ bản (thử việc)' },
  { value: 'completion', label: 'Hoàn thiện' },
]
const PHASE_LABELS = { core: 'Cơ bản', completion: 'Hoàn thiện' }
const PHASE_VARIANTS = { core: 'neutral', completion: 'success' }

const EMPTY_FORM = {
  id: null, brand: '', position: '', day: '', category: '', task_name: '', description: '',
  doc_url: '', level_group: '', order: 0, competency: null, phase: 'core',
}

export default function ChecklistPage() {
  const { user } = useAuth()
  const isAdmin = (user.role || '').toLowerCase() === 'admin'
  const competencyOptions = useCompetencyOptions()

  const [search, setSearch] = useState('')
  const [brand, setBrand] = useState('')
  const [position, setPosition] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [bulkCompetency, setBulkCompetency] = useState('')
  const [bulkMsg, setBulkMsg] = useState('')
  const [bulkPhase, setBulkPhase] = useState('core')
  const [bulkPhaseMsg, setBulkPhaseMsg] = useState('')

  const params = {
    search, brand: brand || undefined, position: position || undefined, category: category || undefined,
    page, page_size: PAGE_SIZE, refreshKey,
  }
  const { data, loading, error } = usePaginatedList('/checklist/', params)

  function onFilterChange(setter) {
    return (e) => {
      setter(e.target.value)
      setPage(1)
      setSelected(new Set())
    }
  }

  function toggleSelected(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function bulkAssign(target) {
    setBulkMsg('')
    try {
      const { data: result } = await api.post('/checklist/bulk-assign-competency/', {
        ...target, competency: bulkCompetency || null,
      })
      setBulkMsg(`Đã gán năng lực cho ${result.updated} mục checklist.`)
      setBulkCompetency('')
      setSelected(new Set())
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setBulkMsg(err.response?.data?.detail || 'Gán hàng loạt thất bại.')
    }
  }

  async function bulkAssignPhase(target) {
    setBulkPhaseMsg('')
    try {
      const { data: result } = await api.post('/checklist/bulk-assign-phase/', {
        ...target, phase: bulkPhase,
      })
      setBulkPhaseMsg(`Đã gán "${PHASE_LABELS[bulkPhase]}" cho ${result.updated} mục checklist.`)
      setSelected(new Set())
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setBulkPhaseMsg(err.response?.data?.detail || 'Gán hàng loạt thất bại.')
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
      competency: c.competency, phase: c.phase || 'core',
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
      competency: form.competency, phase: form.phase,
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
        <input
          style={s.input}
          placeholder="Lọc theo danh mục (nhóm)"
          value={category}
          onChange={onFilterChange(setCategory)}
        />
      </FilterBar>

      {isAdmin && (
        <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>Gán hàng loạt năng lực:</span>
          <CompetencySelect value={bulkCompetency} onChange={(v) => setBulkCompetency(v || '')} options={competencyOptions} />
          <button
            className="btn-sm btn-outline" disabled={selected.size === 0}
            onClick={() => bulkAssign({ ids: [...selected] })}
          >
            Gán cho {selected.size} mục đã chọn
          </button>
          <button
            className="btn-sm btn-outline" disabled={!category}
            onClick={() => bulkAssign({ category })}
            title={!category ? 'Nhập tên danh mục ở ô lọc để gán cho cả nhóm' : ''}
          >
            Gán cho cả danh mục "{category || '...'}"
          </button>
          {bulkMsg && <span className="muted-note">{bulkMsg}</span>}
        </div>
      )}

      {/* Khung noi dung cap S - Buoc 2 (Prompt_KhungNoiDung_CapS_Buoc2.md muc 1). */}
      {isAdmin && (
        <div className="card" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>Gán hàng loạt phân loại:</span>
          <select style={s.select} value={bulkPhase} onChange={(e) => setBulkPhase(e.target.value)}>
            {PHASE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button
            className="btn-sm btn-outline" disabled={selected.size === 0}
            onClick={() => bulkAssignPhase({ ids: [...selected] })}
          >
            Gán cho {selected.size} mục đã chọn
          </button>
          <button
            className="btn-sm btn-outline" disabled={!category}
            onClick={() => bulkAssignPhase({ category })}
            title={!category ? 'Nhập tên danh mục ở ô lọc để gán cho cả nhóm' : ''}
          >
            Gán cho cả danh mục "{category || '...'}"
          </button>
          {bulkPhaseMsg && <span className="muted-note">{bulkPhaseMsg}</span>}
        </div>
      )}

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {!loading && !error && (
        <>
          <Table>
            <thead>
              <tr>
                {isAdmin && (
                  <th style={{ width: 30 }}>
                    <input
                      type="checkbox"
                      checked={data.results.length > 0 && data.results.every((c) => selected.has(c.id))}
                      onChange={(e) => {
                        const next = new Set(selected)
                        data.results.forEach((c) => (e.target.checked ? next.add(c.id) : next.delete(c.id)))
                        setSelected(next)
                      }}
                    />
                  </th>
                )}
                <th>#</th>
                <th>Brand</th>
                <th>Vị trí</th>
                <th>Ngày</th>
                <th>Danh mục</th>
                <th>Đầu việc</th>
                <th>Cấp</th>
                <th>Năng lực</th>
                <th>Phân loại</th>
                <th>Tài liệu</th>
                {isAdmin && <th></th>}
              </tr>
            </thead>
            <tbody>
              {data.results.map((c) => (
                <tr key={c.id}>
                  {isAdmin && (
                    <td><input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleSelected(c.id)} /></td>
                  )}
                  <td>{c.order}</td>
                  <td>{c.brand}</td>
                  <td>{c.position}</td>
                  <td>{c.day}</td>
                  <td>{c.category}</td>
                  <td>{c.task_name}</td>
                  <td>{c.level_group}</td>
                  <td className="muted-note">{c.competency_name || '—'}</td>
                  <td><Badge variant={PHASE_VARIANTS[c.phase] || 'neutral'}>{PHASE_LABELS[c.phase] || c.phase}</Badge></td>
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
                  <td colSpan={isAdmin ? 12 : 10} className="muted-note">
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
              Phân loại (Khung nội dung cấp S)
              <select
                style={{ display: 'block', width: '100%' }}
                value={form.phase}
                onChange={(e) => setForm({ ...form, phase: e.target.value })}
              >
                {PHASE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
            <label>
              Năng lực (dùng để tính điểm Hồ sơ 360)
              <CompetencySelect
                value={form.competency}
                onChange={(v) => setForm({ ...form, competency: v })}
                options={competencyOptions}
                style={{ display: 'block', width: '100%', marginTop: 4 }}
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
