import { useEffect, useRef, useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

// ---- Cấp O (hội đồng) ----
const O_TYPES = [
  { value: 'ShiftOps', label: 'Vận hành ca (Đạt/Không)' },
  { value: 'Council_Skill', label: 'Tay nghề (1–4)' },
  { value: 'Council_Interview', label: 'Phỏng vấn (1–4)' },
]
const GROUPS = [
  { value: 'FOH', label: 'FOH (Quản lý/Giám sát)' },
  { value: 'BOH', label: 'BOH (Bếp trưởng/phó)' },
]
const DEPT_ROLES = [
  { value: 'HCNS', label: 'HCNS' },
  { value: 'DaoTao', label: 'Đào tạo' },
  { value: 'VanHanh', label: 'Vận hành' },
  { value: 'QC', label: 'QC' },
]
// ---- Cấp S (theo vị trí) ----
const S_TYPES = [
  { value: 'Skill_BQL', label: 'Kỹ năng (BQL chấm)' },
  { value: 'Knowledge', label: 'Kiến thức' },
]

export default function CriteriaEditorPage() {
  const [mode, setMode] = useState('S') // 'S' cấp S theo vị trí, 'O' cấp O hội đồng
  // cấp O
  const [oType, setOType] = useState('ShiftOps')
  const [group, setGroup] = useState('FOH')
  const [deptRole, setDeptRole] = useState('HCNS')
  // cấp S
  const [sType, setSType] = useState('Skill_BQL')
  const [brand, setBrand] = useState('')
  const [position, setPosition] = useState('')
  const [positions, setPositions] = useState([])

  const [rows, setRows] = useState([])
  const [form, setForm] = useState(null)
  const [msg, setMsg] = useState('')
  const fileRef = useRef(null)

  const isO = mode === 'O'
  const isInterview = isO && oType === 'Council_Interview'

  useEffect(() => {
    api.get('/employees/positions/').then(({ data }) => setPositions(data)).catch(() => {})
  }, [])

  function load() {
    const params = isO
      ? { eval_type: oType, position_group: group, ...(isInterview ? { dept_role: deptRole } : {}) }
      : { eval_type: sType, ...(brand ? { brand } : {}), ...(position ? { position } : {}) }
    api.get('/evaluation/council-criteria/', { params }).then(({ data }) => setRows(data)).catch(() => setRows([]))
  }
  useEffect(load, [mode, oType, group, deptRole, sType, brand, position])

  function openAdd() {
    if (isO) {
      setForm({ id: null, section: '', content: '', max_score: oType === 'ShiftOps' ? 1 : 4, order: rows.length })
    } else {
      setForm({
        id: null, brand, position, level_group: 'S', section: '', content: '',
        max_score: 10, is_mandatory: false, require_photo: false, order: rows.length,
      })
    }
  }
  function openEdit(r) {
    setForm(isO
      ? { id: r.id, section: r.section, content: r.content, max_score: r.max_score, order: r.order }
      : {
          id: r.id, brand: r.brand, position: r.position, level_group: r.level_group || 'S',
          section: r.section, content: r.content, max_score: r.max_score,
          is_mandatory: r.is_mandatory, require_photo: r.require_photo, order: r.order,
        })
  }
  async function save() {
    setMsg('')
    const payload = isO
      ? { ...form, eval_type: oType, position_group: group, dept_role: isInterview ? deptRole : '' }
      : { ...form, eval_type: sType, position_group: '', dept_role: '' }
    try {
      if (form.id) await api.patch(`/evaluation/council-criteria/${form.id}/`, payload)
      else await api.post('/evaluation/council-criteria/', payload)
      setForm(null)
      load()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Lưu tiêu chí thất bại.')
    }
  }
  async function del(r) {
    if (!window.confirm(`Xóa tiêu chí "${r.content}"?`)) return
    try {
      await api.delete(`/evaluation/council-criteria/${r.id}/`)
      load()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Xóa thất bại.')
    }
  }
  async function importFile(file) {
    if (!file) return
    setMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const { data } = await api.post('/evaluation/council-criteria/import-file/', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMsg(`Đã nhập: ${data.created} thêm mới, ${data.updated} cập nhật, ${data.skipped} bỏ qua.`)
      load()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Nhập file thất bại.')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Tiêu chí đánh giá</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {!isO && (
            <>
              <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" style={{ display: 'none' }} onChange={(e) => importFile(e.target.files[0])} />
              <button className="btn-outline" onClick={() => fileRef.current?.click()}>Nhập từ file</button>
            </>
          )}
          <button onClick={openAdd}>+ Thêm tiêu chí</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, margin: '10px 0' }}>
        <button className={`btn-sm ${mode === 'S' ? '' : 'btn-outline'}`} onClick={() => setMode('S')}>Cấp S (theo vị trí)</button>
        <button className={`btn-sm ${mode === 'O' ? '' : 'btn-outline'}`} onClick={() => setMode('O')}>Cấp O (hội đồng)</button>
      </div>
      <p className="muted-note">Chỉnh sửa ở đây áp dụng ngay cho các phiếu chấm.</p>

      <FilterBar>
        {isO ? (
          <>
            <select style={s.select} value={oType} onChange={(e) => setOType(e.target.value)}>
              {O_TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}
            </select>
            <select style={s.select} value={group} onChange={(e) => setGroup(e.target.value)}>
              {GROUPS.map((g) => (<option key={g.value} value={g.value}>{g.label}</option>))}
            </select>
            {isInterview && (
              <select style={s.select} value={deptRole} onChange={(e) => setDeptRole(e.target.value)}>
                {DEPT_ROLES.map((d) => (<option key={d.value} value={d.value}>{d.label}</option>))}
              </select>
            )}
          </>
        ) : (
          <>
            <select style={s.select} value={sType} onChange={(e) => setSType(e.target.value)}>
              {S_TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}
            </select>
            <input style={s.input} placeholder="Lọc theo brand (vd KMP)" value={brand} onChange={(e) => setBrand(e.target.value)} />
            <input list="pos-list" style={s.input} placeholder="Lọc theo vị trí" value={position} onChange={(e) => setPosition(e.target.value)} />
            <datalist id="pos-list">{positions.map((p) => (<option key={p} value={p} />))}</datalist>
          </>
        )}
      </FilterBar>

      {msg && <p style={{ color: 'var(--forest-dark)' }}>{msg}</p>}

      <Table>
        <thead>
          <tr>
            <th style={{ width: 40 }}>STT</th>
            {!isO && <th>Brand</th>}
            {!isO && <th>Vị trí</th>}
            <th>Mục</th>
            <th>Nội dung</th>
            <th style={{ width: 70 }}>Tối đa</th>
            <th style={{ width: 110 }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id}>
              <td>{i + 1}</td>
              {!isO && <td>{r.brand}</td>}
              {!isO && <td>{r.position}</td>}
              <td>{r.section}</td>
              <td>{r.content}</td>
              <td style={{ textAlign: 'center' }}>{r.max_score}</td>
              <td style={{ display: 'flex', gap: 6 }}>
                <button className="btn-outline btn-sm" onClick={() => openEdit(r)}>Sửa</button>
                <button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => del(r)}>Xóa</button>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={isO ? 5 : 7} className="muted-note">Chưa có tiêu chí. {!isO && 'Dùng "Nhập từ file" để nạp bộ tiêu chí ban đầu.'}</td></tr>
          )}
        </tbody>
      </Table>

      <Modal
        open={!!form}
        title={form?.id ? 'Sửa tiêu chí' : 'Thêm tiêu chí'}
        onClose={() => setForm(null)}
        footer={<><button className="btn-outline" onClick={() => setForm(null)}>Hủy</button><button onClick={save}>Lưu</button></>}
      >
        {form && (
          <div style={{ display: 'grid', gap: 10 }}>
            {!isO && (
              <>
                <label>Brand<input style={{ display: 'block', width: '100%' }} value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} placeholder="Mã brand, vd KMP" /></label>
                <label>Vị trí<input list="pos-list" style={{ display: 'block', width: '100%' }} value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} /></label>
                <label>Level<input style={{ display: 'block', width: '100%' }} value={form.level_group} onChange={(e) => setForm({ ...form, level_group: e.target.value })} placeholder="S" /></label>
              </>
            )}
            <label>Mục (nhóm tiêu chí)<input style={{ display: 'block', width: '100%' }} value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} /></label>
            <label>Nội dung<input style={{ display: 'block', width: '100%' }} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} /></label>
            <label>Điểm tối đa<input type="number" min="1" style={{ display: 'block', width: '100%' }} value={form.max_score} onChange={(e) => setForm({ ...form, max_score: Number(e.target.value) || 1 })} /></label>
            {!isO && (
              <>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}><input type="checkbox" checked={!!form.is_mandatory} onChange={(e) => setForm({ ...form, is_mandatory: e.target.checked })} /> Bắt buộc (không đạt là trượt)</label>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}><input type="checkbox" checked={!!form.require_photo} onChange={(e) => setForm({ ...form, require_photo: e.target.checked })} /> Bắt buộc chụp ảnh minh chứng</label>
              </>
            )}
            <label>Thứ tự<input type="number" min="0" style={{ display: 'block', width: '100%' }} value={form.order} onChange={(e) => setForm({ ...form, order: Number(e.target.value) || 0 })} /></label>
          </div>
        )}
      </Modal>
    </AppShell>
  )
}
