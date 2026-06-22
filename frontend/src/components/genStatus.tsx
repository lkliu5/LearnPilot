/**
 * 资源「逐项生成」状态原语（会话二 TutorResourcePanel 与 主资源生成 LearningResource 共用）。
 *
 * 抽出一套：状态枚举 + 文案/样式映射 + 状态标签组件，两处共享，保证「智能辅导面板」与
 * 「学习资源页·资源中枢」的逐项进度/状态体验完全一致（不另造一套）。
 * 样式类沿用 TutorResourcePanel.css 的 .trp__chip（两处都导入该 CSS）。
 */

export type ItemStatus = 'pending' | 'running' | 'done' | 'error'

export const STATUS_META: Record<ItemStatus, { label: string; cls: string }> = {
  pending: { label: '待生成', cls: 'is-pending' },
  running: { label: '生成中…', cls: 'is-running' },
  done: { label: '已完成', cls: 'is-done' },
  error: { label: '失败', cls: 'is-error' },
}

export function StatusChip({ status }: { status: ItemStatus }) {
  const m = STATUS_META[status]
  return <span className={`trp__chip ${m.cls}`}>{m.label}</span>
}
