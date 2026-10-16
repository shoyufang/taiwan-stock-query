import { describe, expect, it } from 'vitest'
import { addCode, move, removeCode } from './watchlistOps'

describe('watchlistOps', () => {
  it('加入不重複、有上限', () => {
    expect(addCode(['2330'], '2330')).toEqual(['2330'])
    expect(addCode(['2330'], '6488')).toEqual(['2330', '6488'])
    expect(addCode(['a', 'b'], 'c', 2)).toEqual(['a', 'b'])
  })
  it('移除', () => expect(removeCode(['2330', '6488'], '2330')).toEqual(['6488']))
  it('上下移動、邊界不動', () => {
    expect(move(['a', 'b', 'c'], 'b', -1)).toEqual(['b', 'a', 'c'])
    expect(move(['a', 'b', 'c'], 'c', 1)).toEqual(['a', 'b', 'c'])
  })
})
