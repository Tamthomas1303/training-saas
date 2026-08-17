import { useEffect, useRef } from 'react'
import { Chart, BarController, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js'

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

// Mau trang thai dung chung toan he thong (xem theme.css :root) - KHONG bia mau moi, tai dung
// dung 3 mau xanh/vang/do da dung cho badge/indicator_color khap noi.
const STATUS_COLOR = { green: '#2E6F40', yellow: '#C88A3C', red: '#C0392B' }
const DEFAULT_COLOR = '#68BA7F'

// Bar ngang, moi cot to mau rieng theo trang thai (vd xep hang nha hang theo nguong) - dung
// truc tiep chart.js (khong qua react-chartjs-2), cung quy uoc voi RadarChart.jsx.
export default function BarChart({ labels, values, colors, height = 320, max = 100 }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current) return undefined
    chartRef.current = new Chart(canvasRef.current, {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { min: 0, max, grid: { color: '#E4EFE7' } }, y: { grid: { display: false } } },
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
      },
    })
    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [max])

  useEffect(() => {
    if (!chartRef.current) return
    chartRef.current.data.labels = labels
    chartRef.current.data.datasets = [{
      data: values,
      backgroundColor: (colors || []).map((c) => STATUS_COLOR[c] || DEFAULT_COLOR),
      borderRadius: 4,
      barThickness: 18,
    }]
    chartRef.current.update()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(labels), JSON.stringify(values), JSON.stringify(colors)])

  return (
    <div style={{ height, position: 'relative' }}>
      <canvas ref={canvasRef} />
    </div>
  )
}
