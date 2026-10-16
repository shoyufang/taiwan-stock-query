import { describe, expect, it } from 'vitest'
import { arrow, direction, fmtDateLong, fmtPct, fmtPrice, fmtSigned, fmtWanLots, fmtYi } from './format'

describe('format', () => {
  it('股價整數不帶小數、其餘兩位', () => {
    expect(fmtPrice(2420)).toBe('2,420')
    expect(fmtPrice(87.4)).toBe('87.40')
  })
  it('正負號用真正的減號', () => {
    expect(fmtSigned(141.39, 2)).toBe('+141.39')
    expect(fmtSigned(-1554899)).toBe('−1,554,899')
    expect(fmtSigned(0)).toBe('0')
    expect(fmtPct(-0.82)).toBe('−0.82%')
  })
  it('單位換算', () => {
    expect(fmtYi(993_814_830_090)).toBe('9,938')
    expect(fmtWanLots(532182)).toBe('+53.2')
    expect(fmtWanLots(-1554899)).toBe('−155.5')
  })
  it('方向與箭頭', () => {
    expect(direction(1)).toBe('up')
    expect(direction(-1)).toBe('down')
    expect(direction(0)).toBe('flat')
    expect(arrow(-1)).toBe('▼')
  })
  it('長日期含星期', () => {
    expect(fmtDateLong('2026-10-16')).toBe('2026 年 10 月 16 日（五）')
  })
})
