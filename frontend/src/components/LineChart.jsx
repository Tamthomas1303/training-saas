import { useEffect, useRef } from 'react'
import {
  Chart, LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip,
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip)

// UI dot 1 (Prompt_UI_Dot1_Theme.md muc 3d): chuoi 1 doc --brand RUNTIME (khong hardcode nua,
// doi theo thuong hieu tenant) - doc trong ham (khong phai hang so module-level) de luon lay
// dung gia tri MOI NHAT cua bien CSS luc ve, khong bi "dong bang" gia tri luc file duoc import.
// Chuoi phu (2, 3) la mau ngu nghia/phu - GIU NGUYEN, khong doi theo brand (dung y prompt).
function seriesColor(i) {
  if (i === 0) {
    const brand = getComputedStyle(document.documentElement).getPropertyValue('--brand').trim()
    return brand || '#2E6F40'
  }
  return ['#68BA7F', '#C88A3C'][i - 1] || '#68BA7F'
}

// Xu huong nhieu thang (1-3 chuoi) - dung truc tiep chart.js, cung quy uoc voi RadarChart.jsx.
// series: [{ label, data: number[] }]
export default function LineChart({ labels, series, height = 260, max = 100 }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current) return undefined
    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0, max, grid: { color: '#E4EFE7' } }, x: { grid: { display: false } } },
        plugins: { legend: { display: series.length > 1, position: 'bottom' } },
      },
    })
    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [max])

  useEffect(() => {
    if (!chartRef.current) return
    chartRef.current.data.labels = labels
    chartRef.current.data.datasets = series.map((s, i) => ({
      label: s.label,
      data: s.data,
      borderColor: seriesColor(i),
      backgroundColor: seriesColor(i),
      pointRadius: 4,
      tension: 0.25,
    }))
    chartRef.current.options.plugins.legend.display = series.length > 1
    chartRef.current.update()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(labels), JSON.stringify(series)])

  return (
    <div style={{ height, position: 'relative' }}>
      <canvas ref={canvasRef} />
    </div>
  )
}
