/**
 * 管理端知识库数据获取层（接口文档第 14 章 14.1–14.4，B4-a）。
 * 全部接口要求 role=admin（后端 require_admin，非管理员 → code 1003 / 403）。
 */
import { apiGet, apiPost, apiPostForm, apiRequest } from './api'

/** 文档入库状态机（接口文档 14.1） */
export type KbDocStatus = 'pending' | 'indexing' | 'indexed' | 'failed'

/** 知识库文档（KnowledgeDocument，接口文档 14.2） */
export interface KbDocument {
  id: string
  title: string
  filename: string
  size: number
  category?: string | null
  status: KbDocStatus
  chunks: number
  uploadedAt: string | null
}

export interface KbDocumentPage {
  items: KbDocument[]
  total: number
  page: number
  pageSize: number
}

export interface KbUploadResult {
  taskId: string
  documents: KbDocument[]
}

export interface KbDeleteResult {
  id: string
  deleted: boolean
  removedChunks: number
}

/** 检索测试命中切片（接口文档 14.4） */
export interface KbSearchHit {
  chunkId: string
  documentId: string
  documentTitle: string
  content: string
  /** rerank 重排分 0-1（降级时为 RRF 归一化分） */
  score: number
  /** 向量余弦相似度 0-1 */
  vectorScore: number
  /** BM25 原始分（可选） */
  bm25Score?: number | null
  sourceLocation: string
}

export interface KbSearchResult {
  rerankerUsed: boolean
  results: KbSearchHit[]
}

/** 14.2 文档列表（分页 + keyword/status 过滤）。 */
export function listKbDocuments(
  params: { page?: number; pageSize?: number; keyword?: string; status?: KbDocStatus } = {}
): Promise<KbDocumentPage> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.pageSize) qs.set('pageSize', String(params.pageSize))
  if (params.keyword) qs.set('keyword', params.keyword)
  if (params.status) qs.set('status', params.status)
  const suffix = qs.toString()
  return apiGet<KbDocumentPage>(`/admin/kb/documents${suffix ? `?${suffix}` : ''}`)
}

/** 14.1 multipart 上传，返回 taskId（入库异步，列表轮询刷新状态）+ pending 文档。 */
export function uploadKbDocuments(files: File[], category?: string, tags?: string): Promise<KbUploadResult> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  if (category) form.append('category', category)
  if (tags) form.append('tags', tags)
  return apiPostForm<KbUploadResult>('/admin/kb/upload', form)
}

/** 14.3 删除文档 + 同步清理向量切片，返回 removedChunks。 */
export function deleteKbDocument(id: string): Promise<KbDeleteResult> {
  return apiRequest<KbDeleteResult>(`/admin/kb/documents/${id}`, { method: 'DELETE' })
}

/** 14.4 检索测试：混合检索 → 重排，返回 chunk + rerank/vector/bm25 分数 + 来源定位。 */
export function kbSearchTest(query: string, topK = 5): Promise<KbSearchResult> {
  return apiPost<KbSearchResult>('/admin/kb/search-test', { query, topK })
}
