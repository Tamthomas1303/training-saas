import { useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const REF_TYPES = [
  { value: '', label: 'Tất cả loại' },
  { value: 'course', label: 'Khóa học' },
  { value: 'assessment', label: 'Đề thi' },
  { value: 'program', label: 'Chương trình' },
]

export default function CertificatesAdminPage() {
  const [refType, setRefType] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [reissuingId, setReissuingId] = useState(null)

  const { data, loading } = usePaginatedList('/integration/certificates/', {
    ref_type: refType || undefined, page, page_size: PAGE_SIZE, refreshKey,
  })

  async function reissue(id) {
    setReissuingId(id)
    try {
      await api.post(`/integration/certificates/${id}/reissue/`)
      setRefreshKey((k) => k + 1)
    } finally {
      setReissuingId(null)
    }
  }

  return (
    <AppShell>
      <h2>Chứng chỉ đã cấp</h2>

      <FilterBar>
        <select value={refType} onChange={(e) => { setRefType(e.target.value); setPage(1) }} style={s.select}>
          {REF_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      <Table>
        <thead>
          <tr>
            <th>Mã</th><th>Nhân sự</th><th>Loại</th><th>Chương trình</th><th>Ngày cấp</th><th></th>
          </tr>
        </thead>
        <tbody>
          {data.results.map((c) => (
            <tr key={c.id}>
              <td>{c.code}</td>
              <td>{c.employee_code} — {c.employee_name}</td>
              <td>{c.ref_type_display}</td>
              <td>{c.program_name || '-'}</td>
              <td>{c.issue_date}</td>
              <td style={{ display: 'flex', gap: 6 }}>
                {c.pdf_url && (
                  <a href={c.pdf_url} target="_blank" rel="noreferrer" className="btn-outline btn-sm">Tải PDF</a>
                )}
                <button className="btn-outline btn-sm" onClick={() => reissue(c.id)} disabled={reissuingId === c.id}>
                  Cấp lại
                </button>
              </td>
            </tr>
          ))}
          {data.results.length === 0 && !loading && (
            <tr><td colSpan={6} className="muted-note">Chưa có chứng chỉ nào.</td></tr>
          )}
        </tbody>
      </Table>
      <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
    </AppShell>
  )
}
