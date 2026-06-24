/**
 * 即时辅导·打开总线（B-2 / B-3 解耦用）。
 *
 * 让「选中讲义提问」(SelectionAskBubble)、「主动察觉卡顿」(StuckNudge) 等散落入口
 * 无需层层透传 props，即可命令常驻的 AskTutorDock 打开抽屉并预填/自动发起一次提问。
 * 仅一个消费者（页面内唯一的 dock）订阅，故用极轻量的发布订阅，不引入额外状态库。
 */
export interface OpenTutorPayload {
  /** 预填到输入框 / 直接作为问题上下文发起辅导的文本 */
  question?: string
  /** true 时打开抽屉后立即发起该问题（无需用户再点一次） */
  autoAsk?: boolean
}

type Listener = (payload: OpenTutorPayload) => void
const listeners = new Set<Listener>()

/** dock 挂载时订阅；返回取消订阅函数。 */
export function onOpenTutor(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** 任意入口调用：打开即时辅导（可携带预填问题 + 是否自动发起）。 */
export function openInstantTutor(payload: OpenTutorPayload = {}): void {
  listeners.forEach((l) => l(payload))
}
