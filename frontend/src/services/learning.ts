/**
 * 学习路径数据获取层（接口文档第 6 章 + 异步任务 1.4 / 15.2）。
 * 生成路径为耗时操作：提交后拿 taskId，轮询 GET /tasks/{taskId} 至终态。
 */
import { apiGet, apiPost } from './api'
import type { Lesson } from '../data/learningPath'

export interface LearningPathData {
  lessons: Lesson[]
  milestones: { id: number; title: string; completed: boolean; date: string | null }[]
  summary: { completedCount: number; inProgressCount: number; overallProgress: number }
}

/** 6.1 获取个性化学习路径。 */
export function getLearningPath(): Promise<LearningPathData> {
  return apiGet<LearningPathData>('/learning-path')
}

interface TaskState<R> {
  taskId: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  progress?: number
  result?: R
  error?: { code: number; message: string } | null
}

/** 轮询异步任务至终态（接口文档 15.2）。succeeded 返回 result，failed/超时抛错。 */
export async function pollTask<R = unknown>(
  taskId: string,
  { intervalMs = 600, timeoutMs = 30000 }: { intervalMs?: number; timeoutMs?: number } = {}
): Promise<R | undefined> {
  const start = Date.now()
  for (;;) {
    const t = await apiGet<TaskState<R>>(`/tasks/${taskId}`)
    if (t.status === 'succeeded') return t.result
    if (t.status === 'failed') throw new Error(t.error?.message ?? '任务执行失败')
    if (Date.now() - start > timeoutMs) throw new Error('任务轮询超时')
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}

/** 6.2 生成 / 重新规划学习路径：提交任务并轮询至完成。 */
export async function generatePath(targetJobId?: string): Promise<void> {
  const { taskId } = await apiPost<{ taskId: string }>(
    '/learning-path/generate',
    targetJobId ? { targetJobId } : {}
  )
  await pollTask(taskId)
}
