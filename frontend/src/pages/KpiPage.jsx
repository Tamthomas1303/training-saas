import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import PhotoSlot from '../components/PhotoSlot'
import SignaturePad from '../components/SignaturePad'
import StatCard from '../components/StatCard'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import { submitGuarded } from '../utils/offlineQueue'
import * as s from './listPageStyles'

const SESSIONS_PAGE_SIZE = 20

function KpiSessionForm({ restaurants, defaultRestaurantId, onSaved }) {
  const [restaurantId, setRestaurantId] = useState(defaultRestaurantId || restaurants[0]?.id || '')
  const [topics, setTopics] = useState([])
  const [topic, setTopic] = useState('')
  const [documentId, setDocumentId] = useState(null)
  const [topicDocUrl, setTopicDocUrl] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [participants, setParticipants] = useState([])
  const [participantSearch, setParticipantSearch] = useState('')
  const [participantResults, setParticipantResults] = useState([])
  const [photos, setPhotos] = useState({ img_tailieu: '', img_lythuyet: '', img_thuchanh: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [pdfUrl, setPdfUrl] = useState('')

  useEffect(() => {
    api.get('/kpi/topics/').then(({ data }) => setTopics(data))
  }, [])

  useEffect(() => {
    if (!participantSearch || !restaurantId) {
      setParticipantResults([])
      return
    }
    const timeout = setTimeout(() => {
      api
        .get('/employees/', { params: { search: participantSearch, restaurant: restaurantId, page_size: 10 } })
        .then(({ data }) => setParticipantResults(data.results.filter((e) => e.employee_status !== 'resigned')))
    }, 300)
    return () => clearTimeout(timeout)
  }, [participantSearch, restaurantId])

  function handleTopicChange(e) {
    const value = e.target.value
    setTopic(value)
    const match = topics.find((t) => `${t.name}${t.category ? ` (${t.category})` : ''}` === value)
    setDocumentId(match ? match.id : null)
    setTopicDocUrl(match ? match.file_url || '' : '')
  }

  function addParticipant(emp) {
    if (participants.some((p) => p.employee_id === emp.id)) return
    setParticipants((prev) => [...prev, { employee_id: emp.id, name: emp.name, position: emp.position, sign: '' }])
    setParticipantSearch('')
    setParticipantResults([])
  }

  function removeParticipant(employeeId) {
    setParticipants((prev) => prev.filter((p) => p.employee_id !== employeeId))
  }

  function setParticipantSign(employeeId, value) {
    setParticipants((prev) =>
      prev.map((p) => (p.employee_id === employeeId ? { ...p, sign: value } : p))
    )
  }

  function resetForm() {
    setTopic('')
    setDocumentId(null)
    setNote('')
    setParticipants([])
    setPhotos({ img_tailieu: '', img_lythuyet: '', img_thuchanh: '' })
  }

  async function save() {
    setSaving(true)
    setError('')
    setMessage('')
    const payload = {
      restaurant: restaurantId,
      topic,
      document: documentId,
      date,
      note,
      participants: participants.map((p) => ({ employee: p.employee_id, sign: p.sign })),
      ...photos,
    }
    await submitGuarded(
      'kpi',
      (p) => api.post('/kpi/sessions/save/', p).then((r) => r.data),
      payload,
      {
        onOk: (data) => {
          setMessage(`Đã lưu buổi đào tạo (${data.participant_count} người tham gia).`)
          setPdfUrl(data.pdf_url || '')
          resetForm()
          onSaved?.()
        },
        onErr: setError,
        onQueued: () => setMessage('Mất mạng - đã lưu nháp offline, sẽ tự đồng bộ khi có mạng.'),
      }
    )
    setSaving(false)
  }

  const canPickRestaurant = !defaultRestaurantId

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3 style={{ marginTop: 0 }}>Ghi buổi đào tạo KPI</h3>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Nhà hàng</label>
        {canPickRestaurant ? (
          <select value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)} style={s.select}>
            {restaurants.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={restaurants.find((r) => r.id === Number(restaurantId))?.name || ''}
            disabled
            style={s.input}
          />
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Chủ đề đào tạo</label>
        <input
          list="kpi-topic-list"
          value={topic}
          onChange={handleTopicChange}
          placeholder="Gõ để tìm chủ đề..."
          style={{ ...s.input, width: '100%' }}
        />
        <datalist id="kpi-topic-list">
          {topics.map((t) => (
            <option key={t.id} value={`${t.name}${t.category ? ` (${t.category})` : ''}`} />
          ))}
        </datalist>
        {topicDocUrl && (
          <a
            href={topicDocUrl}
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'inline-block', marginTop: 6, padding: '6px 12px', borderRadius: 8,
              background: 'var(--forest)', color: '#fff', fontSize: 13, textDecoration: 'none',
            }}
          >
            📄 Xem tài liệu
          </a>
        )}
        {topics.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--amber)' }}>
            Chưa có tài liệu chuẩn nào — vào màn Checklist / Tài liệu để thêm.
          </div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Ngày</label>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={s.input} />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: 'var(--muted)' }}>Người tham gia</label>
        <input
          value={participantSearch}
          onChange={(e) => setParticipantSearch(e.target.value)}
          placeholder="Tìm nhân sự theo mã / tên để thêm..."
          style={{ ...s.input, width: '100%' }}
        />
        {participantResults.length > 0 && (
          <div style={{ border: '1px solid var(--card-border)', borderRadius: 6, marginTop: 4 }}>
            {participantResults.map((emp) => (
              <div
                key={emp.id}
                onClick={() => addParticipant(emp)}
                style={{ padding: 8, cursor: 'pointer', borderBottom: '1px solid var(--card-border)' }}
              >
                {emp.code} — {emp.name} ({emp.position})
              </div>
            ))}
          </div>
        )}
      </div>

      {participants.map((p) => (
        <div
          key={p.employee_id}
          style={{
            display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 12, flexWrap: 'wrap',
            borderBottom: '1px solid var(--card-border)', paddingBottom: 12,
          }}
        >
          <div style={{ minWidth: 160 }}>
            <div style={{ fontWeight: 'bold' }}>{p.name}</div>
            <div className="muted-note" style={{ fontSize: 12 }}>{p.position}</div>
            <button
              className="btn-outline btn-sm"
              onClick={() => removeParticipant(p.employee_id)}
              style={{ marginTop: 4 }}
            >
              Xóa
            </button>
          </div>
          <SignaturePad
            label="Chữ ký"
            value={p.sign}
            onChange={(v) => setParticipantSign(p.employee_id, v)}
          />
        </div>
      ))}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', margin: '16px 0' }}>
        <PhotoSlot label="Tài liệu" value={photos.img_tailieu} onChange={(v) => setPhotos((p) => ({ ...p, img_tailieu: v }))} />
        <PhotoSlot label="Lý thuyết" value={photos.img_lythuyet} onChange={(v) => setPhotos((p) => ({ ...p, img_lythuyet: v }))} />
        <PhotoSlot label="Thực hành" value={photos.img_thuchanh} onChange={(v) => setPhotos((p) => ({ ...p, img_thuchanh: v }))} />
      </div>

      <textarea
        placeholder="Ghi chú..."
        value={note}
        onChange={(e) => setNote(e.target.value)}
        style={{ width: '100%', minHeight: 60, marginBottom: 12 }}
      />

      <button disabled={saving} onClick={save}>
        Lưu buổi đào tạo & xuất PDF
      </button>

      {saving && <p className="muted-note">Đang lưu...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {message && (
        <p style={{ color: 'var(--forest-dark)' }}>
          {message}{' '}
          {pdfUrl && (
            <a href={pdfUrl} target="_blank" rel="noreferrer">
              Xem biên bản PDF
            </a>
          )}
        </p>
      )}
    </div>
  )
}

