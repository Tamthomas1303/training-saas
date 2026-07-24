import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import BackButton from '../components/BackButton'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Modal from '../components/Modal'
import ProgressBar from '../components/ProgressBar'
import Table from '../components/Table'
import Pager from '../components/Pager'
import SignaturePad from '../components/SignaturePad'
import CouncilPanel from '../components/CouncilPanel'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const EMP_STATUS = { probation: 'Thử việc', active: 'Chính thức', resigned: 'Nghỉ việc' }

const STATUS_LABELS = {
  registered: 'Đăng ký', training: 'Đang đào tạo', completed: 'Hoàn thành', failed: 'Không đạt',
}
const STATUS_VARIANTS = {
  registered: 'warning', training: 'mint', completed: 'success', failed: 'danger',
}

function roleFlags(role) {
  const r = (role || '').toLowerCase()
  return {
    r,
    canRegister: ['admin', 'om', 'bql'].includes(r),
    canOpen: ['admin', 'om', 'trainer'].includes(r),
    canDecide: ['admin', 'om'].includes(r),
    canEvaluate: ['admin', 'om', 'bql', 'am', 'kcs'].includes(r),
    canReview: ['admin', 'om', 'am', 'kcs'].includes(r),
    isTraining: ['admin', 'om'].includes(r),
  }
}

