import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  BookOpen, Circle, DoorOpen, Flag, FileText, PencilLine, Target, Video, CheckCircle2,
} from 'lucide-react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import ProgressBar from '../components/ProgressBar'
import RadarChart from '../components/RadarChart'
import StatCard from '../components/StatCard'
import api from '../api/client'
import * as s from './listPageStyles'

const COLOR_BADGE = { green: 'success', yellow: 'warning', red: 'danger' }

const TIMELINE_ICON = {
  joined: DoorOpen, course: Video, exam: PencilLine, evaluation: CheckCircle2, pass: Flag,
}

function fmtDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('vi-VN')
}

function IndicatorPill({ indicator }) {
  if (indicator.pending) {
    return <span className="badge badge-neutral">{indicator.label}: Chờ dữ liệu</span>
  }
  const variant = COLOR_BADGE[indicator.color] || 'neutral'
  return <Badge variant={variant}>{indicator.label}: {indicator.value}</Badge>
}

export default function Employee360Page() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return undefined
    }
    const timeout = setTimeout(() => {
      api.get('/dashboard/employees/', { params: { q: query.trim() } })
        .then(({ data }) => setResults(Array.isArray(data) ? data : []))
    }, 300)
    return () => clearTimeout(timeout)
  }, [query])

  function loadEmployee(idOrCode) {
    setLoading(true)
    setError('')
    setResults([])
    api.get(`/dashboard/employee/${idOrCode}/`)
      .then(({ data }) => { setProfile(data); setQuery('') })
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được hồ sơ.'))
      .finally(() => setLoading(false))
  }

  // Drill-down tu man tong hop CEO/GDDT (Prompt_Dashboard_B_ManTongHop.md, muc 3):
  // /employee-360?employee=<id|code> -> tu dong mo ho so, khong can go tim lai.
  useEffect(() => {
    const target = searchParams.get('employee')
    if (target) loadEmployee(target)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const groups = profile?.groups || []
  const radarLabels = groups.map((g) => g.name)
  const notAssessed = profile?.competency_status === 'not_assessed'
  const radarActual = notAssessed ? groups.map(() => null) : groups.map((g) => g.score)
  const radarTarget = groups.map((g) => g.target)
  const isLegacy = !!profile?.employee?.is_legacy
  const probationStatusLabel = isLegacy
    ? 'Đã pass — công nhận theo thâm niên'
    : (profile?.employee?.final_result || 'Chưa có kết quả')
  const achievedPositions = profile?.achieved_positions || []

  return (
    <AppShell>
      <h2>Hồ sơ 360</h2>

      <div className="card" style={{ marginBottom: 16 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Gõ tên hoặc mã nhân sự..."
          style={{ ...s.input, width: '100%' }}
        />
        {results.length > 0 && (
          <div style={{ border: '1px solid var(--card-border)', borderRadius: 6, marginTop: 4 }}>
            {results.map((r) => (
              <div key={r.id} onClick={() => loadEmployee(r.id)} style={{ padding: 8, cursor: 'pointer' }}>
                {r.code} — {r.name} ({r.position}{r.restaurant ? ` · ${r.restaurant}` : ''})
              </div>
            ))}
          </div>
        )}
      </div>

      {loading && <p className="muted-note">Đang tải hồ sơ...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {profile && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
              <div>
                <strong style={{ fontSize: 18 }}>{profile.employee.name}</strong>
                <div className="muted-note">
                  {profile.employee.code} · {profile.employee.position || '—'}
                  {profile.employee.restaurant ? ` · ${profile.employee.restaurant}` : ''}
                </div>
                <div className="muted-note">
                  Vào làm: {fmtDate(profile.employee.start_date) || '—'} · Trạng thái: {profile.employee.employee_status}
                </div>
              </div>
              <div>
                <Badge variant={isLegacy || profile.employee.pass_date ? 'success' : 'neutral'}>
                  {probationStatusLabel}
                </Badge>
              </div>
            </div>
            {(profile.warnings || []).length > 0 && (
              <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {(profile.warnings || []).map((w, i) => (
                  <Badge key={i} variant={w.type === 'overdue' ? 'danger' : 'warning'}>{w.label}</Badge>
                ))}
              </div>
            )}
          </div>

          <div className="stat-grid" style={{ marginBottom: 16 }}>
            <StatCard icon={<Target size={16} />} label="Chỉ số năng lực (CI)" value={notAssessed ? 'Chưa đánh giá' : (profile.ci ?? 'Chờ dữ liệu')} />
            <StatCard icon={<Flag size={16} />} label="Lộ trình thử việc" value={probationStatusLabel} />
            <StatCard
              icon={<BookOpen size={16} />} label="Tiến độ học"
              value={isLegacy ? 'Công nhận theo thâm niên' : `${profile.study.done}/${profile.study.total}`}
            />
            <StatCard
              icon={<FileText size={16} />} label="Điểm thi TB"
              value={notAssessed ? 'Chưa đánh giá' : (profile.exam.avg_percent != null ? `${profile.exam.avg_percent}%` : 'Chờ dữ liệu')}
            />
          </div>

          {(profile.indicators || []).length > 0 && (
            <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {profile.indicators.map((ind) => <IndicatorPill key={ind.key} indicator={ind} />)}
            </div>
          )}

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start', marginBottom: 16 }}>
            <div className="card" style={{ flex: '1 1 420px', minWidth: 320 }}>
              <h3 style={{ marginTop: 0 }}>Radar năng lực (Thực tế vs Mục tiêu)</h3>
              {groups.length > 0 ? (
                <div style={{ position: 'relative' }}>
                  <RadarChart labels={radarLabels} actual={radarActual} target={radarTarget} />
                  {notAssessed && (
                    <div style={{
                      position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                      alignItems: 'center', justifyContent: 'center', textAlign: 'center', pointerEvents: 'none',
                    }}>
                      <span style={{ fontSize: 18, fontWeight: 600, color: 'var(--muted)' }}>Chưa đánh giá</span>
                      {isLegacy && (
                        <span className="muted-note" style={{ fontSize: 12, marginTop: 4 }}>
                          Nhân sự cũ — cần Đánh giá đầu kỳ
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <p className="muted-note">Chưa cấu hình khung năng lực.</p>
              )}
            </div>

            <div className="card" style={{ flex: '1 1 320px', minWidth: 280 }}>
              <h3 style={{ marginTop: 0 }}>Khoảng trống & gợi ý khóa học</h3>
              {(profile.gaps || []).length === 0 && <p className="muted-note">Không có khoảng trống đáng kể (hoặc chưa đủ dữ liệu).</p>}
              {(profile.gaps || []).map((g) => (
                <div key={g.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--card-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{g.name}</span>
                    <span className="muted-note">{g.score}/{g.target} (thiếu {g.gap})</span>
                  </div>
                  {(g.suggested_courses || []).length > 0 && (
                    <div className="muted-note" style={{ fontSize: 12, marginTop: 2 }}>
                      Gợi ý: {g.suggested_courses.map((c) => c.title).join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
            <div className="card" style={{ flex: '1 1 260px', minWidth: 220 }}>
              <h3 style={{ marginTop: 0 }}>Học</h3>
              {isLegacy ? (
                <div className="muted-note">Công nhận theo thâm niên</div>
              ) : (
                <>
                  <ProgressBar percent={profile.study.total ? (profile.study.done / profile.study.total) * 100 : 0} />
                  <div className="muted-note" style={{ marginTop: 6 }}>{profile.study.done}/{profile.study.total} khóa hoàn thành</div>
                </>
              )}
            </div>
            <div className="card" style={{ flex: '1 1 260px', minWidth: 220 }}>
              <h3 style={{ marginTop: 0 }}>Thi</h3>
              <div>{profile.exam.attempts} lượt thi</div>
              <div className="muted-note">
                Điểm TB: {notAssessed ? 'Chưa đánh giá' : `${profile.exam.avg_percent ?? '—'}%`}
              </div>
            </div>
            <div className="card" style={{ flex: '1 1 260px', minWidth: 220 }}>
              <h3 style={{ marginTop: 0 }}>Chứng chỉ</h3>
              {(profile.certificates || []).length === 0 && <p className="muted-note">Chưa có chứng chỉ.</p>}
              {(profile.certificates || []).map((c) => (
                <div key={c.id} style={{ fontSize: 13, marginBottom: 4 }}>
                  {c.program_name || c.ref_type} · {c.code}
                  {c.pdf_url && (
                    <> · <a href={c.pdf_url} target="_blank" rel="noreferrer">Xem</a></>
                  )}
                </div>
              ))}
            </div>
            <div className="card" style={{ flex: '1 1 260px', minWidth: 220 }}>
              <h3 style={{ marginTop: 0 }}>Vị trí đã trải qua</h3>
              {achievedPositions.length === 0 && <p className="muted-note">Chưa có dữ liệu.</p>}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {achievedPositions.map((pos, i) => (
                  <Badge key={`${pos}-${i}`} variant={i === 0 ? 'success' : 'neutral'}>
                    {pos}{i === 0 ? ' (hiện tại)' : ''}
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Dòng thời gian</h3>
            {(profile.timeline || []).map((ev, i) => {
              const EvIcon = TIMELINE_ICON[ev.type] || Circle
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--card-border)' }}>
                  <EvIcon size={14} color="var(--muted)" />
                  <span className="muted-note" style={{ minWidth: 90 }}>{fmtDate(ev.date)}</span>
                  <span>{ev.label}</span>
                </div>
              )
            })}
          </div>
        </>
      )}
    </AppShell>
  )
}
