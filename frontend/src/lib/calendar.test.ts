import { describe, expect, it } from 'vitest'
import { dayLabel, groupEvents, type CalEvent, type EventKind } from './calendar'

const ev: CalEvent[] = [
  { date: '2026-10-20', kind: 'dividend', code: '2330', name: '台積電', title: '除息', detail: '' },
  { date: '2026-10-15', kind: 'conference', code: '1303', name: '南亞', title: '法說會', detail: '' },
  { date: '2026-10-20', kind: 'conference', code: '2317', name: '鴻海', title: '法說會', detail: '' },
  { date: '2026-11-10', kind: 'deadline', title: '10 月營收公布期限', detail: '' },
]
const all = new Set<EventKind>(['dividend', 'conference', 'deadline'])

describe('groupEvents', () => {
  it('依日期分組並隱藏過去事件', () => {
    const g = groupEvents(ev, { kinds: all, watchOnly: false, showPast: false }, new Set(), '2026-10-17')
    expect(g.map(([d, l]) => [d, l.length])).toEqual([
      ['2026-10-20', 2],
      ['2026-11-10', 1],
    ])
  })
  it('只看自選股時保留公布期限', () => {
    const g = groupEvents(ev, { kinds: all, watchOnly: true, showPast: true }, new Set(['2330']), '2026-10-17')
    expect(g.flatMap(([, l]) => l.map((e) => e.code ?? e.title))).toEqual(['2330', '10 月營收公布期限'])
  })
  it('類型篩選', () => {
    const g = groupEvents(ev, { kinds: new Set(['conference']), watchOnly: false, showPast: true }, new Set(), '2026-10-17')
    expect(g.flatMap(([, l]) => l.map((e) => e.code))).toEqual(['1303', '2317'])
  })
})

describe('dayLabel', () => {
  it('星期與今天', () => {
    expect(dayLabel('2026-10-17', '2026-10-17')).toBe('今天 10/17（六）')
    expect(dayLabel('2026-10-19', '2026-10-17')).toBe('10/19（一）')
  })
})
