/**
 * 学情概览数据获取层（接口文档第 12 章，接口 29）。
 * 聚合接口：综合分 / 强弱项 / 雷达 / 对标摘要等均与明细接口同口径。
 */
import { apiGet } from './api'

export interface TopicMastery {
  name: string
  mastery: number
}

export interface DashboardOverview {
  overall_level: string
  overall_score: number
  /** 图谱覆盖率 0-1 */
  knowledge_graph_coverage: number
  learned_resources: number
  strong_topics: TopicMastery[]
  weak_topics: TopicMastery[]
  radar: {
    dimensions: string[]
    values: number[]
  }
  comparison: { betterThanPct: number }
  /** 岗位对标摘要（来自 Journey） */
  targetSummary: {
    hasDiagnosed: boolean
    targetJobName: string | null
    matchPct: number | null
  }
}

/** 12.1 获取学情概览聚合数据。 */
export function getDashboardOverview(): Promise<DashboardOverview> {
  return apiGet<DashboardOverview>('/dashboard/overview')
}
