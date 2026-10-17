// 自選股清單操作（純函式，方便測試）

export function addCode(codes: string[], code: string, max = 60): string[] {
  if (codes.includes(code) || codes.length >= max) return codes
  return [...codes, code]
}

export function removeCode(codes: string[], code: string): string[] {
  return codes.filter((c) => c !== code)
}

export function move(codes: string[], code: string, delta: -1 | 1): string[] {
  const i = codes.indexOf(code)
  const j = i + delta
  if (i < 0 || j < 0 || j >= codes.length) return codes
  const next = [...codes]
  ;[next[i], next[j]] = [next[j], next[i]]
  return next
}
