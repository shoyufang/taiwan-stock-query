// 盤中／盤後模式判斷。台灣無日光節約時間，固定 UTC+8 換算。
// 尚未處理國定假日（P2 改接證交所休市日資料）。

export type Mode = 'live' | 'close'

export interface ModeOverride {
  mode: Mode
  until: string // ISO 時間；過了就恢復自動
}

const TAIPEI_OFFSET_MS = 8 * 3600_000
const DAY_MS = 86_400_000
const SESSION_OPEN_MIN = 8 * 60 + 30 // 08:30
const SESSION_CLOSE_MIN = 13 * 60 + 45 // 13:45

function isWeekday(dow: number): boolean {
  return dow >= 1 && dow <= 5
}

export function isTradingSession(now: Date): boolean {
  const t = new Date(now.getTime() + TAIPEI_OFFSET_MS)
  const minutes = t.getUTCHours() * 60 + t.getUTCMinutes()
  return isWeekday(t.getUTCDay()) && minutes >= SESSION_OPEN_MIN && minutes < SESSION_CLOSE_MIN
}

/** 下一次盤中／盤後切換的時間點（平日 08:30 或 13:45）。 */
export function nextBoundary(now: Date): Date {
  const t = new Date(now.getTime() + TAIPEI_OFFSET_MS)
  const dayStart = Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), t.getUTCDate())
  for (let d = 0; d < 8; d++) {
    for (const minute of [SESSION_OPEN_MIN, SESSION_CLOSE_MIN]) {
      const shifted = dayStart + d * DAY_MS + minute * 60_000
      if (!isWeekday(new Date(shifted).getUTCDay())) continue
      const real = shifted - TAIPEI_OFFSET_MS
      if (real > now.getTime()) return new Date(real)
    }
  }
  return new Date(now.getTime() + DAY_MS)
}

export function autoMode(now: Date): Mode {
  return isTradingSession(now) ? 'live' : 'close'
}

export function resolveMode(now: Date, override?: ModeOverride | null): Mode {
  if (override && new Date(override.until).getTime() > now.getTime()) return override.mode
  return autoMode(now)
}
