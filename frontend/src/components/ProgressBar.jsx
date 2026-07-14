export default function ProgressBar({ percent, color }) {
  const clamped = Math.min(100, Math.max(0, percent || 0))
  return (
    <div className="bar-track">
      <div className="bar-fill" style={{ width: `${clamped}%`, background: color }} />
    </div>
  )
}
