import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { USE_REAL_API } from '../services/api'
import { aggregateExternalResources } from '../services/resource'
import { getResourceKpId } from '../services/resourceNav'

type ResType = '视频' | '论文' | '文档' | '课程'

export interface ExternalResource {
  id: string
  type: ResType
  title: string
  source: string
  url: string
  /** 可嵌入的播放地址（视频类）*/
  embed?: string
  duration?: string
  /** 审核 Agent 给出的相关性 / 可信度评分 */
  relevance: number
  credibility: number
  reason: string
}

/* 模拟「资源聚合 Agent」检索 + 「审核 Agent」评分后的精选外部资源 */
const resources: ExternalResource[] = [
  {
    id: 'r1',
    type: '视频',
    title: '3Blue1Brown：神经网络是什么？',
    source: 'YouTube · 3Blue1Brown',
    url: 'https://www.youtube.com/watch?v=aircAruvnKk',
    embed: 'https://www.youtube.com/embed/aircAruvnKk',
    duration: '19:13',
    relevance: 98,
    credibility: 97,
    reason: '可视化讲解神经元与权重，直观契合你当前「神经网络基础」知识点。',
  },
  {
    id: 'r2',
    type: '课程',
    title: 'CS231n：卷积神经网络（Stanford）',
    source: 'Stanford 公开课',
    url: 'https://cs231n.github.io/',
    duration: '系列',
    relevance: 92,
    credibility: 96,
    reason: '权威课程，从神经网络基础平滑过渡到 CNN，匹配你的下一步学习路径。',
  },
  {
    id: 'r3',
    type: '论文',
    title: 'Attention Is All You Need',
    source: 'arXiv:1706.03762',
    url: 'https://arxiv.org/abs/1706.03762',
    duration: '15 页',
    relevance: 78,
    credibility: 99,
    reason: 'Transformer 奠基论文，作为你「待提升领域」的进阶拓展读物。',
  },
  {
    id: 'r4',
    type: '文档',
    title: 'PyTorch 官方教程 · 构建神经网络',
    source: 'pytorch.org',
    url: 'https://pytorch.org/tutorials/beginner/basics/buildmodel_tutorial.html',
    duration: '实操',
    relevance: 90,
    credibility: 95,
    reason: '官方动手教程，把讲义中的前向传播落到 nn.Module 代码实践。',
  },
]

const typeMeta: Record<ResType, { icon: string; color: string }> = {
  视频: { icon: '🎬', color: 'var(--primary-600)' },
  论文: { icon: '📄', color: 'var(--purple-600)' },
  文档: { icon: '📘', color: 'var(--success-600)' },
  课程: { icon: '🎓', color: 'var(--warning-600)' },
}

export default function ResourceAggregator() {
  const [active, setActive] = useState<string | null>(null)

  /* 联调数据源（8.6 增量）：POST /resource/external/aggregate —— AI 联网搜索聚合
     （后端代理联网 + 聚合 Agent 整理 + critic 评分；无搜索能力 → 种子兜底 online=false）。
     kpId 来自 resourceNav 路由通道；mock 模式不请求，初值即本地精选示例，渲染零差异。 */
  const [list, setList] = useState<ExternalResource[]>(resources)
  const [online, setOnline] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(false)
  const loadAggregate = useCallback(async () => {
    if (!USE_REAL_API) return
    setLoading(true)
    try {
      const res = await aggregateExternalResources(getResourceKpId())
      setList(res.items)
      setOnline(res.online)
    } catch (e) {
      console.error('[external] 联网聚合失败，保留示例兜底', e)
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    void loadAggregate()
  }, [loadAggregate])

  const activeRes = list.find((r) => r.id === active && r.embed)

  return (
    <div className="agg">
      <div className="agg__head">
        <span className="agg__head-icon">🔗</span>
        <div className="agg__head-main">
          <div className="agg__head-title">
            AI 已为你精选 {list.length} 个优质外部资源
            {USE_REAL_API && online !== null && (
              <span className={`agg__badge ${online ? 'agg__badge--online' : 'agg__badge--offline'}`}>
                {online ? '🌐 联网搜索聚合' : '📦 离线兜底（未配置搜索 API）'}
              </span>
            )}
          </div>
          <div className="agg__head-sub">资源聚合 Agent 联网检索 · 审核 Agent 按相关性 + 来源可信度评分排序</div>
        </div>
        {USE_REAL_API && (
          <button className="agg__refresh" onClick={() => void loadAggregate()} disabled={loading}>
            {loading ? '联网搜索中…' : '🔄 重新联网搜索'}
          </button>
        )}
      </div>

      {/* 嵌入播放区 */}
      {activeRes && (
        <motion.div
          className="agg__embed"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
        >
          <div className="agg__embed-bar">
            <span>{activeRes.title}</span>
            <button className="agg__embed-close" onClick={() => setActive(null)}>✕ 关闭</button>
          </div>
          <iframe
            className="agg__iframe"
            src={activeRes.embed}
            title={activeRes.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </motion.div>
      )}

      {/* 资源卡片列表 */}
      <div className="agg__list">
        {list.map((r) => {
          const m = typeMeta[r.type]
          return (
            <div key={r.id} className="agg__card">
              <div className="agg__card-top">
                <span className="agg__type" style={{ color: m.color }}>{m.icon} {r.type}</span>
                {r.duration && <span className="agg__duration">{r.duration}</span>}
              </div>
              <h4 className="agg__card-title">{r.title}</h4>
              <div className="agg__source">{r.source}</div>
              <p className="agg__reason">💡 {r.reason}</p>

              <div className="agg__scores">
                <span className="agg__score">
                  相关性
                  <span className="agg__score-bar"><span className="agg__score-fill agg__score-fill--rel" style={{ width: `${r.relevance}%` }} /></span>
                  {r.relevance}
                </span>
                <span className="agg__score">
                  可信度
                  <span className="agg__score-bar"><span className="agg__score-fill agg__score-fill--cred" style={{ width: `${r.credibility}%` }} /></span>
                  {r.credibility}
                </span>
              </div>

              <div className="agg__actions">
                {r.embed && (
                  <button className="agg__btn agg__btn--play" onClick={() => setActive(r.id)}>▶ 内嵌观看</button>
                )}
                <a className="agg__btn agg__btn--open" href={r.url} target="_blank" rel="noreferrer">↗ 原站打开</a>
              </div>
            </div>
          )
        })}
      </div>

      <p className="agg__note">
        {USE_REAL_API && online === false
          ? '当前未配置联网搜索 API（走种子库兜底）。配置 SEARCH_PROVIDER=tavily + SEARCH_API_KEY 后，即由后端联网搜索 + 聚合/审核 Agent 实时产出。'
          : '由后端聚合 Agent 联网检索 YouTube / B站 / arXiv / 慕课等资源，经审核 Agent 过滤低质与不相关资源并评分排序。'}
      </p>
    </div>
  )
}
