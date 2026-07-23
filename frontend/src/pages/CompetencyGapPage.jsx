import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Table from '../components/Table'
import api from '../api/client'

const GAPS = [
  { value: 'skill', label: 'Chưa đánh giá kỹ năng' },
  { value: 'shiftops', label: 'Chưa đánh giá vận hành ca' },
  { value: 'interview', label: 'Chưa có kết quả phỏng vấn' },
  { value: 'exam', label: 'Chưa đạt thi lý thuyết' },
  { value: 'cohort', label: 'Chưa tham gia đợt/khóa...' },
]
const LEVELS = [{ value: '', label: 'Tất cả level' }, { value: 'S', label: 'Cấp S' }, { value: 'O', label: 'Cấp O' }, { value: 'P', label: 'Part-time (P)' }]

export default function CompetencyGapPage() {
  const [gap, setGap] = useState('skill')
  const [level, setLevel] = useState('')
  const [cohortId, setCohortId] = useState('')
  const [cohorts, setCohorts] = useState([])
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [ran, setRan] = useState(false)
  const [inviteCohort, setInviteCohort] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/sourcing/cohorts/', { params: { page_size: 100 } }).then(({ data }) => setCohorts(data.results || [])).catch(() => {})
  }, [])

  async function run() {
    if (gap === 'cohort' && !cohortId) { setMsg('Hãy chọn đợt/khóa.'); return }
    setLoading(true); setMsg(''); setRan(true)
    try {
      const { data } = await api.get('/employees/competency-gap/', {
        params: { gap, level_group: level || undefined, cohort: gap === 'cohort' ? cohortId : undefined },
      })
      setRows(data)
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Lọc thất bại.')
    } finally { setLoading(false) }
  }

  function exportCsv() {
    const cell = (c) => '"' + String(c == null ? '' : c).split('"').join('""') + '"'
    const head = ['Mã', 'Họ tên', 'Nhà hàng', 'Vị trí', 'Level']
    const lines = rows.map((r) => [r.code, r.name, r.restaurant_name, r.position, r.job_level])
    const csv = [head, ...lines].map((r) => r.map(cell).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = 'danh_sach_khung_nang_luc.csv'; a.click()
  }

  async function invite() {
    if (!inviteCohort) { setMsg('Chọn đợt để mời.'); return }
    try {
      const { data } = await api.post(`/sourcing/cohorts/${inviteCohort}/bulk-enroll/`, { employee_ids: rows.map((r) => r.id) })
      setMsg(`Đã mời ${data.invited} người vào đợt (đã có sẵn ${data.already_in}).`)
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Mời thất bại.')
    }
  }

  return (
    <AppShell>
      <h2 style={{ marginTop: 0 }}>Lập danh sách theo khung năng lực</h2>
      <p className="muted-note" style={{ marginTop: -6 }}>Lọc nhân sự còn thiếu (chưa đào tạo/đánh giá/thi) để lập danh sách đào tạo, thi, đánh giá — rồi mời vào đợt.</p>

      <FilterBar>
        <select value={gap} onChange={(e) => setGap(e.target.value)}>
          {GAPS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
        </select>
        {gap === 'cohort' && (
          <select value={cohortId} onChange={(e) => setCohortId(e.target.value)}>
            <option value="">— Chọn đợt/khóa —</option>
            {cohorts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
        <select value={level} onChange={(e) => setLevel(e.target.value)}>
          {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
        </select>
        <button onClick={run}>Lọc</button>
      </FilterBar>

      {msg && <p style={{ color: 'var(--forest-dark)' }}>{msg}</p>}
      {loading && <p className="muted-note">Đang lọc...</p>}

      {ran && !loading && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', margin: '8px 0' }}>
            <b>{rows.length} nhân sự còn thiếu.</b>
            {rows.length > 0 && <button className="btn-outline btn-sm" onClick={exportCsv}>Xuất CSV</button>}
            {rows.length > 0 && (
              <>
                <span className="muted-note">Mời cả danh sách vào đợt:</span>
                <select value={inviteCohort} onChange={(e) => setInviteCohort(e.target.value)}>
                  <option value="">— Chọn đợt —</option>
                  {cohorts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <button className="btn-sm" onClick={invite}>Mời hàng loạt</button>
              </>
            )}
          </div>
          <Table>
            <thead><tr><th>Mã</th><th>Họ tên</th><th>Nhà hàng</th><th>Vị trí</th><th>Level</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}><td>{r.code}</td><td>{r.name}</td><td>{r.restaurant_name}</td><td>{r.position}</td><td>{r.job_level}</td></tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={5} className="muted-note">Không có nhân sự nào thiếu mục này (hoặc đã đủ).</td></tr>}
            </tbody>
          </Table>
        </>
      )}
    </AppShell>
  )
}
