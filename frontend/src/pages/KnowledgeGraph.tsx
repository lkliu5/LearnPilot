import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { motion, AnimatePresence } from 'framer-motion'
import { useChartTokens, withAlpha, type ChartTokens } from '../utils/chartTheme'
import PageHeader from '../components/PageHeader'
import { RevealGroup, RevealItem } from '../components/Reveal'
import { useMastery } from '../store/mastery'
import { kpByGraphNode } from '../data/knowledgePoints'
import { USE_REAL_API } from '../services/api'
import { getKnowledgeGraph, type KnowledgeGraphData } from '../services/graph'
import { setResourceNav } from '../services/resourceNav'
import type { PageType } from '../App'
import './KnowledgeGraph.css'
import './admin/admin.css' // 复用 .akb__toast 轻提示样式（AdminKB/AdminPrompts 同形态），零新增样式

/* 掌握状态 → 类别（颜色随主题，从令牌取）*/
const categories = [
  { name: '已掌握' },
  { name: '学习中' },
  { name: '待学习' },
  { name: '知识盲区' },
]

/* 类别色板（4 类）：已掌握=primary · 学习中=primary-d · 待学习=ink-soft · 知识盲区=accent(告警) */
const catColors = (t: ChartTokens) => [t.primary, t.primaryD, t.inkSoft, t.accent]

/* AI 领域知识点（节点）—— category 对应掌握状态，value=掌握度 */
const nodes = [
  { id: 'ml', name: '机器学习基础', category: 0, value: 92 },
  { id: 'nn', name: '神经网络基础', category: 0, value: 85 },
  { id: 'dl', name: '深度学习原理', category: 1, value: 65 },
  { id: 'cnn', name: 'CNN架构', category: 2, value: 30 },
  { id: 'rnn', name: 'RNN架构', category: 2, value: 28 },
  { id: 'attn', name: '注意力机制', category: 3, value: 18 },
  { id: 'transformer', name: 'Transformer', category: 3, value: 15 },
  { id: 'bertgpt', name: 'BERT与GPT', category: 2, value: 22 },
  { id: 'finetune', name: '大模型微调', category: 2, value: 12 },
  { id: 'prompt', name: 'Prompt工程', category: 1, value: 58 },
  { id: 'rag', name: 'RAG检索增强', category: 2, value: 35 },
  { id: 'agent', name: 'AI Agent开发', category: 2, value: 20 },
]

/* 依赖关系（边）：source 是 target 的前置知识 */
const links = [
  { source: 'ml', target: 'nn' },
  { source: 'nn', target: 'dl' },
  { source: 'dl', target: 'cnn' },
  { source: 'dl', target: 'rnn' },
  { source: 'dl', target: 'attn' },
  { source: 'attn', target: 'transformer' },
  { source: 'rnn', target: 'transformer' },
  { source: 'transformer', target: 'bertgpt' },
  { source: 'bertgpt', target: 'finetune' },
  { source: 'transformer', target: 'prompt' },
  { source: 'bertgpt', target: 'rag' },
  { source: 'rag', target: 'agent' },
  { source: 'prompt', target: 'agent' },
  { source: 'finetune', target: 'agent' },
]

