import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

const EVAL_TYPES = [
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

export default function CriteriaEditorPage() {
  const [evalType, setEvalType] = useState('ShiftOps')
  const [group, setGroup] = useState('FOH')
  const [deptRole, setDeptRole] = useState('HCNS')
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(null)
  const [msg, setMsg] = useState('')

  const isInterview = evalType === 'Council_Interview'
  const defaultMax = evalType === 'ShiftOps' ? 1 : 4

  function load() {
    const params = { eval_type: evalType, position_group: group }
    if (isInterview) params.dept_role = deptRole
    api.get('/evaluation/council-criteria/', { params }).then(({ data }) => setRows(data)).catch(() => setRows([]))
  }
  useEffect(load, [evalType, group, deptRole])

  async function save() {
    setMsg('')
    const payload = { ...form, eval_type: evalType, position_group: group, dept_role: isInterview ? deptRole : '' }
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

  return (
    <AppShell>
      <h2>Tiêu chí đánh giá cấp O</h2>
      <p className="muted-note">Chỉnh sửa ở đây sẽ áp dụng ngay cho các phiếu chấm hội đồng.</p>

      <FilterBar>
        <select style={s.select} value={evalType} onChange={(e) => setEvalType(e.target.value)}>
          {EVAL_TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}
        </select>
        <select style={s.select} value={group} onChange={(e) => setGroup(e.target.value)}>
          {GROUPS.map((g) => (<option key={g.value} value={g.value}>{g.label}</option>))}
        </select>
        {isInterview && (
          <select style={s.select} value={deptRole} onChange={(e) => setDeptRole(e.target.value)}>
            {DEPT_ROLES.map((d) => (<option key={d.value} value={d.value}>{d.label}</option>))}
          </select>
        )}
        <button onClick={() => setForm({ id: null, section: '', content: '', max_score: defaultMax, order: rows.length })}>
          + Thêm tiêu chí
        </button>
      </FilterBar>

      {msg && <p style={{ color: 'var(--danger)' }}>{msg}</p>}

      <Table>
        <thead>
          <tr>
            <th style={{ width: 40 }}>STT</th>
            <th>Mục</th>
            <th>Nội dung</th>
            <th style={{ width: 80 }}>Điểm tối đa</th>
            <th style={{ width: 120 }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id}>
              <td>{i + 1}</td>
              <td>{r.section}</td>
              <td>{r.content}</td>
              <td style={{ textAlign: 'center' }}>{r.max_score}</td>
              <td style={{ display: 'flex', gap: 6 }}>
                <button className="btn-outline btn-sm" onClick={() => setForm({ id: r.id, section: r.section, content: r.content, max_score: r.max_score, order: r.order })}>Sửa</button>
                <button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => del(r)}>Xóa</button>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={5} className="muted-note">Chưa có tiêu chí cho nhóm này.</td></tr>
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
            <label>Mục (nhóm tiêu chí)<input style={{ display: 'block', width: '100%' }} value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} placeholder="VD: Mở ca sáng / I. Chuẩn bị..." /></label>
            <label>Nội dung tiêu chí<input style={{ display: 'block', width: '100%' }} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} /></label>
            <label>Điểm tối đa<input type="number" min="1" style={{ display: 'block', width: '100%' }} value={form.max_score} onChange={(e) => setForm({ ...form, max_score: Number(e.target.value) || 1 })} /></label>
            <label>Thứ tự<input type="number" min="0" style={{ display: 'block', width: '100%' }} value={form.order} onChange={(e) => setForm({ ...form, order: Number(e.target.value) || 0 })} /></label>
          </div>
        )}
      </Modal>
    </AppShell>
  )
}
