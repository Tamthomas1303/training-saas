// Port EmployeeService.gs::canTrainPosition (client-side mirror cua backend
// employees/permissions.py::can_train_position) - dung de an/hien nut "Đào tạo".
function normalizeKey(value) {
  return (value || '').trim().toLowerCase()
}

export function canTrainPosition(role, jobPosition) {
  const r = (role || '').toLowerCase()
  const p = normalizeKey(jobPosition)
  const isQl = p.includes('quan ly') || p.includes('quản lý')
  const isBt = p.includes('bep truong') || p.includes('bếp trưởng')
  const isGs = p.includes('giam sat') || p.includes('giám sát')
  const isBp = p.includes('bep pho') || p.includes('bếp phó')

  if (r === 'admin') return true
  if (r === 'am') return isQl
  if (r === 'kcs') return isBt
  if (r === 'bql') return !(isQl || isBt)
  if (r === 'trainer') return !(isQl || isBt || isGs || isBp)
  return false
}
