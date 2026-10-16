import { describe, expect, it } from 'vitest'
import type { Bar } from './api'
import { liveToBar, sma, taipeiToday } from './indicators'
import type { LiveStock } from './useLiveQuotes'

const bar = (date: string, close: number): Bar => ({ date, open: close, high: close, low: close, close, volume: 1, value: 1 })

describe('sma', () => {
  it('前段不足不輸出，之後為平均', () => {
    expect(sma([bar('d1', 1), bar('d2', 2), bar('d3', 3), bar('d4', 4)], 3)).toEqual([
      { time: 'd3', value: 2 },
      { time: 'd4', value: 3 },
    ])
  })
})

describe('liveToBar', () => {
  const live = { kind: 'stock', code: '2330', time: '2026-10-19T09:30:00', open: 2425, high: 2440, low: 2420, close: 2435, total_volume: 9000, total_amount: 2.2e10 } as LiveStock
  it('今天的推播轉成今天的 K 棒', () => {
    expect(liveToBar(live, '2026-10-19')).toMatchObject({ date: '2026-10-19', open: 2425, close: 2435, volume: 9000 })
  })
  it('不是今天的推播不採用', () => {
    expect(liveToBar({ ...live, time: '2026-10-16T13:30:00' }, '2026-10-19')).toBeUndefined()
  })
})

describe('taipeiToday', () => {
  it('UTC 晚上 20 點已是台北隔天', () => {
    expect(taipeiToday(new Date('2026-10-18T20:00:00Z'))).toBe('2026-10-19')
  })
})
