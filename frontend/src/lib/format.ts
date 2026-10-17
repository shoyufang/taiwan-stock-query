// 數字顯示規則（全站一致）。台股慣例：紅漲綠跌，另附 ▲▼ 與正負號，不只靠顏色。

export type Direction = 'up' | 'down' | 'flat'

export function direction(value: number): Direction {
  return value > 0 ? 'up' : value < 0 ? 'down' : 'flat'
}

const MINUS = '−' // 用真正的減號，與等寬數字對齊

export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString('en-US')
}

/** 股價：整數不帶小數，其餘兩位。 */
export function fmtPrice(n: number): string {
  return Number.isInteger(n) ? fmtInt(n) : n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function fmtFixed(n: number, digits = 2): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** 帶正負號：+1,234 / −1,234 / 0 */
export function fmtSigned(n: number, digits = 0): string {
  const body = digits ? fmtFixed(Math.abs(n), digits) : fmtInt(Math.abs(n))
  return n > 0 ? `+${body}` : n < 0 ? `${MINUS}${body}` : body
}

export function fmtPct(n: number): string {
  return `${fmtSigned(n, 2)}%`
}

export function arrow(n: number): string {
  return n > 0 ? '▲' : n < 0 ? '▼' : ''
}

/** 元 → 億元 */
export function fmtYi(twd: number, digits = 0): string {
  return (twd / 1e8).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** 張 → 萬張（帶正負號） */
export function fmtWanLots(lots: number): string {
  return fmtSigned(lots / 10_000, 1)
}

const WEEKDAY = ['日', '一', '二', '三', '四', '五', '六']

/** '2026-10-16' → '2026 年 10 月 16 日（五）' */
export function fmtDateLong(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const wd = WEEKDAY[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]
  return `${y} 年 ${m} 月 ${d} 日（${wd}）`
}

/** '2026-10-15' → '10/15' */
export function fmtMonthDay(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${m}/${d}`
}
