import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import BackButton from '../components/BackButton'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Table from '../components/Table'
import Pager from '../components/Pager'
import api from '../api/client'

const TARGET_LABEL = { GS: 'Giám sát', BP: 'Bếp phó', BTr: 'Bếp trưởng', QL: 'Quản lý' }
const MGMT_PAGE_SIZE = 20

function statusVariant(s) {
  const t = (s || '').toLowerCase()
  if (t.includes('sẵn sàng')) return 'success'
  if (t.includes('hoàn thiện')) return 'warning'
  return 'neutral'
}

export default function MgmtDevPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [term, setTerm] = useState('')
  const [target, setTarget] = useState('')
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    api.get('/employees/mgmt-development/').then(({ data }) => setRows(data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const shown = rows.filter((r) =>
    (!term || r.name.toLowerCase().includes(term.toLowerCase()) || (r.code || '').toLowerCase().includes(term.toLowerCase())) &&
    (!target || r.target_code === target))
  const pageRows = shown.slice((page - 1) * MGMT_PAGE_SIZE, page * MGMT_PAGE_SIZE)

  return (
    <AppShell>
      <BackButton />
      <h2 style={{ marginTop: 0 }}>Ban quản lý — Đào tạo & Đánh giá</h2>
      <p className="muted-note" style={{ marginTop: -6 }}>Nội dung đã đào tạo, điểm thi theo vai, đánh giá và trạng thái sẵn sàng của nhân sự cấp O.</p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <input style={{ maxWidth: 320 }} placeholder="Tìm tên / mã..." value={term} onChange={(e) => { setTerm(e.target.value); setPage(1) }} />
        <select value={target} onChange={(e) => { setTarget(e.target.value); setPage(1) }}>
          <option value="">Tất cả vị trí đích</option>
          {Object.entries(TARGET_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {loading ? <p className="muted-note">Đang tải...</p> : (
        <>
        <div className="table-sticky"><Table>
          <thead>
            <tr><th>Nhân sự</th><th>Nhà hàng</th><th>Vị trí</th><th>Đích</th><th>Trạng thái</th><th>Tiên quyết</th><th>Khóa/Buổi</th><th></th></tr>
          </thead>
          <tbody>
            {pageRows.map((r) => (
              <tr key={r.employee_id}>
                <td>{r.name} - {r.code}</td>
                <td>{r.restaurant_name}</td>
                <td>{r.position} <span className="muted-note">{r.job_level}</span></td>
                <td>{TARGET_LABEL[r.target_code] || r.target_code}</td>
                <td><Badge variant={statusVariant(r.final_status)}>{r.final_status || '—'}</Badge></td>
                <td>{r.prerequisites?.ok ? <Badge variant="success">Đủ</Badge> : <Badge variant="warning">Thiếu</Badge>}</td>
                <td>{r.courses_attended} khóa / {r.sessions_attended} buổi</td>
                <td><button className="btn-outline btn-sm" onClick={() => setDetail(r)}>Chi tiết</button></td>
              </tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={8} className="muted-note">Chưa có dữ liệu Ban quản lý. Hãy đồng bộ roster + nạp lịch sử (có link Daotao_BQL).</td></tr>}
          </tbody>
        </Table></div>
        <Pager page={page} pageSize={MGMT_PAGE_SIZE} count={shown.length} onChange={setPage} />
        </>
      )}

      {detail && (
        <Modal open title={`${detail.name} — ${detail.code}`} onClose={() => setDetail(null)} footer={<button className="btn-outline" onClick={() => setDetail(null)}>Đóng</button>}>
          <div className="muted-note" style={{ marginBottom: 8 }}>
            {detail.position} · {detail.restaurant_name} · Đích: {TARGET_LABEL[detail.target_code] || detail.target_code} · {detail.source}
          </div>
          <div style={{ marginBottom: 6 }}><b>Trạng thái:</b> <Badge variant={statusVariant(detail.final_status)}>{detail.final_status || '—'}</Badge></div>

          <div style={{ fontWeight: 700, marginTop: 10 }}>Điều kiện tiên quyết</div>
          {(detail.prerequisites?.items || []).map((it, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '2px 0' }}>
              <span style={{ color: it.ok ? 'var(--forest)' : 'var(--danger)' }}>{it.ok ? '✓' : '✗'}</span>
              <span style={{ fontSize: 14 }}>{it.label}{it.missing?.length ? ` — thiếu: ${it.missing.join(', ')}` : ''}</span>
            </div>
          ))}
          {(!detail.prerequisites?.items || detail.prerequisites.items.length === 0) && <div className="muted-note">Không có yêu cầu tiên quyết.</div>}

          <div style={{ fontWeight: 700, marginTop: 10 }}>Nội dung đã đào tạo ({detail.topics.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
            {detail.topics.map((t) => <span key={t} className="badge badge-mint">{t}</span>)}
            {detail.topics.length === 0 && <span className="muted-note">—</span>}
          </div>

          <div style={{ fontWeight: 700, marginTop: 12 }}>Điểm thi theo vai</div>
          <Table>
            <thead><tr><th>Vai</th><th>Điểm</th><th>Kết quả</th></tr></thead>
            <tbody>
              {Object.entries(detail.scores).map(([role, v]) => (
                <tr key={role}><td>{role}</td><td>{v.score || '—'}</td><td>{v.result || '—'}</td></tr>
              ))}
              {Object.keys(detail.scores).length === 0 && <tr><td colSpan={3} className="muted-note">—</td></tr>}
            </tbody>
          </Table>

          <div style={{ fontWeight: 700, marginTop: 12 }}>Đánh giá</div>
          <Table>
            <thead><tr><th>Hạng mục</th><th>Kết quả</th></tr></thead>
            <tbody>
              {Object.entries(detail.assessments).filter(([, v]) => v).map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v}</td></tr>
              ))}
              {Object.values(detail.assessments).every((v) => !v) && <tr><td colSpan={2} className="muted-note">—</td></tr>}
            </tbody>
          </Table>
          <div className="muted-note" style={{ fontSize: 12, marginTop: 8 }}>Đã tham gia {detail.courses_attended} khóa · {detail.sessions_attended} buổi (xem chi tiết ở ĐT nguồn).</div>
        </Modal>
      )}
    </AppShell>
  )
}
