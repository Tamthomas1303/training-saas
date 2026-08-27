import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import AppShell from '../components/AppShell'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

// Nhom 3A (Prompt_Nhom3A_Onboarding_TuDong.md muc 4) - man "Tu dong hoa" (admin, desktop):
// 3 cong tac onboarding tu dong + anh xa vi tri -> khoa hoi nhap + mau email tiep nhan. Huong
// "luong co san" (recipe) - bat/tat + dat tham so, KHONG dung builder tu do.
function CcListInput({ label, value, onChange }) {
  const text = (value || []).join(', ')
  return (
    <label>
      {label}
      <input
        style={{ ...s.input, width: '100%' }} defaultValue={text}
        placeholder="email1@x.com, email2@x.com"
        onBlur={(e) => onChange(e.target.value.split(',').map((v) => v.trim()).filter(Boolean))}
      />
    </label>
  )
}

function SettingsCard() {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/employees/automation-settings/').then(({ data }) => setForm(data)).catch(() => setMsg('Không tải được cấu hình.'))
  }, [])

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function save() {
    setSaving(true)
    setMsg('')
    try {
      const { data } = await api.put('/employees/automation-settings/', form)
      setForm(data)
      setMsg('Đã lưu.')
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Lưu thất bại.')
    } finally {
      setSaving(false)
    }
  }

  if (!form) return <p className="muted-note">{msg || 'Đang tải...'}</p>

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>Công tắc onboarding tự động</h3>
      <p className="muted-note">
        Áp dụng khi import nhân sự MỚI (chưa từng có tài khoản). Thông tin đăng nhập SMTP được
        cấu hình ở biến môi trường, không nhập tại đây.
      </p>
      <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={!!form.auto_create_account} onChange={(e) => set('auto_create_account', e.target.checked)} />
          Tạo tài khoản khi import
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={!!form.auto_enroll_onboarding} onChange={(e) => set('auto_enroll_onboarding', e.target.checked)} />
          Auto-enroll khóa hội nhập
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={!!form.send_welcome_email} onChange={(e) => set('send_welcome_email', e.target.checked)} />
          Gửi email tiếp nhận
        </label>
      </div>

      <h3>Công tắc thi kết thúc thử việc (Nhóm 3B)</h3>
      <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={!!form.auto_assign_probation_exam} onChange={(e) => set('auto_assign_probation_exam', e.target.checked)} />
          Tự gán kỳ thi kết thúc thử việc khi đủ điều kiện (LMS + checklist 100%)
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={!!form.require_approval_before_exam} onChange={(e) => set('require_approval_before_exam', e.target.checked)} />
          Chờ duyệt trước khi cho thi (khuyến nghị bật - tắt sẽ tự cho thi ngay không qua duyệt)
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={!!form.auto_send_probation_result} onChange={(e) => set('auto_send_probation_result', e.target.checked)} />
          Tự gửi kết quả thử việc về nhà hàng khi có kết quả
        </label>
        <label>
          Mốc lương chính thức tính theo
          <select
            style={{ ...s.select, marginLeft: 8 }} value={form.salary_effective_rule || 'pass_date'}
            onChange={(e) => set('salary_effective_rule', e.target.value)}
          >
            <option value="pass_date">Ngày Pass thử việc</option>
            <option value="next_month_first">Ngày 1 tháng kế tiếp</option>
          </select>
        </label>
      </div>

      <h4>Mẫu email kết quả thử việc</h4>
      <p className="muted-note" style={{ marginTop: 0 }}>
        Biến chèn được: {'{ten_nhan_su} {ma_nhan_su} {nha_hang} {vi_tri} {ket_qua} {ngay_pass} {ngay_luong_chinh_thuc} {ten_he_thong}'}
      </p>
      <div style={{ display: 'grid', gap: 12, maxWidth: 560, marginBottom: 16 }}>
        <label>
          Tiêu đề
          <input style={{ ...s.input, width: '100%' }} value={form.result_email_subject || ''} onChange={(e) => set('result_email_subject', e.target.value)} />
        </label>
        <label>
          Nội dung
          <textarea
            style={{ ...s.input, width: '100%', minHeight: 140, fontFamily: 'inherit' }}
            value={form.result_email_body || ''}
            onChange={(e) => set('result_email_body', e.target.value)}
          />
        </label>
      </div>

      <h4>Mẫu email tiếp nhận</h4>
      <p className="muted-note" style={{ marginTop: 0 }}>
        Biến chèn được: {'{ten_nhan_su} {ma_nhan_su} {nha_hang} {vi_tri} {link_dat_mat_khau} {ten_dang_nhap} {ten_he_thong}'}
      </p>
      <div style={{ display: 'grid', gap: 12, maxWidth: 560 }}>
        <label>
          Tên người gửi hiển thị
          <input style={{ ...s.input, width: '100%' }} value={form.sender_display_name || ''} onChange={(e) => set('sender_display_name', e.target.value)} />
        </label>
        <label>
          Tiêu đề
          <input style={{ ...s.input, width: '100%' }} value={form.welcome_email_subject || ''} onChange={(e) => set('welcome_email_subject', e.target.value)} />
        </label>
        <label>
          Nội dung
          <textarea
            style={{ ...s.input, width: '100%', minHeight: 160, fontFamily: 'inherit' }}
            value={form.welcome_email_body || ''}
            onChange={(e) => set('welcome_email_body', e.target.value)}
          />
        </label>
        <p className="muted-note" style={{ margin: 0 }}>
          Người nhận chính = email của nhà hàng (QLNH phụ trách) của nhân sự. CC thêm bên dưới (vd phòng Đào tạo).
        </p>
        <CcListInput label="CC" value={form.cc_recipients} onChange={(v) => set('cc_recipients', v)} />

        <div>
          <button onClick={save} disabled={saving}>Lưu</button>
          {msg && <span className="muted-note" style={{ marginLeft: 8 }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

function CourseRulesCard() {
  const [rules, setRules] = useState([])
  const [positions, setPositions] = useState([])
  const [courses, setCourses] = useState([])
  const [position, setPosition] = useState('')
  const [courseId, setCourseId] = useState('')
  const [msg, setMsg] = useState('')

  function load() {
    api.get('/employees/onboarding-course-rules/', { params: { page_size: 200 } })
      .then(({ data }) => setRules(data.results ?? data))
      .catch(() => setMsg('Không tải được danh sách ánh xạ.'))
  }

  useEffect(() => {
    load()
    api.get('/employees/positions/').then(({ data }) => setPositions(data)).catch(() => {})
    api.get('/courses/', { params: { status: 'published', page_size: 200 } })
      .then(({ data }) => setCourses(data.results ?? data))
      .catch(() => {})
  }, [])

  async function addRule() {
    if (!position || !courseId) return
    setMsg('')
    try {
      await api.post('/employees/onboarding-course-rules/', { position, course: courseId })
      setPosition('')
      setCourseId('')
      load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Thêm ánh xạ thất bại (có thể đã tồn tại).')
    }
  }

  async function removeRule(id) {
    await api.delete(`/employees/onboarding-course-rules/${id}/`)
    load()
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>Ánh xạ vị trí → khóa hội nhập</h3>
      <p className="muted-note">Khi auto-enroll bật, nhân sự mới sẽ được ghi danh vào (các) khóa khớp đúng vị trí vào làm.</p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <select style={s.select} value={position} onChange={(e) => setPosition(e.target.value)}>
          <option value="">-- Chọn vị trí --</option>
          {positions.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select style={s.select} value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">-- Chọn khóa hội nhập --</option>
          {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
        <button onClick={addRule} disabled={!position || !courseId}>Thêm</button>
      </div>
      {msg && <p className="muted-note">{msg}</p>}

      <Table>
        <thead>
          <tr><th>Vị trí</th><th>Khóa hội nhập</th><th></th></tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>{r.position}</td>
              <td>{r.course_title}</td>
              <td>
                <button className="btn-outline btn-sm" onClick={() => removeRule(r.id)} title="Xóa">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
          {rules.length === 0 && (
            <tr><td colSpan={3} className="muted-note">Chưa có ánh xạ nào.</td></tr>
          )}
        </tbody>
      </Table>
    </div>
  )
}

function ProbationExamRulesCard() {
  const [rules, setRules] = useState([])
  const [positions, setPositions] = useState([])
  const [assessments, setAssessments] = useState([])
  const [position, setPosition] = useState('')
  const [assessmentId, setAssessmentId] = useState('')
  const [msg, setMsg] = useState('')

  function load() {
    api.get('/employees/probation-exam-rules/', { params: { page_size: 200 } })
      .then(({ data }) => setRules(data.results ?? data))
      .catch(() => setMsg('Không tải được danh sách ánh xạ.'))
  }

  useEffect(() => {
    load()
    api.get('/employees/positions/').then(({ data }) => setPositions(data)).catch(() => {})
    api.get('/exams/assessments/', { params: { status: 'published', page_size: 200 } })
      .then(({ data }) => setAssessments(data.results ?? data))
      .catch(() => {})
  }, [])

  async function addRule() {
    if (!position || !assessmentId) return
    setMsg('')
    try {
      await api.post('/employees/probation-exam-rules/', { position, assessment: assessmentId })
      setPosition('')
      setAssessmentId('')
      load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Thêm ánh xạ thất bại (mỗi vị trí chỉ có 1 đề).')
    }
  }

  async function removeRule(id) {
    await api.delete(`/employees/probation-exam-rules/${id}/`)
    load()
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>Ánh xạ vị trí → đề thi kết thúc thử việc</h3>
      <p className="muted-note">Mỗi vị trí ánh xạ với đúng 1 đề thi kết thúc thử việc.</p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <select style={s.select} value={position} onChange={(e) => setPosition(e.target.value)}>
          <option value="">-- Chọn vị trí --</option>
          {positions.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select style={s.select} value={assessmentId} onChange={(e) => setAssessmentId(e.target.value)}>
          <option value="">-- Chọn đề thi --</option>
          {assessments.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
        </select>
        <button onClick={addRule} disabled={!position || !assessmentId}>Thêm</button>
      </div>
      {msg && <p className="muted-note">{msg}</p>}

      <Table>
        <thead>
          <tr><th>Vị trí</th><th>Đề thi</th><th></th></tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>{r.position}</td>
              <td>{r.assessment_title}</td>
              <td>
                <button className="btn-outline btn-sm" onClick={() => removeRule(r.id)} title="Xóa">
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
          {rules.length === 0 && (
            <tr><td colSpan={3} className="muted-note">Chưa có ánh xạ nào.</td></tr>
          )}
        </tbody>
      </Table>
    </div>
  )
}

export default function AutomationPage() {
  return (
    <AppShell>
      <h2>Tự động hóa</h2>
      <SettingsCard />
      <CourseRulesCard />
      <ProbationExamRulesCard />
    </AppShell>
  )
}
