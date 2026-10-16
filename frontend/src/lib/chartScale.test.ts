import { describe, expect, it } from 'vitest'
import { monthStarts, niceScale } from './chartScale'

describe('niceScale', () => {
  it('加權指數半年區間取整齊刻度並包住全部資料', () => {
    const s = niceScale([37132.02, 49822.55, 47111.26])
    expect(s.ticks).toEqual([35000, 40000, 45000, 50000])
    expect(s.min).toBeLessThanOrEqual(37132.02)
    expect(s.max).toBeGreaterThanOrEqual(49822.55)
  })
})

describe('monthStarts', () => {
  it('每月第一筆', () => {
    expect(monthStarts(['2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02'])).toEqual([
      { index: 0, label: '9月' },
      { index: 2, label: '10月' },
    ])
  })
})
