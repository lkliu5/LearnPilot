/**
 * 学习资源 + 测验数据获取层
 * （接口文档第 8 章讲义/外部资源 / 第 9 章测验/错题强化，接口 16/17/21/23/24/25）。
 */
import { apiGet, apiPost } from './api'
import type { QuizQuestion } from '../components/QuizRenderer'
import type { ExternalResource } from '../components/ResourceAggregator'

export interface LectureData {
  kpId: string
  difficulty: string
  markdown: string
  sources: { title: string; type: string; confidence: number }[]
  hallucinationRate: number
}

/** 8.2 生成自适应讲义（difficulty: 入门|初级|高级）。 */
export function getLecture(kpId: string, difficulty: string): Promise<LectureData> {
  return apiPost<LectureData>('/resource/lecture', { kpId, difficulty })
}

/** 9.1 获取测验题（含 correct_answer / explanation，契约 2.5）。 */
export function getQuiz(kpId: string): Promise<{ questions: QuizQuestion[] }> {
  return apiGet<{ questions: QuizQuestion[] }>(`/quiz/${kpId}`)
}

export interface QuizSubmitResult {
  score: number
  passed: boolean
  correctCount: number
  total: number
  wrong: QuizQuestion[]
  masteryUpdated: { id: string; status: string } | null
}

/** 9.1 提交作答并判分。≥60 后端联动掌握度置 passed。 */
export function submitQuiz(
  kpId: string,
  answers: Record<string, string | string[]>
): Promise<QuizSubmitResult> {
  const payload = Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer }))
  return apiPost<QuizSubmitResult>(`/quiz/${kpId}/submit`, { answers: payload })
}

/** 8.6 外部资源聚合（聚合 Agent 检索 + 审核 Agent 评分，已按相关度降序）。 */
export function getExternalResources(kpId: string): Promise<ExternalResource[]> {
  return apiGet<ExternalResource[]>(`/resource/external/${kpId}`)
}

/** 9.2 错题强化卡：薄弱点 + 强化讲解 + 一道针对性追加练习。 */
export interface ReinforceCard {
  questionId: string
  point: string
  recap: string
  practice: QuizQuestion
}

/** 9.2 错题强化生成（诊断 Agent 定位薄弱 + 生成 Agent 产出强化内容）。 */
export function reinforce(kpId: string, wrongQuestionIds: string[]): Promise<ReinforceCard[]> {
  return apiPost<ReinforceCard[]>('/reinforce', { kpId, wrongQuestionIds })
}
