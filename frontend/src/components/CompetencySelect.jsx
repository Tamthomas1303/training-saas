import * as s from '../pages/listPageStyles'

// Dropdown chon 1 Nang luc (dashboard.Competency) - dung chung o form Khoa hoc/Đề thi/Tiêu chí
// đánh giá/Checklist. value=null hoặc '' -> "Chưa gán".
export default function CompetencySelect({ value, onChange, options, disabled, style }) {
  return (
    <select
      value={value || ''}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      style={{ ...s.select, ...style }}
      disabled={disabled}
    >
      <option value="">— Chưa gán năng lực —</option>
      {options.map((c) => (
        <option key={c.id} value={c.id}>{c.group_code} · {c.name}</option>
      ))}
    </select>
  )
}
