import { describe, expect, it } from 'vitest'
import { isTradingSession, nextBoundary, resolveMode } from './marketMode'

// 台北時間 → Date（台北 = UTC+8）
const tp = (iso: string) => new Date(`${iso}+08:00`)

describe('isTradingSession', () => {
  it('平日盤中為 true', () => {
    expect(isTradingSession(tp('2026-10-15T10:00:00'))).toBe(true)
  })
  it('08:30 開始、13:45 結束（含頭不含尾）', () => {
    expect(isTradingSession(tp('2026-10-15T08:29:59'))).toBe(false)
    expect(isTradingSession(tp('2026-10-15T08:30:00'))).toBe(true)
    expect(isTradingSession(tp('2026-10-15T13:44:59'))).toBe(true)
    expect(isTradingSession(tp('2026-10-15T13:45:00'))).toBe(false)
  })
  it('週末為 false', () => {
    expect(isTradingSession(tp('2026-10-17T10:00:00'))).toBe(false)
    expect(isTradingSession(tp('2026-10-18T10:00:00'))).toBe(false)
  })
})

describe('nextBoundary', () => {
  it('盤中 → 當日 13:45', () => {
    expect(nextBoundary(tp('2026-10-15T10:00:00')).toISOString()).toBe('2026-10-15T05:45:00.000Z')
  })
  it('週五盤後 → 下週一 08:30', () => {
    expect(nextBoundary(tp('2026-10-16T14:00:00')).toISOString()).toBe('2026-10-19T00:30:00.000Z')
  })
  it('平日清晨 → 當日 08:30', () => {
    expect(nextBoundary(tp('2026-10-15T07:00:00')).toISOString()).toBe('2026-10-15T00:30:00.000Z')
  })
})

describe('resolveMode', () => {
  const now = tp('2026-10-15T10:00:00')
  it('無手動設定時依時間', () => {
    expect(resolveMode(now)).toBe('live')
    expect(resolveMode(tp('2026-10-15T20:00:00'))).toBe('close')
  })
  it('手動設定未過期時優先', () => {
    expect(resolveMode(now, { mode: 'close', until: '2026-10-15T05:45:00.000Z' })).toBe('close')
  })
  it('手動設定過期後恢復自動', () => {
    expect(resolveMode(now, { mode: 'close', until: '2026-10-15T01:00:00.000Z' })).toBe('live')
  })
})
