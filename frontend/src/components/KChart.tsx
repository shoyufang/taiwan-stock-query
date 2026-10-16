import { CandlestickSeries, ColorType, createChart, HistogramSeries, LineSeries } from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import type { Bar } from '../lib/api'
import { sma } from '../lib/indicators'
import type { Mode } from '../lib/marketMode'

export const MA_LINES = [
  { period: 5, color: '#e0a83d' },
  { period: 20, color: '#5b8def' },
  { period: 60, color: '#b06ad9' },
]

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/** 日 K（紅漲綠跌）＋均線＋下方成交量。顏色取自設計 token，切換模式時重建。 */
type Updater = { candle: (b: Bar) => void; volume: (b: Bar, prevClose: number) => void } | null

export function KChart({ bars, liveBar, mode, height = 420 }: { bars: Bar[]; liveBar?: Bar; mode: Mode; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const updater = useRef<Updater>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || bars.length === 0) return
    const up = token('--up')
    const down = token('--down')
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: token('--surface') },
        textColor: token('--muted'),
        fontFamily: token('--font-num'),
        panes: { separatorColor: token('--border') },
      },
      grid: { vertLines: { visible: false }, horzLines: { color: token('--border') } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: { locale: 'zh-TW' },
    })
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: up,
      downColor: down,
      borderUpColor: up,
      borderDownColor: down,
      wickUpColor: up,
      wickDownColor: down,
      priceLineVisible: true,
    })
    candles.setData(bars.map((b) => ({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close })))
    for (const m of MA_LINES) {
      const line = chart.addSeries(LineSeries, {
        color: m.color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      line.setData(sma(bars, m.period))
    }
    const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false }, 1)
    vol.setData(
      bars.map((b, i) => ({
        time: b.date,
        value: b.volume,
        color: (i === 0 ? b.close >= b.open : b.close >= bars[i - 1].close) ? up + '99' : down + '99',
      })),
    )
    chart.panes()[1]?.setHeight(Math.round(height * 0.22))
    chart.timeScale().fitContent()
    updater.current = {
      candle: (b) => candles.update({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close }),
      volume: (b, prevClose) => vol.update({ time: b.date, value: b.volume, color: (b.close >= prevClose ? up : down) + '99' }),
    }
    return () => {
      updater.current = null
      chart.remove()
    }
  }, [bars, mode, height])

  // 盤中即時：只更新最後一根，不重建圖表
  useEffect(() => {
    const last = bars[bars.length - 1]
    if (!liveBar || !updater.current || !last || liveBar.date < last.date) return
    const prevClose = liveBar.date === last.date ? (bars[bars.length - 2]?.close ?? last.open) : last.close
    updater.current.candle(liveBar)
    updater.current.volume(liveBar, prevClose)
  }, [liveBar, bars])

  return <div ref={ref} style={{ height }} role="img" aria-label="日 K 線圖（含 5、20、60 日均線與成交量）" />
}
