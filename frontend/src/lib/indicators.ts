import type { Bar } from './api'
import type { LiveStock } from './useLiveQuotes'

/** 簡單移動平均；資料不足的前段不輸出。 */
export function sma(bars: Bar[], period: number): { time: string; value: number }[] {
  const out: { time: string; value: number }[] = []
  let sum = 0
  bars.forEach((b, i) => {
    sum += b.close
    if (i >= period) sum -= bars[i - period].close
    if (i >= period - 1) out.push({ time: b.date, value: Math.round((sum / period) * 100) / 100 })
  })
  return out
}

/** 盤中把今天的即時報價轉成一根 K 棒；不是今天的推播回傳 undefined。 */
export function liveToBar(live: LiveStock | undefined, today: string): Bar | undefined {
  if (!live || !live.close || live.time.slice(0, 10) !== today) return undefined
  return {
    date: today,
    open: live.open ?? live.close,
    high: live.high,
    low: live.low,
    close: live.close,
    volume: live.total_volume,
    value: live.total_amount,
  }
}

/** 台北今天的日期（YYYY-MM-DD）。 */
export function taipeiToday(now = new Date()): string {
  return new Date(now.getTime() + 8 * 3600_000).toISOString().slice(0, 10)
}
