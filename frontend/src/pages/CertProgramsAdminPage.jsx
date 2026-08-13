import { useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const TYPES = [
  { value: 'chuyen_mon', label: 'Đào tạo kỹ năng nghề' },
  { value: 'bql', label: 'Ban quản lý' },
]

const RULE_KINDS = [
  { value: 'positions_count', label: 'Đủ N vị trí (thăng tiến)' },
  { value: 'course_exam', label: 'Hoàn thành 1 khóa + 1 bài thi (vd Train the trainer)' },
  { value: 'bql_position', label: 'Theo vị trí BQL (đào tạo + thi cuối)' },
]

function defaultRuleConfig(kind) {
  if (kind === 'positions_count') return { kind, count: 3 }
  if (kind === 'course_exam') return { kind, course: '', exam: '' }
  if (kind === 'bql_position') return { kind, require: ['training', 'final_exam', 'council', 'shift_eval', 'interview'] }
  return { kind }
}

function RuleConfigEditor({ rule, onChange }) {
  const kind = rule.kind || 'positions_count'

  function setKind(nextKind) {
    onChange(defaultRuleConfig(nextKind))
  }

  return (
    <div style={{ marginBottom: 8 }}>
      <select value={kind} onChange={(e) => setKind(e.target.value)} style={{ ...s.select, width: '100%', marginBottom: 8 }}>
        {RULE_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
      </select>

      {kind === 'positions_count' && (
        <input
          type="number" value={rule.count ?? 3}
          onChange={(e) => onChange({ ...rule, count: Number(e.target.value) })}
          placeholder="Số vị trí cần đạt" style={{ ...s.input, width: 160 }}
        />
      )}

      {kind === 'course_exam' && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            value={rule.course || ''} onChange={(e) => onChange({ ...rule, course: e.target.value })}
            placeholder="Mã đồng bộ khóa (sync_course_code)" style={{ ...s.input, flex: 1, minWidth: 200 }}
          />
          <input
            value={rule.exam || ''} onChange={(e) => onChange({ ...rule, exam: e.target.value })}
            placeholder="Mã đồng bộ bài thi (sync_exam_type)" style={{ ...s.input, flex: 1, minWidth: 200 }}
          />
        </div>
      )}

      {kind === 'bql_position' && (
        <div>
          <p className="muted-note" style={{ marginBottom: 4 }}>
            MVP chỉ kiểm được "Đào tạo tại điểm 100%" và "Thi cuối đạt" (đọc theo ExamResult chung, không lọc
            theo kỳ thi cụ thể). Hội đồng tay nghề / đánh giá ca / phỏng vấn để cờ chờ tích hợp module Đánh giá
            (P2) — không chặn cấp chứng chỉ MVP.
          </p>
          {['training', 'final_exam', 'council', 'shift_eval', 'interview'].map((key) => (
            <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
              <input
                type="checkbox" checked={(rule.require || []).includes(key)}
                onChange={(e) => {
                  const require = rule.require || []
                  onChange({
                    ...rule,
                    require: e.target.checked ? [...require, key] : require.filter((r) => r !== key),
                  })
                }}
              />
              {{
                training: 'Đào tạo tại điểm 100%', final_exam: 'Thi cuối đạt',
                council: 'Hội đồng tay nghề (chờ tích hợp P2)', shift_eval: 'Đánh giá vận hành ca (chờ tích hợp P2)',
                interview: 'Phỏng vấn (chờ tích hợp P2)',
              }[key]}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

function ProgramForm({ program, templates, onSaved, onCancel }) {
  const [name, setName] = useState(program?.name || '')
  const [type, setType] = useState(program?.type || 'chuyen_mon')
  const [rule, setRule] = useState(program?.rule_config?.kind ? program.rule_config : defaultRuleConfig('positions_count'))
  const [templateId, setTemplateId] = useState(program?.certificate_template || '')
  const [active, setActive] = useState(program?.active ?? true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function save() {
    if (!name.trim()) {
      setError('Nhập tên chương trình.')
      return
    }
    if (!templateId) {
      setError('Chọn mẫu chứng chỉ.')
      return
    }
    setSaving(true)
    setError('')
    const payload = { name: name.trim(), type, rule_config: rule, certificate_template: templateId, active }
    try {
      if (program) {
        await api.patch(`/integration/programs/${program.id}/`, payload)
      } else {
        await api.post('/integration/programs/', payload)
      }
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không lưu được chương trình.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <input
        value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên chương trình..."
        style={{ ...s.input, width: '100%', marginBottom: 8 }}
      />
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <select value={type} onChange={(e) => setType(e.target.value)} style={s.select}>
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} style={s.select}>
          <option value="">— Chọn mẫu chứng chỉ —</option>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Đang dùng
        </label>
      </div>

      <RuleConfigEditor rule={rule} onChange={setRule} />

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={save} disabled={saving}>Lưu</button>
        <button className="btn-outline" onClick={onCancel}>Hủy</button>
      </div>
    </div>
  )
}

export default function CertProgramsAdminPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const { data, loading } = usePaginatedList('/integration/programs/', { page_size: 50, refreshKey })
  const { data: templates } = usePaginatedList('/integration/templates/', { page_size: 100, active: true })

  function reload() {
    setCreating(false)
    setEditingId(null)
    setRefreshKey((k) => k + 1)
  }

  return (
    <AppShell>
      <h2>Chương trình chứng chỉ</h2>
      <p className="muted-note">
        Chứng chỉ được cấp tự động khi nhân sự đủ điều kiện (kiểm tra lại mỗi khi hoàn thành khóa/thi/xác
        nhận offline).
      </p>

      {!creating && !editingId && (
        <button onClick={() => setCreating(true)} style={{ marginBottom: 16 }}>+ Tạo chương trình</button>
      )}
      {creating && <ProgramForm templates={templates.results} onSaved={reload} onCancel={() => setCreating(false)} />}

      {loading && <p className="muted-note">Đang tải...</p>}
      <Table>
        <thead>
          <tr><th>Tên</th><th>Loại</th><th>Mẫu chứng chỉ</th><th>Trạng thái</th><th></th></tr>
        </thead>
        <tbody>
          {data.results.map((p) => (
            <tr key={p.id}>
              <td>{p.name}</td>
              <td>{p.type_display}</td>
              <td>{p.certificate_template_name || <span className="muted-note">(chưa chọn)</span>}</td>
              <td><Badge variant={p.active ? 'success' : 'neutral'}>{p.active ? 'Đang dùng' : 'Ngừng'}</Badge></td>
              <td><button className="btn-outline btn-sm" onClick={() => setEditingId(p.id)}>Sửa</button></td>
            </tr>
          ))}
          {data.results.length === 0 && !loading && (
            <tr><td colSpan={5} className="muted-note">Chưa có chương trình nào.</td></tr>
          )}
        </tbody>
      </Table>
      {editingId && (
        <ProgramForm
          program={data.results.find((p) => p.id === editingId)} templates={templates.results}
          onSaved={reload} onCancel={() => setEditingId(null)}
        />
      )}
    </AppShell>
  )
}
