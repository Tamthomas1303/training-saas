import { useEffect, useRef } from 'react'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler } from 'chart.js'
import { hexToRgba } from '../utils/color'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler)

function resolveColor(color) {
  const match = /^var\((--[a-z-]+)\)$/i.exec((color || '').trim())
  if (!match) return color
  return getComputedStyle(document.documentElement).getPropertyValue(match[1]).trim()
}

// Sparkline gon tich hop trong StatCard (UI dot 2, Prompt_UI_Dot2_ConsoleAdmin.md muc C): khong
// truc/luoi, khong diem (pointRadius:0), duong cong nhe (tension:0.4), to dai chuyen mau (gradient
// area) tu mau chinh nhat dan ve trong suot. `color` nhan hex thuong ('#1e6f5c') hoac bien CSS
// ('var(--brand)') - resolve runtime de luon dung mau brand/hien tai.
export default function Sparkline({ data, color = 'var(--brand)', height = 42 }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current || !data || data.length < 2) return undefined
    const resolved = resolveColor(color) || '#1e6f5c'
    const ctx = canvasRef.current.getContext('2d')
    const gradient = ctx.createLinearGradient(0, 0, 0, height)
    gradient.addColorStop(0, hexToRgba(resolved, 0.32))
    gradient.addColorStop(1, hexToRgba(resolved, 0))

    chartRef.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.map((_, i) => i),
        datasets: [{
          data,
          borderColor: resolved,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          borderWidth: 2,
          pointRadius: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: { x: { display: false }, y: { display: false } },
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
    })
    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(data), color, height])

  if (!data || data.length < 2) return null
  return (
    <div style={{ height, width: '100%' }}>
      <canvas ref={canvasRef} />
    </div>
  )
}
