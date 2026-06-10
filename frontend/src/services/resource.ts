/**
 * 学习资源 + 测验数据获取层（接口文档第 8 章讲义 / 第 9 章测验，接口 16/17/23/24）。
 */
import { apiGet, apiPost } from './api'
import type { QuizQuestion } from '../components/QuizRenderer'

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
