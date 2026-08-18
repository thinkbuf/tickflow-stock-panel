import { describe, expect, it } from 'vitest'
import { createPerSymbolQueue } from './tagWriteQueue'

function deferred<T = void>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>(r => { resolve = r })
  return { promise, resolve }
}

describe('createPerSymbolQueue', () => {
  it('同 symbol 两连发: 第二个等第一个完成后才发, 顺序保持', async () => {
    const sent: string[][] = []
    const gate = deferred<void>()
    const q = createPerSymbolQueue<string[]>((_symbol, payload) => {
      sent.push(payload)
      if (sent.length === 1) return gate.promise.then(() => 'ok')
      return Promise.resolve('ok')
    })

    const p1 = q('600519.SH', ['A'])
    const p2 = q('600519.SH', ['A', 'B'])
    await Promise.resolve()
    await Promise.resolve()
    expect(sent).toEqual([['A']]) // 第二个还没开始
    gate.resolve()
    await Promise.all([p1, p2])
    expect(sent).toEqual([['A'], ['A', 'B']])
  })

  it('不同 symbol 互不阻塞', async () => {
    const started: string[] = []
    const gate = deferred<void>()
    const q = createPerSymbolQueue<string[]>((symbol) => {
      started.push(symbol)
      if (symbol === 'a') return gate.promise.then(() => 'ok')
      return Promise.resolve('ok')
    })

    const pa = q('a', ['x'])
    const pb = q('b', ['y'])
    await Promise.resolve()
    await Promise.resolve()
    expect(started).toEqual(['a', 'b']) // b 不等 a 完成
    gate.resolve()
    await Promise.all([pa, pb])
  })

  it('前一次失败不阻塞下一次', async () => {
    const q = createPerSymbolQueue<string[]>((_symbol, payload) => {
      if (payload.length === 1) return Promise.reject(new Error('boom'))
      return Promise.resolve('ok')
    })

    const p1 = q('s', ['A'])
    await expect(p1).rejects.toThrow('boom')
    await expect(q('s', ['A', 'B'])).resolves.toBe('ok')
  })

  it('每次调用恰好发一次请求, 完成后再调仍正常', async () => {
    let sends = 0
    const q = createPerSymbolQueue<string[]>(() => {
      sends += 1
      return Promise.resolve('ok')
    })

    await Promise.all([q('s', ['A']), q('s', ['A', 'B']), q('s', ['A', 'B', 'C'])])
    expect(sends).toBe(3)
    // settle 后新一轮调用照常工作且只发一次 (链头覆写, 不累积)
    await q('s', ['D'])
    expect(sends).toBe(4)
  })
})