const REPORT_ROLES = new Set(['admin', 'om'])
const PERFORM_ROLES = new Set(['trainer', 'bql', 'am', 'kcs'])

function KpiStatsSummary() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/kpi/stats/')
      .then(({ data }) => setStats(data))
      .catch(() => setError('Không tải được thống kê KPI.'))
  }, [])

  if (error) return <p style={{ color: 'var(--danger)' }}>{error}</p>
  if (!stats) return <p className="muted-note">Đang tải thống kê...</p>

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3 style={{ marginTop: 0 }}>Thống kê KPI</h3>
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <StatCard label="Tổng số buổi đào tạo" value={stats.total_classes ?? 0} />
        <StatCard label="Tổng lượt tham gia" value={stats.total_joins ?? 0} />
        <StatCard label="TB người tham gia/buổi" value={stats.avg_per_class ?? 0} />
      </div>
      {stats.top_topics?.length > 0 && (
        <>
          <div className="stat-label" style={{ marginBottom: 6 }}>
            Chủ đề được đào tạo nhiều nhất
          </div>
          {stats.top_topics.slice(0, 5).map((t) => (
            <div key={t.topic} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, padding: '4px 0' }}>
              <span>{t.topic}</span>
              <span>{t.count}</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function ExportedReportSlot({ label, data, exportingKey, exporting, onExport }) {
  return (
    <div>
      <div style={{ marginBottom: 4, fontWeight: 'bold', fontSize: 13 }}>{label}</div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {data?.exported_url ? (
          <a href={data.exported_url} target="_blank" rel="noreferrer" className="btn-outline btn-sm">
            Xem
          </a>
        ) : (
          <span className="muted-note" style={{ fontSize: 12 }}>Chưa xuất</span>
        )}
        <button className="btn-outline btn-sm" onClick={onExport} disabled={exporting === exportingKey}>
          {data?.exported_url ? 'Xuất lại' : 'Xuất PDF'}
        </button>
      </div>
    </div>
  )
}

function KpiReportSection({ month, year, setMonth, setYear }) {
  const [report, setReport] = useState(null)
  const [allowance, setAllowance] = useState(null)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState('')

  useEffect(() => {
    setError('')
    api
      .get('/kpi/report/', { params: { month, year } })
      .then(({ data }) => setReport(data))
      .catch(() => setError('Không tải được báo cáo KPI BQL.'))
    api
      .get('/kpi/allowance/', { params: { month, year } })
      .then(({ data }) => setAllowance(data))
      .catch(() => setError('Không tải được danh sách phụ cấp.'))
  }, [month, year])

  async function exportReport() {
    setExporting('report')
    try {
      const { data } = await api.post('/kpi/report/export/', null, { params: { month, year } })
      setReport((prev) => (prev ? { ...prev, exported_url: data.pdf_url } : prev))
    } catch {
      setError('Không xuất được báo cáo KPI BQL.')
    } finally {
      setExporting('')
    }
  }

  async function exportAllowance() {
    setExporting('allowance')
    try {
      const { data } = await api.post('/kpi/allowance/export/', null, { params: { month, year } })
      setAllowance((prev) => (prev ? { ...prev, exported_url: data.pdf_url } : prev))
    } catch {
      setError('Không xuất được phiếu phụ cấp trainer.')
    } finally {
      setExporting('')
    }
  }

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <h3 style={{ marginTop: 0 }}>Báo cáo KPI BQL & Phụ cấp trainer</h3>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <select value={month} onChange={(e) => setMonth(Number(e.target.value))} style={s.select}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>
              Tháng {m}
            </option>
          ))}
        </select>
        <input
          type="number"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          style={{ ...s.input, width: 100 }}
        />
      </div>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 'bold', marginBottom: 10 }}>
          Phiếu kỳ {month}/{year}
        </div>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          <ExportedReportSlot
            label="Báo cáo KPI BQL"
            data={report}
            exportingKey="report"
            exporting={exporting}
            onExport={exportReport}
          />
          <ExportedReportSlot
            label="Phiếu phụ cấp trainer"
            data={allowance}
            exportingKey="allowance"
            exporting={exporting}
            onExport={exportAllowance}
          />
        </div>
      </div>

      {report && (
        <>
          <div className="muted-note" style={{ marginBottom: 6 }}>
            Đúng lộ trình: {report.totals.on_num}/{report.totals.on_den} ({report.totals.on_rate}%) · Đạt kỹ năng
            lần đầu: {report.totals.skill_pass}/{report.totals.skill_total} ({report.totals.skill_rate}%)
          </div>
          {(report.totals.excl_resigned > 0 || report.totals.excl_next_period > 0) && (
            <div className="muted-note" style={{ marginBottom: 6, fontSize: 12 }}>
              Loại trừ toàn hệ thống: {report.totals.excl_resigned} nghỉ việc, {report.totals.excl_next_period} đánh
              giá kỳ sau.
            </div>
          )}
          <Table>
            <thead>
              <tr>
                <th>Nhà hàng</th>
                <th>Đúng lộ trình</th>
                <th>Đạt KN lần đầu</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.restaurant}>
                  <td>
                    {r.restaurant}
                    {(r.excl_resigned > 0 || r.excl_next_period > 0) && (
                      <div className="muted-note" style={{ fontSize: 11 }}>
                        (loại {r.excl_resigned} nghỉ việc; {r.excl_next_period} đánh giá kỳ sau)
                      </div>
                    )}
                  </td>
                  <td>
                    {r.on_num}/{r.on_den} ({r.on_den > 0 ? `${r.on_rate}%` : '—'})
                  </td>
                  <td>
                    {r.skill_pass}/{r.skill_total} ({r.skill_total > 0 ? `${r.skill_rate}%` : '—'})
                  </td>
                </tr>
              ))}
              {report.rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="muted-note">
                    Không có dữ liệu.
                  </td>
                </tr>
              )}
            </tbody>
          </Table>

          {report.am_kcs?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="stat-label" style={{ marginBottom: 6 }}>
                Thống kê theo AM / KCS / OM
              </div>
              <Table>
                <thead>
                  <tr>
                    <th>Vị trí</th>
                    <th>Người phụ trách</th>
                    <th>Phạm vi</th>
                    <th>Số NV trong kỳ</th>
                    <th>Đúng lộ trình</th>
                    <th>Đạt KN lần đầu</th>
                  </tr>
                </thead>
                <tbody>
                  {report.am_kcs.map((item, idx) => (
                    <tr key={`${item.role}-${item.name}-${idx}`}>
                      <td>{item.role}</td>
                      <td>{item.name}</td>
                      <td>{item.scope}</td>
                      <td>{item.emp_count}</td>
                      <td>{item.on_den > 0 ? `${item.on_rate}%` : '—'}</td>
                      <td>{item.skill_total > 0 ? `${item.skill_rate}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </>
      )}

      {allowance && (
        <div style={{ marginTop: 16 }}>
          <div className="muted-note" style={{ marginBottom: 6 }}>
            Tổng phụ cấp: {Math.round(allowance.total_amount).toLocaleString('vi-VN')}đ
          </div>
        </div>
      )}
    </div>
  )
}

export default function KpiPage() {
  const { user } = useAuth()
  const role = (user.role || '').toLowerCase()
  const canPerform = PERFORM_ROLES.has(role)
  const canSeeReport = REPORT_ROLES.has(role)
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [restaurantFilter, setRestaurantFilter] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })
  const { data: sessions, loading } = usePaginatedList('/kpi/sessions/', {
    restaurant: restaurantFilter || undefined,
    // Bang bien ban buoi dao tao chi loc theo ky (Thang/Nam) cho vai tro xem duoc bao cao -
    // cac vai tro con lai (trainer/BQL/AM/KCS) van xem toan bo lich su nhu truoc.
    month: canSeeReport ? month : undefined,
    year: canSeeReport ? year : undefined,
    page,
    page_size: SESSIONS_PAGE_SIZE,
    refreshKey,
  })

  return (
    <AppShell>
      <h2>KPI đào tạo</h2>

      {canSeeReport && <KpiReportSection month={month} year={year} setMonth={setMonth} setYear={setYear} />}
      {role === 'admin' && <KpiStatsSummary />}

      {canPerform && restaurantOptions.results.length > 0 && (
        <KpiSessionForm
          restaurants={restaurantOptions.results}
          defaultRestaurantId={user?.restaurant || null}
          onSaved={() => setRefreshKey((k) => k + 1)}
        />
      )}

      <h3>Danh sách buổi đã ghi{canSeeReport ? ` — kỳ ${month}/${year}` : ''}</h3>
      <FilterBar>
        <select
          value={restaurantFilter}
          onChange={(e) => { setRestaurantFilter(e.target.value); setPage(1) }}
          style={s.select}
        >
          <option value="">Tất cả nhà hàng</option>
          {restaurantOptions.results.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      <div className="table-sticky">
        <Table>
          <thead>
            <tr>
              <th>Ngày</th>
              <th>Nhà hàng</th>
              <th>Chủ đề</th>
              <th>Người ĐT</th>
              <th>SL</th>
              <th>Biên bản</th>
            </tr>
          </thead>
          <tbody>
            {sessions.results.map((sess) => (
              <tr key={sess.id}>
                <td>{sess.date}</td>
                <td>{sess.restaurant_name}</td>
                <td>{sess.topic}</td>
                <td>{sess.trainer_name}</td>
                <td>{sess.participant_count}</td>
                <td>
                  {sess.pdf_url ? (
                    <a href={sess.pdf_url} target="_blank" rel="noreferrer">
                      Xem
                    </a>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            ))}
            {sessions.results.length === 0 && (
              <tr>
                <td colSpan={6} className="muted-note">
                  Không có dữ liệu.
                </td>
              </tr>
            )}
          </tbody>
        </Table>
      </div>
      <Pager page={page} pageSize={SESSIONS_PAGE_SIZE} count={sessions.count} onChange={setPage} />
    </AppShell>
  )
}
