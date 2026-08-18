/**
 * 按 symbol 串行化写入 — 后端 set_tags 是整体替换语义, 并行请求乱序到达会互相覆盖
 * (最终落库 ≠ 最后点击), 所以后一次写必须等前一次完成后再发。
 */
/**
 * R 只出现在 send 返回位置, TS 无法从箭头函数推断 (静默落 unknown);
 * 需具体返回类型时显式传: `createPerSymbolQueue<T, { ... }>(send)`。
 */
export function createPerSymbolQueue<T, R = unknown>(
  send: (symbol: string, payload: T) => Promise<R>,
) {
  // map 存吞掉 rejection 的副本 (失败不卡链); run 原样返回, 调用方仍收到错误
  const chains = new Map<string, Promise<unknown>>()
  return function enqueue(symbol: string, payload: T): Promise<R> {
    const prev = chains.get(symbol) ?? Promise.resolve()
    const run = prev.then(() => send(symbol, payload))
    chains.set(symbol, run.catch(() => {}))
    return run
  }
}
