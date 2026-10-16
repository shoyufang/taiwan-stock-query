// 走勢圖刻度：取整齊的格線值（例如每 5,000 點），並保留上下留白。

export interface Scale {
  min: number
  max: number
  ticks: number[]
}

export function niceStep(range: number, targetTicks = 4): number {
  const raw = range / targetTicks
  const mag = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / mag
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10
  return nice * mag
}

export function niceScale(values: number[], targetTicks = 4): Scale {
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const step = niceStep(hi - lo || Math.abs(hi) || 1, targetTicks)
  const min = Math.floor(lo / step) * step
  const max = Math.ceil(hi / step) * step
  const ticks: number[] = []
  for (let v = min; v <= max + step / 2; v += step) ticks.push(Math.round(v * 1e6) / 1e6)
  return { min, max, ticks }
}

/** 月份第一個交易日的索引與標籤，例如 [{index: 0, label: '4月'}, …] */
export function monthStarts(dates: string[]): { index: number; label: string }[] {
  const out: { index: number; label: string }[] = []
  dates.forEach((d, i) => {
    const m = d.slice(5, 7)
    if (i === 0 || dates[i - 1].slice(5, 7) !== m) out.push({ index: i, label: `${Number(m)}月` })
  })
  return out
}
