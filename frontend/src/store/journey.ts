import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * 学习闭环进度（画像→学习→评估→画像更新）的前端状态。
 * 仅两个主标志即可推导"用户当前处于哪一步"，持久化到 localStorage。
 */
export type JourneyStep = 'diagnose' | 'generate-path' | 'learn' | 'review'

interface JourneyState {
  /** 已完成 ① 画像诊断 */
  hasDiagnosed: boolean
  /** 已生成 ② 学习路径 */
  hasGeneratedPath: boolean
  /** 画像诊断选定的目标岗位（用于首页轻量摘要）*/
  targetJobName?: string
  /** 与目标岗位的对标进度 %（达标维度占比，用于首页轻量摘要）*/
  matchPct?: number
  completeDiagnosis: (result?: { targetJobName?: string; matchPct?: number }) => void
  generatePath: () => void
  resetJourney: () => void
}

export const useJourney = create<JourneyState>()(
  persist(
    (set) => ({
      hasDiagnosed: false,
      hasGeneratedPath: false,
      targetJobName: undefined,
      matchPct: undefined,
      completeDiagnosis: (result) =>
        set({
          hasDiagnosed: true,
          ...(result?.targetJobName !== undefined ? { targetJobName: result.targetJobName } : {}),
          ...(result?.matchPct !== undefined ? { matchPct: result.matchPct } : {}),
        }),
      generatePath: () => set({ hasGeneratedPath: true }),
      resetJourney: () =>
        set({ hasDiagnosed: false, hasGeneratedPath: false, targetJobName: undefined, matchPct: undefined }),
    }),
    { name: 'zx-progress' }
  )
)

/** 由两个主标志（+ 路径是否学完）派生当前所处步骤 */
export function getJourneyStep(
  s: Pick<JourneyState, 'hasDiagnosed' | 'hasGeneratedPath'>,
  allLessonsDone = false
): JourneyStep {
  if (!s.hasDiagnosed) return 'diagnose'
  if (!s.hasGeneratedPath) return 'generate-path'
  if (allLessonsDone) return 'review'
  return 'learn'
}