export default function KnowledgeGraph({ onNavigate }: { onNavigate?: (page: PageType) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  const t = useChartTokens()
  const colors = catColors(t)
  const masteryStatus = useMastery((s) => s.status)

  /* 节点点击轻提示（非核心 6 节点）：复用 AdminKB toast 形态，3.2s 自动消失 */
  const [toast, setToast] = useState<string | null>(null)
  const toastTimerRef = useRef(0)
  const showToast = (msg: string) => {
    setToast(msg)
    window.clearTimeout(toastTimerRef.current)
    toastTimerRef.current = window.setTimeout(() => setToast(null), 3200)
  }
  useEffect(() => () => window.clearTimeout(toastTimerRef.current), [])

  /* 联调数据源：GET /knowledge-graph（接口 26），节点 category/value 由后端权威推导；
     mock 模式不请求，保持本地种子 + 前端派生。掌握度变化时重取，着色随 useMastery 实时刷新 */
  const [remote, setRemote] = useState<KnowledgeGraphData | null>(null)
  useEffect(() => {
    if (!USE_REAL_API) return
    let alive = true
    getKnowledgeGraph()
      .then((g) => alive && setRemote(g))
      .catch((e) => console.error('[knowledge-graph] 加载图谱失败', e)) // 失败保留本地种子兜底
    return () => {
      alive = false
    }
  }, [masteryStatus])

  /* 节点类别/掌握度由 mastery 派生：通过→已掌握(0)/100；学习中·待检验→学习中(1)；否则种子
     （仅 mock 模式使用；联调以后端推导为准，不再前端自行着色）*/
  const derived = nodes.map((n) => {
    const kp = kpByGraphNode(n.id)
    const ms = kp ? masteryStatus[kp.id] : undefined
    if (ms === 'passed') return { ...n, category: 0, value: 100 }
    if (ms === 'learning' || ms === 'pending-check') return { ...n, category: 1, value: Math.min(n.value, 60) }
    return n
  })
  const enodes = USE_REAL_API && remote ? remote.nodes : derived
  const elinks = USE_REAL_API && remote ? remote.links : links
  const ecats = USE_REAL_API && remote ? remote.categories : categories
  const statusCounts = ecats.map((c, i) => ({
    name: c.name,
    count: enodes.filter((n) => n.category === i).length,
  }))

  useEffect(() => {
    if (!ref.current) return
    if (!chart.current) chart.current = echarts.init(ref.current)

    const option: echarts.EChartsOption = {
      tooltip: {
        formatter: (p: any) =>
          p.dataType === 'node'
            ? `<b>${p.data.name}</b><br/>状态：${ecats[p.data.category].name}<br/>掌握度：${p.data.value}%`
            : '',
        backgroundColor: withAlpha(t.surface, 0.94),
        borderColor: withAlpha(t.primary, 0.25),
        textStyle: { color: t.ink, fontSize: 12 },
      },
      legend: [{
        data: ecats.map((c) => c.name),
        bottom: 8,
        textStyle: { color: t.inkSoft, fontSize: 12 },
        itemWidth: 12,
        itemHeight: 12,
      }],
      animationDuration: 1200,
      animationEasingUpdate: 'quinticInOut',
      series: [{
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        categories: ecats.map((c, i) => ({ name: c.name, itemStyle: { color: colors[i] } })),
        data: enodes.map((n) => ({
          id: n.id,
          name: n.name,
          category: n.category,
          value: n.value,
          symbolSize: 26 + n.value * 0.32,
          /* 标签移到节点下方、落在浅色画布上的深色 --ink 文字，不受节点颜色影响 */
          label: { show: true, position: 'bottom', distance: 6, color: t.ink, fontSize: 11, fontWeight: 600 },
          itemStyle: {
            shadowBlur: 14,
            shadowColor: withAlpha(colors[n.category], 0.4),
            borderColor: t.surface,
            borderWidth: 1.5,
          },
        })),
        links: elinks.map((l) => ({
          source: l.source,
          target: l.target,
          lineStyle: { color: withAlpha(t.inkSoft, 0.4), width: 1.4, curveness: 0.12 },
        })),
        lineStyle: { opacity: 0.6 },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3, color: withAlpha(t.primary, 0.7) },
          label: { fontWeight: 700 },
        },
        force: { repulsion: 320, edgeLength: 110, gravity: 0.08 },
        labelLayout: { hideOverlap: true },
      }],
    }
    chart.current.setOption(option)

    /* 节点点击：核心 6 节点（注册表命中，ml/nn/dl/cnn/transformer/finetune）→ 经
       resourceNav 通道跳转对应知识点资源页（与学习路径页同款导航）；其余节点 → 轻提示。
       effect 随主题/掌握度重跑，先 off 再 on 防止处理器堆叠 */
    chart.current.off('click')
    chart.current.on('click', (p) => {
      if ((p as { dataType?: string }).dataType !== 'node') return
      const node = p.data as { id: string; name: string }
      const kp = kpByGraphNode(node.id)
      if (kp) {
        setResourceNav(kp.id)
        onNavigate?.('learning-resource')
      } else {
        showToast(`「${node.name}」暂未开通课程，作为领域拓扑参考`)
      }
    })

    const onResize = () => chart.current?.resize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, masteryStatus, remote])

  return (
    <div className="kg-page">
      {/* 统一标题区：锚条 + 高亮 + Beta + 掌握度类别徽章（带主题色点）*/}
      <PageHeader
        title="知识图谱"
        highlight="知识图谱"
        tag="Beta"
        subtitle="AI 领域知识拓扑 · 按你的掌握度着色 · 可拖拽 / 缩放"
        badges={statusCounts.map((s, i) => ({ label: s.name, value: s.count, dot: colors[i] }))}
      />

      <RevealGroup>
        <RevealItem className="kg-card">
          <div className="kg-graph" ref={ref} />
          <p className="kg-hint">提示：连线表示「前置 → 进阶」依赖关系；悬停节点查看掌握度，拖拽可调整布局。</p>
        </RevealItem>
      </RevealGroup>

      {/* 非核心节点点击轻提示（复用 AdminKB toast 形态与样式） */}
      <AnimatePresence>
        {toast && (
          <motion.div
            className="akb__toast glass-card"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