// ---- Form chấm đánh giá 1 vòng (Skill_BQL / AM_KCS) ----
function RoundEvalForm({ criteria, defaultType, allowTypeChoice, onDone }) {
  const [evalType, setEvalType] = useState(defaultType)
  const [scores, setScores] = useState({})
  const [signEval, setSignEval] = useState('')
  const [signTrainee, setSignTrainee] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const total = criteria.reduce((a, c) => a + (Number(scores[c.criteria_id]) || 0), 0)
  const maxTotal = criteria.reduce((a, c) => a + c.max_score, 0)
  const percent = maxTotal ? Math.round((total / maxTotal) * 100) : 0

  async function submit(complete) {
    setBusy(true)
    setMsg('')
    try {
      await onDone({
        eval_type: evalType,
        details: criteria.map((c) => ({ criteria_id: c.criteria_id, score: Number(scores[c.criteria_id]) || 0 })),
        sign_evaluator: signEval || undefined,
        sign_trainee: signTrainee || undefined,
        complete,
      })
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Không lưu được đánh giá.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {allowTypeChoice && (
        <label style={{ display: 'block', marginBottom: 10 }}>
          Loại đánh giá
          <select style={{ display: 'block', width: '100%' }} value={evalType} onChange={(e) => setEvalType(e.target.value)}>
            <option value="Skill_BQL">BQL đánh giá kỹ năng</option>
            <option value="AM_KCS">AM/KCS kiểm tra</option>
          </select>
        </label>
      )}
      {criteria.map((c) => (
        <div key={c.criteria_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid var(--card-border)' }}>
          <span style={{ flex: 1, fontSize: 14 }}>{c.content}{c.require_photo ? ' 📷' : ''}</span>
          <input
            type="number" min="0" max={c.max_score}
            value={scores[c.criteria_id] ?? ''}
            onFocus={(e) => e.target.select()}
            onChange={(e) => {
              const raw = Number(e.target.value)
              setScores((v) => ({ ...v, [c.criteria_id]: Math.max(0, Math.min(c.max_score, Number.isNaN(raw) ? 0 : raw)) }))
            }}
            style={{ width: 64 }} placeholder={`0–${c.max_score}`}
          />
        </div>
      ))}
      <div style={{ margin: '10px 0', fontWeight: 700 }}>
        Tổng: {total}/{maxTotal} — <span style={{ color: percent >= 85 ? 'var(--forest)' : 'var(--danger)' }}>{percent}%</span>
      </div>
      <SignaturePad label="Chữ ký người đánh giá" value={signEval} onChange={setSignEval} />
      <div style={{ height: 8 }} />
      <SignaturePad label="Chữ ký nhân viên" value={signTrainee} onChange={setSignTrainee} />
      {msg && <p style={{ color: 'var(--danger)' }}>{msg}</p>}
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button className="btn-outline" disabled={busy} onClick={() => submit(false)}>Lưu nháp</button>
        <button disabled={busy} onClick={() => submit(true)}>{busy ? 'Đang lưu...' : 'Hoàn thành'}</button>
      </div>
      <p className="muted-note" style={{ fontSize: 12 }}>
        Tiêu chí có 📷 cần ảnh minh chứng để hoàn thành (bổ sung ở màn đánh giá đầy đủ nếu bị chặn).
      </p>
    </div>
  )
}

// ---- Modal chi tiết 1 vòng ----
function RoundModal({ enrollmentId, onClose, onChanged }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const f = roleFlags(user?.role)
  const [round, setRound] = useState(null)
  const [err, setErr] = useState('')

  async function load() {
    setErr('')
    try {
      const { data } = await api.get(`/employees/levelup-enrollments/${enrollmentId}/round/`)
      setRound(data)
    } catch (e) {
      setErr(e.response?.data?.detail || 'Không tải được vòng đào tạo.')
    }
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [enrollmentId])

  async function submitEval(payload) {
    await api.post(`/employees/levelup-enrollments/${enrollmentId}/evaluate/`, payload)
    await load()
    onChanged?.()
  }
  async function complete() {
    try {
      const { data } = await api.post(`/employees/levelup-enrollments/${enrollmentId}/complete/`)
      alert(data.message || 'Đã lên level.')
      if (data.proposal_pdf_url) window.open(data.proposal_pdf_url, '_blank')
      onChanged?.()
      onClose()
    } catch (e) {
      alert(e.response?.data?.detail || 'Chưa đủ điều kiện lên level.')
    }
  }

  const c = round?.completion
  const evalType = f.r === 'bql' ? 'Skill_BQL' : (['am', 'kcs'].includes(f.r) ? 'AM_KCS' : 'Skill_BQL')

  return (
    <Modal open title="Vòng thăng tiến" onClose={onClose} footer={<button className="btn-outline" onClick={onClose}>Đóng</button>}>
      {err && <p style={{ color: 'var(--danger)' }}>{err}</p>}
      {!round && !err && <p className="muted-note">Đang tải...</p>}
      {round && (
        <div style={{ display: 'grid', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700 }}>{round.employee_name}</div>
            <div className="muted-note">
              Vị trí đích: <b>{round.target_position}</b> · {round.from_level} → {round.target_level} · Đợt {round.exam_batch} ·{' '}
              <Badge variant={STATUS_VARIANTS[round.status]}>{STATUS_LABELS[round.status]}</Badge>
            </div>
          </div>

          {/* Điều kiện lên level */}
          <div className="card" style={{ padding: 10 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Điều kiện lên level</div>
            <Cond ok={c?.lms} label="LMS học xong" />
            <Cond ok={c?.checklist_ok} label={`Đào tạo vị trí đích 100% (hiện ${c?.checklist_percent ?? 0}%)`} />
            <Cond ok={c?.exam_pass} label={`Thi lý thuyết đạt (điểm ${c?.exam_score ?? 0})`} />
            <Cond
              ok={c?.combined_ok}
              label={`Điểm tổng 40/60 ≥ 85% ${c?.combined_score != null ? `(hiện ${c.combined_score}%)` : '(chưa có đánh giá kỹ năng)'}`}
            />
            {f.canDecide && (
              <button style={{ marginTop: 8 }} disabled={!c?.can_complete} onClick={complete} title={c?.reason}>
                Chốt lên level
              </button>
            )}
            {!c?.can_complete && c?.reason && <p className="muted-note" style={{ fontSize: 12 }}>Còn thiếu: {c.reason}</p>}
            {round.proposal_pdf_url && (
              <p style={{ marginTop: 8 }}>
                <a href={round.proposal_pdf_url} target="_blank" rel="noreferrer">📄 Xem phiếu đề xuất lên level</a>
              </p>
            )}
          </div>

          {/* Checklist vị trí đích */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Checklist vị trí đích — {round.progress_percent}%</div>
              {round.status === 'training' && (
                <button
                  className="btn-outline btn-sm"
                  onClick={() => navigate('/training', {
                    state: {
                      employee: { id: round.employee_id, name: round.employee_name, position: round.target_position, restaurant_name: '' },
                      position: round.target_position,
                    },
                  })}
                >
                  Đào tạo checklist này »
                </button>
              )}
            </div>
            <ProgressBar percent={round.progress_percent} />
            <Table>
              <thead><tr><th>Ngày</th><th>Nội dung</th><th>Trạng thái</th></tr></thead>
              <tbody>
                {round.checklist.map((it) => (
                  <tr key={it.id}>
                    <td>{it.day}</td>
                    <td>{it.task_name}</td>
                    <td>{it.status === 'done' ? '✅ Xong' : it.status === 'in_progress' ? '⏳ Đang' : '—'}</td>
                  </tr>
                ))}
                {round.checklist.length === 0 && <tr><td colSpan={3} className="muted-note">Chưa có checklist cho vị trí đích.</td></tr>}
              </tbody>
            </Table>
            <p className="muted-note" style={{ fontSize: 12 }}>
              Đào tạo & ký biên bản từng mục thực hiện ở màn "Đào tạo" như thường lệ (checklist vị trí đích).
            </p>
          </div>

          {/* Đánh giá kỹ năng vòng */}
          {round.skill_percent != null && (
            <div className="muted-note">Đã đánh giá kỹ năng: <b>{round.skill_percent}%</b> — {round.skill_result === 'pass' ? 'Đạt' : 'Không đạt'}</div>
          )}
          {f.canEvaluate && round.status === 'training' && (round.criteria?.length > 0) && (
            <div className="card" style={{ padding: 10 }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Chấm đánh giá vòng</div>
              <RoundEvalForm
                criteria={round.criteria}
                defaultType={evalType}
                allowTypeChoice={f.isTraining}
                onDone={submitEval}
              />
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

function Cond({ ok, label }) {
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '2px 0' }}>
      <span style={{ color: ok ? 'var(--forest)' : 'var(--danger)' }}>{ok ? '✓' : '✗'}</span>
      <span style={{ fontSize: 14 }}>{label}</span>
    </div>
  )
}

// ---- Modal đăng ký thăng tiến ----
function RegisterModal({ batches, presetEmployee, onClose, onDone }) {
  const [term, setTerm] = useState('')
  const [results, setResults] = useState([])
  const [picked, setPicked] = useState(null)
  const [options, setOptions] = useState(null)
  const [targetPos, setTargetPos] = useState('')
  const [batch, setBatch] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (presetEmployee) pick(presetEmployee)
    // eslint-disable-next-line
  }, [])

  async function search() {
    const { data } = await api.get('/employees/', { params: { search: term, page_size: 8 } })
    setResults(data.results || [])
  }
  async function pick(emp) {
    setPicked(emp)
    setResults([])
    setTerm(`${emp.name} - ${emp.code}`)
    setOptions(null)
    setMsg('')
    const { data } = await api.get(`/employees/${emp.id}/levelup-options/`)
    setOptions(data)
    setTargetPos('')
  }
  async function register() {
    setBusy(true)
    setMsg('')
    try {
      await api.post(`/employees/${picked.id}/levelup-register/`, { target_position: targetPos, exam_batch: batch })
      onDone()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Không đăng ký được.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open title="Đăng ký thăng tiến" onClose={onClose}
      footer={
        <>
          <button className="btn-outline" onClick={onClose}>Hủy</button>
          <button disabled={busy || !options?.can || !targetPos || !batch} onClick={register}>Đăng ký</button>
        </>
      }
    >
      <div style={{ display: 'grid', gap: 10 }}>
        <label>
          Nhân sự
          <div style={{ display: 'flex', gap: 6 }}>
            <input style={{ flex: 1 }} value={term} placeholder="Tìm mã / tên..." onChange={(e) => { setTerm(e.target.value); setPicked(null) }} />
            <button className="btn-outline" onClick={search}>Tìm</button>
          </div>
        </label>
        {results.length > 0 && (
          <div className="card" style={{ padding: 6, maxHeight: 160, overflow: 'auto' }}>
            {results.map((e) => (
              <div key={e.id} style={{ padding: '4px 6px', cursor: 'pointer' }} onClick={() => pick(e)}>
                {e.name} - {e.code} <span className="muted-note">({e.position || '—'})</span>
              </div>
            ))}
          </div>
        )}

        {options && (
          <div className="card" style={{ padding: 10 }}>
            <div className="muted-note">
              Khối <b>{options.zone}</b> · Level {options.current_level || '?'} → {options.next_level || '(tối đa)'} ·{' '}
              Đã đạt {options.positions_achieved_count} vị trí
            </div>
            {!options.can ? (
              <p style={{ color: 'var(--danger)', marginTop: 6 }}>Không thể đăng ký: {options.reason}</p>
            ) : (
              <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>
                <label>
                  Vị trí đích
                  <select style={{ display: 'block', width: '100%' }} value={targetPos} onChange={(e) => setTargetPos(e.target.value)}>
                    <option value="">— Chọn vị trí —</option>
                    {options.options.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </label>
                <label>
                  Đợt thi
                  <select style={{ display: 'block', width: '100%' }} value={batch} onChange={(e) => setBatch(e.target.value)}>
                    <option value="">— Chọn đợt —</option>
                    {batches.map((b) => <option key={b.code} value={b.code}>{b.label} (hạn ĐK {b.register_deadline})</option>)}
                  </select>
                </label>
              </div>
            )}
          </div>
        )}
        {msg && <p style={{ color: 'var(--danger)' }}>{msg}</p>}
      </div>
    </Modal>
  )
}

// ---- #8: Danh sách theo dõi & đào tạo lộ trình (cấp S, CRUD) ----
const PROG_PAGE_SIZE = 20
function ProgressionList({ onRegister }) {
  const { user } = useAuth()
  const isAdmin = ['admin', 'om'].includes((user?.role || '').toLowerCase())
  const [search, setSearch] = useState('')
  const [restaurant, setRestaurant] = useState('')
  const [status, setStatus] = useState('')
  const [staffKind, setStaffKind] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [form, setForm] = useState(null)
  const [positions, setPositions] = useState([])

  useEffect(() => { api.get('/employees/positions/').then(({ data }) => setPositions(data)).catch(() => {}) }, [])
  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })

  const params = {
    level_group: 'S', search, restaurant: restaurant || undefined,
    employee_status: status || undefined,
    is_legacy: staffKind === 'new' ? false : staffKind === 'legacy' ? true : undefined,
    page, page_size: PROG_PAGE_SIZE, refreshKey,
  }
  const { data, loading, error } = usePaginatedList('/employees/', params)

  function onFilter(setter) { return (e) => { setter(e.target.value); setPage(1) } }
  async function save() {
    try {
      await api.patch(`/employees/${form.id}/`, { position: form.position, job_level: form.job_level, restaurant: form.restaurant || null })
      setForm(null); setRefreshKey((k) => k + 1)
    } catch (e) { alert(e.response?.data?.detail || 'Không lưu được.') }
  }
  async function del(e) {
    if (!window.confirm(`Xóa nhân sự "${e.name}"? Không hoàn tác.`)) return
    try { await api.delete(`/employees/${e.id}/`); setRefreshKey((k) => k + 1) }
    catch (err) { alert(err.response?.data?.detail || 'Không xóa được.') }
  }
  async function changeStatus(e, st) {
    try { await api.post(`/employees/${e.id}/change-status/`, { employee_status: st }); setRefreshKey((k) => k + 1) }
    catch (err) { alert(err.response?.data?.detail || 'Không đổi được trạng thái.') }
  }

  return (
    <>
      <p className="muted-note">Nhân sự cấp S theo lộ trình (nhân sự mới đã pass + nhân sự cũ). Sửa vị trí/level, đổi trạng thái, đăng ký thăng tiến.</p>
      <FilterBar>
        <input style={s.input} placeholder="Tìm mã / tên..." value={search} onChange={onFilter(setSearch)} />
        <select style={s.select} value={restaurant} onChange={onFilter(setRestaurant)}>
          <option value="">Tất cả nhà hàng</option>
          {restaurantOptions.results.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <select style={s.select} value={status} onChange={onFilter(setStatus)}>
          <option value="">Tất cả trạng thái</option>
          {Object.entries(EMP_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select style={s.select} value={staffKind} onChange={onFilter(setStaffKind)}>
          <option value="">Mới + Cũ</option>
          <option value="new">Chỉ nhân sự mới</option>
          <option value="legacy">Chỉ nhân sự cũ</option>
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!loading && !error && (
        <>
          <div className="table-sticky">
            <Table>
              <thead>
                <tr><th>Nhân sự</th><th>Nhà hàng</th><th>Vị trí</th><th>Level</th><th>Trạng thái</th><th></th></tr>
              </thead>
              <tbody>
                {data.results.map((e) => (
                  <tr key={e.id}>
                    <td>{e.name} - {e.code}{e.is_legacy ? <span className="muted-note" style={{ fontSize: 11 }}> (cũ)</span> : ''}</td>
                    <td>{e.restaurant_name}</td>
                    <td>{e.position}</td>
                    <td>{e.job_level}</td>
                    <td>
                      {isAdmin ? (
                        <select value={e.employee_status} onChange={(ev) => changeStatus(e, ev.target.value)}>
                          {Object.entries(EMP_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                        </select>
                      ) : (EMP_STATUS[e.employee_status] || e.employee_status)}
                    </td>
                    <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <button className="btn-sm" onClick={() => onRegister({ id: e.id, name: e.name, code: e.code })}>Đăng ký</button>
                      {isAdmin && <button className="btn-outline btn-sm" onClick={() => setForm({ id: e.id, position: e.position, job_level: e.job_level, restaurant: e.restaurant || '' })}>Sửa</button>}
                      {isAdmin && <button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => del(e)}>Xóa</button>}
                    </td>
                  </tr>
                ))}
                {data.results.length === 0 && <tr><td colSpan={6} className="muted-note">Không có nhân sự cấp S phù hợp.</td></tr>}
              </tbody>
            </Table>
          </div>
          <Pager page={page} pageSize={PROG_PAGE_SIZE} count={data.count} onChange={setPage} />
        </>
      )}

      {form && (
        <Modal open title="Sửa nhân sự (lộ trình)" onClose={() => setForm(null)}
          footer={<><button className="btn-outline" onClick={() => setForm(null)}>Hủy</button><button onClick={save}>Lưu</button></>}>
          <div style={{ display: 'grid', gap: 10 }}>
            <label>Vị trí
              <input list="prog-pos-list" style={{ display: 'block', width: '100%' }} value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} />
              <datalist id="prog-pos-list">{positions.map((p) => <option key={p} value={p} />)}</datalist>
            </label>
            <label>Level (vd S1.2, S2.1)
              <input style={{ display: 'block', width: '100%' }} value={form.job_level} onChange={(e) => setForm({ ...form, job_level: e.target.value })} />
            </label>
            <label>Nhà hàng
              <select style={{ display: 'block', width: '100%' }} value={form.restaurant} onChange={(e) => setForm({ ...form, restaurant: e.target.value })}>
                <option value="">—</option>
                {restaurantOptions.results.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </label>
          </div>
        </Modal>
      )}
    </>
  )
}

export default function LevelUpPage() {
  const { user } = useAuth()
  const f = roleFlags(user?.role)

  const [tab, setTab] = useState('enrollments')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusF, setStatusF] = useState('')
  const [batchF, setBatchF] = useState('')
  const [batches, setBatches] = useState([])
  const [showRegister, setShowRegister] = useState(false)
  const [presetEmp, setPresetEmp] = useState(null)
  const [roundId, setRoundId] = useState(null)
  const [talent, setTalent] = useState([])
  const [reviewEmp, setReviewEmp] = useState(null)
  const [councilEmp, setCouncilEmp] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const { data } = await api.get('/employees/levelup-enrollments/', {
        params: { status: statusF || undefined, exam_batch: batchF || undefined },
      })
      setRows(data)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() /* eslint-disable-next-line */ }, [statusF, batchF])
  useEffect(() => {
    api.get('/employees/exam-batches/').then(({ data }) => setBatches(data)).catch(() => {})
  }, [])
  function loadTalent() {
    api.get('/employees/talent-candidates/').then(({ data }) => setTalent(data)).catch(() => {})
  }
  useEffect(() => {
    if (tab === 'talent' && f.canReview) loadTalent()
  }, [tab, f.canReview])

  async function openTraining(id) {
    try {
      await api.post(`/employees/levelup-enrollments/${id}/open-training/`)
      load()
    } catch (e) {
      alert(e.response?.data?.detail || 'Không mở được đào tạo.')
    }
  }
  async function markFail(id) {
    if (!window.confirm('Đánh dấu vòng này KHÔNG ĐẠT?')) return
    try {
      await api.post(`/employees/levelup-enrollments/${id}/fail/`)
      load()
    } catch (e) {
      alert(e.response?.data?.detail || 'Không cập nhật được.')
    }
  }

  const batchFilterOptions = useMemo(() => {
    const set = new Map()
    batches.forEach((b) => set.set(b.code, b.label))
    rows.forEach((r) => { if (r.exam_batch && !set.has(r.exam_batch)) set.set(r.exam_batch, r.exam_batch) })
    return [...set.entries()]
  }, [batches, rows])

  return (
    <AppShell>
      <BackButton />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Lộ trình thăng tiến</h2>
        {f.canRegister && <button onClick={() => setShowRegister(true)}>+ Đăng ký thăng tiến</button>}
      </div>

      <div style={{ display: 'flex', gap: 8, margin: '10px 0' }}>
        <button className={`btn-sm ${tab === 'eligible' ? '' : 'btn-outline'}`} onClick={() => setTab('eligible')}>Theo dõi & đào tạo</button>
        <button className={`btn-sm ${tab === 'enrollments' ? '' : 'btn-outline'}`} onClick={() => setTab('enrollments')}>Đợt thăng tiến</button>
        {f.canReview && <button className={`btn-sm ${tab === 'talent' ? '' : 'btn-outline'}`} onClick={() => setTab('talent')}>Nhân sự nguồn</button>}
      </div>

      {tab === 'eligible' && (
        <ProgressionList onRegister={(emp) => { setPresetEmp(emp); setShowRegister(true) }} />
      )}

      {tab === 'enrollments' && (
        <>
          <FilterBar>
            <select style={s.select} value={statusF} onChange={(e) => setStatusF(e.target.value)}>
              <option value="">Tất cả trạng thái</option>
              {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <select style={s.select} value={batchF} onChange={(e) => setBatchF(e.target.value)}>
              <option value="">Tất cả đợt thi</option>
              {batchFilterOptions.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
            </select>
          </FilterBar>

          {loading ? <p className="muted-note">Đang tải...</p> : (
            <div className="table-sticky"><Table>
              <thead>
                <tr>
                  <th>Nhân sự</th><th>Nhà hàng</th><th>Vị trí đích</th><th>Level</th>
                  <th>Đợt thi</th><th>Trạng thái</th><th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.employee_name} - {r.employee_code}</td>
                    <td>{r.restaurant_name}</td>
                    <td>{r.target_position}</td>
                    <td>{r.from_level} → {r.target_level}</td>
                    <td>{r.exam_batch}</td>
                    <td><Badge variant={STATUS_VARIANTS[r.status]}>{STATUS_LABELS[r.status]}</Badge></td>
                    <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <button className="btn-outline btn-sm" onClick={() => setRoundId(r.id)}>Vòng</button>
                      {f.canOpen && r.status === 'registered' && (
                        <button className="btn-sm" onClick={() => openTraining(r.id)}>Mở đào tạo</button>
                      )}
                      {f.canDecide && r.status === 'training' && (
                        <button className="btn-outline btn-sm" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} onClick={() => markFail(r.id)}>Không đạt</button>
                      )}
                      {r.proposal_pdf_url && (
                        <a className="btn-outline btn-sm" href={r.proposal_pdf_url} target="_blank" rel="noreferrer">📄 Phiếu đề xuất</a>
                      )}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && <tr><td colSpan={7} className="muted-note">Chưa có đợt thăng tiến nào.</td></tr>}
              </tbody>
            </Table></div>
          )}
        </>
      )}

      {tab === 'talent' && f.canReview && (
        <>
          <p className="muted-note">Nhân sự đủ 3 vị trí → AM/KCS phỏng vấn đánh giá sẵn sàng. Duyệt = chính thức vào nhân sự nguồn; sau đó Phòng Đào tạo lập hội đồng đánh giá phát triển lên BQL.</p>
          <div className="table-sticky"><Table>
            <thead>
              <tr><th>Nhân sự</th><th>Nhà hàng</th><th>Level</th><th>Vị trí đã đạt</th><th>Duyệt sẵn sàng</th><th></th></tr>
            </thead>
            <tbody>
              {talent.map((e) => (
                <tr key={e.id}>
                  <td>{e.name} - {e.code}</td>
                  <td>{e.restaurant_name}</td>
                  <td><Badge variant="success">{e.level}</Badge></td>
                  <td>{(e.achieved_positions || []).join(', ')}</td>
                  <td>
                    {e.decision === 'approved' ? <Badge variant="success">Đã vào nguồn</Badge>
                      : e.decision === 'rejected' ? <Badge variant="danger">Chưa sẵn sàng</Badge>
                      : <Badge variant="warning">Chờ đánh giá</Badge>}
                    {e.reviewed_by && <div className="muted-note" style={{ fontSize: 11 }}>{e.reviewed_by}</div>}
                  </td>
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button className="btn-outline btn-sm" onClick={() => setReviewEmp(e)}>Đánh giá sẵn sàng</button>
                    {f.canDecide && e.decision === 'approved' && (
                      <button className="btn-outline btn-sm" onClick={() => setCouncilEmp(e)}>Lập hội đồng</button>
                    )}
                  </td>
                </tr>
              ))}
              {talent.length === 0 && <tr><td colSpan={6} className="muted-note">Chưa có ứng viên đủ 3 vị trí.</td></tr>}
            </tbody>
          </Table></div>
        </>
      )}

      {showRegister && (
        <RegisterModal
          batches={batches}
          presetEmployee={presetEmp}
          onClose={() => { setShowRegister(false); setPresetEmp(null) }}
          onDone={() => { setShowRegister(false); setPresetEmp(null); load() }}
        />
      )}
      {roundId && <RoundModal enrollmentId={roundId} onClose={() => setRoundId(null)} onChanged={load} />}
      {reviewEmp && <TalentReviewModal emp={reviewEmp} onClose={() => setReviewEmp(null)} onDone={() => { setReviewEmp(null); loadTalent() }} />}
      {councilEmp && (
        <Modal open title={`Hội đồng đánh giá — ${councilEmp.name}`} onClose={() => setCouncilEmp(null)} footer={<button className="btn-outline" onClick={() => setCouncilEmp(null)}>Đóng</button>}>
          <CouncilPanel employee={{ id: councilEmp.id, name: councilEmp.name, position: councilEmp.position, restaurant: councilEmp.restaurant_name }} />
        </Modal>
      )}
    </AppShell>
  )
}

function TalentReviewModal({ emp, onClose, onDone }) {
  const [note, setNote] = useState(emp.note || '')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  async function submit(decision) {
    setBusy(true); setMsg('')
    try {
      await api.post(`/employees/${emp.id}/talent-review/`, { decision, note })
      onDone()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Không lưu được.')
    } finally { setBusy(false) }
  }
  return (
    <Modal open title={`Đánh giá sẵn sàng — ${emp.name}`} onClose={onClose}
      footer={
        <>
          <button className="btn-outline" style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }} disabled={busy} onClick={() => submit('rejected')}>Chưa sẵn sàng</button>
          <button disabled={busy} onClick={() => submit('approved')}>Duyệt vào nguồn</button>
        </>
      }>
      <p className="muted-note">AM/KCS phỏng vấn đánh giá: sẵn sàng phát triển lên, mức độ gắn bó lâu dài, phù hợp văn hóa công ty.</p>
      <label>Ghi chú đánh giá
        <textarea style={{ display: 'block', width: '100%' }} rows={4} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {msg && <p style={{ color: 'var(--danger)' }}>{msg}</p>}
    </Modal>
  )
}
