import { describe, expect, it } from 'vitest'
import { isToday } from './useLiveQuotes'

describe('isToday（台北日期）', () => {
  const now = new Date('2026-10-19T01:30:00Z') // 台北 10/19 09:30
  it('同一天為 true', () => expect(isToday('2026-10-19T09:29:58', now)).toBe(true))
  it('上個交易日的最後一筆不算即時', () => expect(isToday('2026-10-16T13:30:00', now)).toBe(false))
  it('沒有時間為 false', () => expect(isToday(undefined, now)).toBe(false))
})
