/**
 * 学情概览数据获取层（接口文档第 12 章，接口 29）。
 * 聚合接口：综合分 / 强弱项 / 雷达 / 对标摘要等均与明细接口同口径。
 */
import { apiGet } from './api'
import { CANONICAL_DIMS, type PortraitDimension } from './profileDialogue'

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

/** synthesizeOverview 产物：仅「画像可推导」的部分（综合分/水平/雷达/强弱项）。 */
export interface SynthesizedOverview {
  overall_level: string
  overall_score: number
  radar: { dimensions: string[]; values: number[] }
  strong_topics: TopicMastery[]
  weak_topics: TopicMastery[]
}

/**
 * 由「真实学习画像维度」合成学情概览——确认弹窗与 Mock 模式首页共用，保证两处口径一致。
 *
 * 仅合成画像本身能推导的字段：
 * - 雷达：6 个异质画像维度，可量化维度（知识基础）取 score，其余取 confidence×100；
 * - 优势：source≠inferred 且取值高的维度；盲区：inferred 或取值偏低的维度；
 * - 综合分 / 水平：可用取值的均值分档。
 *
 * 不合成 knowledge_graph_coverage / learned_resources——它们属「学习活动」指标，
 * 刚诊断、未做题的用户应为 0/空，随真实 Mastery 增长，由首页另取（不在此臆造）。
 */
export function synthesizeOverview(dims: PortraitDimension[]): SynthesizedOverview {
  // 按 CANONICAL_DIMS 稳定排序（对话诊断的 6 维），其余维度（如表单入口的知识点自评）顺次附后，
  // 保证雷达轴次序固定且不丢维度
  const canon = CANONICAL_DIMS.map((c) => dims.find((d) => d.key === c.key)).filter(
    (d): d is PortraitDimension => !!d
  )
  const extras = dims.filter((d) => !CANONICAL_DIMS.some((c) => c.key === d.key))
  const ordered = [...canon, ...extras]
  const axisOf = (d: PortraitDimension) =>
    typeof d.score === 'number' ? d.score : Math.round(d.confidence * 100)

  const radar = {
    dimensions: ordered.map((d) => d.label),
    values: ordered.map(axisOf),
  }

  const scored = ordered.map((d) => ({ name: d.label, mastery: axisOf(d), inferred: d.source === 'inferred' }))
  const strong_topics = scored
    .filter((s) => !s.inferred)
    .sort((a, b) => b.mastery - a.mastery)
    .slice(0, 3)
    .map(({ name, mastery }) => ({ name, mastery }))
  const weak_topics = scored
    .filter((s) => s.inferred || s.mastery < 60)
    .sort((a, b) => a.mastery - b.mastery)
    .slice(0, 3)
    .map(({ name, mastery }) => ({ name, mastery }))

  const overall_score = scored.length
    ? Math.round((scored.reduce((sum, s) => sum + s.mastery, 0) / scored.length) * 10) / 10
    : 0
  const overall_level =
    overall_score >= 80 ? '高级' : overall_score >= 60 ? '中级' : overall_score >= 40 ? '入门' : '初学'

  return { overall_level, overall_score, radar, strong_topics, weak_topics }
}
