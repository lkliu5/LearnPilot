import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { CURRENT_KP_ID } from '../data/knowledgePoints'

/**
 * 知识点掌握度状态：完成的唯一判定 = 通过分阶测试（在资源页 quiz 处置位 passed）。
 * 学习路径 / 知识图谱 / 学情概览 都从这里派生，保证"通过后只更新一次、多处同步"。
 */
export type KPStatus = 'learning' | 'pending-check' | 'passed'

interface MasteryState {
  status: Record<string, KPStatus>
  /** 点击"去检验"：学习中 → 待检验（已通过不回退）*/
  goCheck: (id: string) => void
  /** 测试通过：→ 已通过（幂等，仅首次置位算新掌握）*/
  markPassed: (id: string) => void
  reset: () => void
}

/** 初始：当前知识点处于"学习中"，其余按各自种子数据 */
const initial = (): Record<string, KPStatus> => ({ [CURRENT_KP_ID]: 'learning' })

export const useMastery = create<MasteryState>()(
  persist(
    (set) => ({
      status: initial(),
      goCheck: (id) =>
        set((s) =>
          s.status[id] === 'passed' ? s : { status: { ...s.status, [id]: 'pending-check' } }
        ),
      markPassed: (id) =>
        set((s) => (s.status[id] === 'passed' ? s : { status: { ...s.status, [id]: 'passed' } })),
      reset: () => set({ status: initial() }),
    }),
    { name: 'zx-mastery' }
  )
)

export const STATUS_LABEL: Record<KPStatus, string> = {
  learning: '学习中',
  'pending-check': '待检验',
  passed: '已通过',
}
