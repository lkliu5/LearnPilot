import { useState, useEffect, useRef, useMemo } from 'react'
import { motion } from 'framer-motion'
import RadarChart from '../components/charts/RadarChart'
import LearningPathCard from '../components/LearningPathCard'
import AgentStatusCard from '../components/AgentStatusCard'
import CountUp from '../components/CountUp'
import BlurText from '@/components/BlurText/BlurText'
import GuideCard from '../components/GuideCard'
import { useScrollReveal } from '../hooks/useScrollReveal'
import { useMastery } from '../store/mastery'
import { useJourney } from '../store/journey'
import { usePortrait } from '../store/portrait'
import { KNOWLEDGE_POINTS } from '../data/knowledgePoints'
import { USE_REAL_API } from '../services/api'
import { getDashboardOverview, synthesizeOverview, type DashboardOverview } from '../services/dashboard'
import type { PageType } from '../App'
import './Dashboard.css'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0 }
}

export default function Dashboard({ onNavigate }: { onNavigate?: (page: PageType) => void }) {
  const rootRef = useRef<HTMLDivElement>(null)
  useScrollReveal(rootRef)

  /* 实时时钟 */
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const hours = time.getHours().toString().padStart(2, '0')
  const minutes = time.getMinutes().toString().padStart(2, '0')
  const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const dateStr = `${time.getFullYear()}年${time.getMonth() + 1}月${time.getDate()}日 ${weekDays[time.getDay()]}`

  /* 学情概览随掌握度同步：每通过一个核心知识点，图谱覆盖率 / 已学资源真实增长 */
  const masteryStatus = useMastery((s) => s.status)
  const masteredCore = KNOWLEDGE_POINTS.filter((k) => masteryStatus[k.id] === 'passed').length

  /* 门控：学情概览数据须来自「真实诊断结果 / 画像」，无则视为未诊断（问题 4）。
     Mock 模式以本地画像快照为准（确认画像后写入）；联调以后端 journey.hasDiagnosed 为准。 */
  const journeyHasDiagnosed = useJourney((s) => s.hasDiagnosed)
  const portraitDims = usePortrait((s) => s.dims)
  const diagnosed = journeyHasDiagnosed && (USE_REAL_API || portraitDims.length > 0)

  /* 联调数据源：GET /dashboard/overview（接口 29）聚合综合分/强弱项/雷达/对标摘要；
     未诊断不请求。掌握度变化时重取，保持"随掌握度联动"行为 */
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  useEffect(() => {
    if (!USE_REAL_API || !diagnosed) return
    let alive = true
    getDashboardOverview()
      .then((d) => alive && setOverview(d))
      .catch((e) => console.error('[dashboard] 加载学情概览失败', e)) // 失败回退本地画像合成
    return () => {
      alive = false
    }
  }, [masteryStatus, diagnosed])

  /* 由真实画像合成的概览（综合分/水平/雷达/强弱项）——确认弹窗同源，口径一致 */
  const synth = useMemo(() => synthesizeOverview(portraitDims), [portraitDims])
  const profileData = USE_REAL_API && overview ? overview : synth
  const radarData = USE_REAL_API && overview ? overview.radar : synth.radar

  /* 图谱覆盖率 / 已学资源属「学习活动」指标：随真实 Mastery 增长，刚诊断未做题=0/空，绝不由画像臆造 */
  const knowledgeGraphCoverage =
    USE_REAL_API && overview ? overview.knowledge_graph_coverage : masteredCore / KNOWLEDGE_POINTS.length
  const learnedResources = USE_REAL_API && overview ? overview.learned_resources : masteredCore
  /* 同级对比同属队列统计：仅联调由后端给出，Mock 下无真实样本则不展示该行 */
  const betterThanPct = USE_REAL_API && overview ? overview.comparison.betterThanPct : null

  /* 岗位对标轻量摘要：完整对标在「画像诊断」页，首页只回显结果 + 跳转入口 */
  const journeyTargetJobName = useJourney((s) => s.targetJobName)
  const journeyMatchPct = useJourney((s) => s.matchPct)
  const hasDiagnosed = USE_REAL_API && overview ? overview.targetSummary.hasDiagnosed : journeyHasDiagnosed
  const targetJobName = USE_REAL_API && overview ? overview.targetSummary.targetJobName : journeyTargetJobName
  const matchPct = USE_REAL_API && overview ? overview.targetSummary.matchPct : journeyMatchPct

  /* 未诊断：学情概览不展示任何数据，仅留引导态（问题 4）——避免新用户首登即见假数据 */
  if (!diagnosed) {
    return (
      <motion.div
        className="dashboard dashboard--empty"
        ref={rootRef}
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <motion.div variants={itemVariants}>
          <GuideCard onNavigate={onNavigate} />
        </motion.div>

        <motion.div className="dashboard__empty" variants={itemVariants}>
          <div className="dashboard__empty-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 8v4" />
              <path d="M12 16h.01" />
            </svg>
          </div>
          <h2 className="dashboard__empty-title">学情概览尚未生成</h2>
          <p className="dashboard__empty-desc">
            综合评分、知识雷达、优势与盲区都来自你的<strong>真实学习画像</strong>。
            先完成一次画像诊断，AI 才能据此生成你的专属学情概览。
          </p>
          <button className="dashboard__empty-cta" type="button" onClick={() => onNavigate?.('profile')}>
            先完成画像诊断 →
          </button>
        </motion.div>
      </motion.div>
    )
  }

  return (
    <motion.div
      className="dashboard"
      ref={rootRef}
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* 首屏状态化引导：唯一明确的下一步 */}
      <motion.div variants={itemVariants}>
        <GuideCard onNavigate={onNavigate} />
      </motion.div>

      {/* 岗位对标轻量摘要：完整对标在画像诊断页，点击跳转 */}
      <motion.button
        type="button"
        className="dashboard__target-summary"
        variants={itemVariants}
        onClick={() => onNavigate?.('profile')}
      >
        <span className="dashboard__target-summary-icon">🎯</span>
        {hasDiagnosed && targetJobName ? (
          <span className="dashboard__target-summary-text">
            目标岗位：<strong>{targetJobName}</strong>
            <span className="dashboard__target-summary-sep">·</span>
            对标进度 <strong>{matchPct ?? 0}%</strong>
          </span>
        ) : (
          <span className="dashboard__target-summary-text">
            尚未进行岗位对标 · <strong>开始画像诊断</strong>，看你与目标岗位的能力差距
          </span>
        )}
        <span className="dashboard__target-summary-cta">查看完整对标 →</span>
      </motion.button>

      {/* V3.0 三栏式顶部信息栏 */}
      <motion.div className="dashboard__header" variants={itemVariants}>
        {/* 左栏：欢迎语 */}
        <div className="dashboard__header-card dashboard__header-card--welcome">
          <BlurText className="dashboard__greeting" text="你好，学习者_001 👋" animateBy="chars" delay={55} stepDuration={0.38} />
          <p className="dashboard__subtitle">
            您的AI学习旅程已开启，当前处于 <strong>{profileData.overall_level}</strong> 水平
          </p>
          {betterThanPct !== null && (
            <div className="dashboard__score-meta">
              <span className="dashboard__score-comparison">超过了 {betterThanPct}% 的同级学习者</span>
              <svg className="dashboard__score-trend" width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M7 17L12 12L17 17" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M7 12L12 7L17 12" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          )}
        </div>

        {/* 中栏：立体发光仪表盘 */}
        <div className="dashboard__header-card dashboard__header-card--gauge">
          <div className="dashboard__gauge">
            <div className="dashboard__gauge-outer-glow" />
            <svg viewBox="0 0 200 200" className="dashboard__gauge-svg">
              <defs>
                <linearGradient id="gauge-main" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: 'var(--primary)' }} />
                  <stop offset="100%" style={{ stopColor: 'var(--primary-d)' }} />
                </linearGradient>
                <linearGradient id="gauge-glow" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: 'var(--primary)', stopOpacity: 0.6 }} />
                  <stop offset="100%" style={{ stopColor: 'var(--primary-d)', stopOpacity: 0.3 }} />
                </linearGradient>
                <linearGradient id="gauge-highlight" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="rgba(255,255,255,0.4)" />
                  <stop offset="50%" stopColor="rgba(255,255,255,0)" />
                </linearGradient>
                <filter id="gauge-outer-glow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
                  <feColorMatrix in="blur" type="matrix"
                    values="0 0 0 0 0.23  0 0 0 0 0.51  0 0 0 0 0.97  0 0 0 0.4 0" />
                </filter>
              </defs>
              <circle cx="100" cy="100" r="82" fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth="12" />
              <circle cx="100" cy="100" r="82" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="12" strokeDasharray="4 8" />
              <circle cx="100" cy="100" r="82" fill="none" stroke="url(#gauge-glow)" strokeWidth="16" strokeLinecap="round"
                strokeDasharray={`${(profileData.overall_score / 100) * 515} 515`} filter="url(#gauge-outer-glow)"
                style={{ transition: 'stroke-dasharray 1.5s cubic-bezier(0.4, 0, 0.2, 1)' }} />
              <circle cx="100" cy="100" r="82" fill="none" stroke="url(#gauge-main)" strokeWidth="12" strokeLinecap="round"
                strokeDasharray={`${(profileData.overall_score / 100) * 515} 515`} transform="rotate(-90 100 100)"
                style={{ transition: 'stroke-dasharray 1.5s cubic-bezier(0.4, 0, 0.2, 1)' }} />
              <circle cx="100" cy="100" r="82" fill="none" stroke="url(#gauge-highlight)" strokeWidth="12" strokeLinecap="round"
                strokeDasharray={`${(profileData.overall_score / 100) * 515} 515`} transform="rotate(-90 100 100)" opacity="0.5"
                style={{ transition: 'stroke-dasharray 1.5s cubic-bezier(0.4, 0, 0.2, 1)' }} />
              <circle cx="100" cy="18" r="5" style={{ fill: 'var(--primary)' }} filter="url(#gauge-outer-glow)" opacity="0.9" />
              <circle cx="100" cy="18" r="3" fill="#ffffff" opacity="0.8" />
            </svg>
            <div className="dashboard__gauge-center">
              <CountUp className="dashboard__gauge-value" value={profileData.overall_score} decimals={1} duration={1.6} />
              <span className="dashboard__gauge-label">综合能力评分</span>
            </div>
          </div>
        </div>

        {/* 右栏：环境上下文卡片 */}
        <div className="dashboard__header-card dashboard__header-card--context">
          {/* 时钟 */}
          <div className="context-clock">
            <span className="context-clock__time">{hours}:{minutes}</span>
            <span className="context-clock__date">{dateStr} · 上海</span>
          </div>
          {/* 天气 */}
          <div className="context-weather">
            <div className="context-weather__icon">
              <svg viewBox="0 0 48 48" fill="none">
                <defs>
                  <linearGradient id="cloud-grad" x1="0" y1="0" x2="48" y2="48">
                    <stop offset="0%" stopColor="#60a5fa" />
                    <stop offset="100%" stopColor="#a78bfa" />
                  </linearGradient>
                  <filter id="cloud-glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
                    <feColorMatrix in="blur" type="matrix"
                      values="0 0 0 0 0.37  0 0 0 0 0.65  0 0 0 0 0.98  0 0 0 0.35 0" />
                  </filter>
                </defs>
                <circle cx="30" cy="16" r="8" fill="#fbbf24" opacity="0.9" />
                <circle cx="30" cy="16" r="8" fill="none" stroke="#fbbf24" strokeWidth="1" opacity="0.4" />
                <path d="M14 32c-4.4 0-8-3.6-8-8 0-3.7 2.5-6.8 6-7.7C13.3 12.5 18.2 9 24 9c7.2 0 13 5.8 13 13 0 .3 0 .7-.1 1h.1c3.3 0 6 2.7 6 6s-2.7 6-6 6H14z"
                  fill="url(#cloud-grad)" filter="url(#cloud-glow)" opacity="0.85" />
              </svg>
            </div>
            <div className="context-weather__info">
              <span className="context-weather__temp">22°C</span>
              <span className="context-weather__desc">晴</span>
            </div>
          </div>
          {/* 学习贴士 */}
          <p className="context-tip">今天天气晴朗，去图书馆刷题效率更高哦！📚</p>
        </div>
      </motion.div>

      {/* V3.0 Stats Grid - 3D Icons + Sparklines */}
      <motion.div className="dashboard__stats" variants={itemVariants}>
        {/* 知识图谱覆盖 */}
        <div className="stat-card">
          <div className="stat-card__top">
            <div className="stat-card__icon stat-card__icon--blue">
              <svg viewBox="0 0 24 24" fill="none">
                <defs>
                  <linearGradient id="sc-blue" x1="0" y1="0" x2="24" y2="24">
                    <stop style={{ stopColor: 'var(--primary)' }} /><stop offset="1" style={{ stopColor: 'var(--primary-d)' }} />
                  </linearGradient>
                </defs>
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="url(#sc-blue)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <svg className="stat-card__sparkline" viewBox="0 0 80 30" preserveAspectRatio="none">
              <defs>
                <linearGradient id="spark-blue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0.22 }} />
                  <stop offset="100%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0 }} />
                </linearGradient>
              </defs>
              <path d="M0 25 Q10 20, 16 18 T32 14 T48 16 T64 8 T80 5" fill="none" style={{ stroke: 'var(--ink-soft)' }} strokeWidth="2" strokeLinecap="round" />
              <path d="M0 25 Q10 20, 16 18 T32 14 T48 16 T64 8 T80 5 L80 30 L0 30Z" fill="url(#spark-blue)" />
            </svg>
          </div>
          <div className="stat-card__content">
            <CountUp className="stat-card__value" value={Math.round(knowledgeGraphCoverage * 100)} suffix="%" />
            <span className="stat-card__label">知识图谱覆盖</span>
          </div>
        </div>

        {/* 优势知识点 */}
        <div className="stat-card">
          <div className="stat-card__top">
            <div className="stat-card__icon stat-card__icon--green">
              <svg viewBox="0 0 24 24" fill="none">
                <defs>
                  <linearGradient id="sc-green" x1="0" y1="0" x2="24" y2="24">
                    <stop stopColor="#34d399" /><stop offset="1" stopColor="#059669" />
                  </linearGradient>
                </defs>
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="url(#sc-green)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <svg className="stat-card__sparkline" viewBox="0 0 80 30" preserveAspectRatio="none">
              <defs>
                <linearGradient id="spark-green" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0.22 }} />
                  <stop offset="100%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0 }} />
                </linearGradient>
              </defs>
              <path d="M0 22 Q12 18, 20 20 T40 12 T60 15 T80 6" fill="none" style={{ stroke: 'var(--ink-soft)' }} strokeWidth="2" strokeLinecap="round" />
              <path d="M0 22 Q12 18, 20 20 T40 12 T60 15 T80 6 L80 30 L0 30Z" fill="url(#spark-green)" />
            </svg>
          </div>
          <div className="stat-card__content">
            <CountUp className="stat-card__value" value={profileData.strong_topics.length} />
            <span className="stat-card__label">优势知识点</span>
          </div>
        </div>

        {/* 知识盲区 */}
        <div className="stat-card stat-card--warning">
          <div className="stat-card__top">
            <div className="stat-card__icon stat-card__icon--amber">
              <svg viewBox="0 0 24 24" fill="none">
                <defs>
                  <linearGradient id="sc-amber" x1="0" y1="0" x2="24" y2="24">
                    <stop style={{ stopColor: 'var(--accent)' }} /><stop offset="1" style={{ stopColor: 'var(--accent)' }} />
                  </linearGradient>
                </defs>
                <circle cx="12" cy="12" r="10" stroke="url(#sc-amber)" strokeWidth="1.8" />
                <line x1="12" y1="8" x2="12" y2="12" stroke="url(#sc-amber)" strokeWidth="2" strokeLinecap="round" />
                <circle cx="12" cy="16" r="1" fill="url(#sc-amber)" />
              </svg>
            </div>
            <svg className="stat-card__sparkline" viewBox="0 0 80 30" preserveAspectRatio="none">
              <defs>
                <linearGradient id="spark-amber" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0.22 }} />
                  <stop offset="100%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0 }} />
                </linearGradient>
              </defs>
              <path d="M0 15 Q10 20, 20 14 T40 18 T60 10 T80 12" fill="none" style={{ stroke: 'var(--ink-soft)' }} strokeWidth="2" strokeLinecap="round" />
              <path d="M0 15 Q10 20, 20 14 T40 18 T60 10 T80 12 L80 30 L0 30Z" fill="url(#spark-amber)" />
            </svg>
          </div>
          <div className="stat-card__content">
            <CountUp className="stat-card__value" value={profileData.weak_topics.length} />
            <span className="stat-card__label">知识盲区</span>
          </div>
        </div>

        {/* 已学资源 */}
        <div className="stat-card">
          <div className="stat-card__top">
            <div className="stat-card__icon stat-card__icon--purple">
              <svg viewBox="0 0 24 24" fill="none">
                <defs>
                  <linearGradient id="sc-purple" x1="0" y1="0" x2="24" y2="24">
                    <stop style={{ stopColor: 'var(--primary-d)' }} /><stop offset="1" style={{ stopColor: 'var(--primary-d)' }} />
                  </linearGradient>
                </defs>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="url(#sc-purple)" strokeWidth="1.8" />
                <polyline points="14 2 14 8 20 8" stroke="url(#sc-purple)" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </div>
            <svg className="stat-card__sparkline" viewBox="0 0 80 30" preserveAspectRatio="none">
              <defs>
                <linearGradient id="spark-purple" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0.22 }} />
                  <stop offset="100%" style={{ stopColor: 'var(--ink-soft)', stopOpacity: 0 }} />
                </linearGradient>
              </defs>
              <path d="M0 20 Q15 15, 25 18 T50 10 T80 4" fill="none" style={{ stroke: 'var(--ink-soft)' }} strokeWidth="2" strokeLinecap="round" />
              <path d="M0 20 Q15 15, 25 18 T50 10 T80 4 L80 30 L0 30Z" fill="url(#spark-purple)" />
            </svg>
          </div>
          <div className="stat-card__content">
            <CountUp className="stat-card__value" value={learnedResources} />
            <span className="stat-card__label">已学资源</span>
          </div>
        </div>
      </motion.div>

      {/* Main Content Grid */}
      <div className="dashboard__grid">
        {/* Radar Chart */}
        <motion.div className="dashboard__card dashboard__card--chart" variants={itemVariants}>
          <div className="card-header">
            <h3>知识掌握雷达图</h3>
            <span className="card-badge">实时更新</span>
          </div>
          <div className="card-content">
            <RadarChart data={radarData} />
          </div>
        </motion.div>

        {/* V3.0: 能力分析 + 3D 玻璃装置 */}
        <motion.div className="dashboard__card dashboard__card--ability" variants={itemVariants}>
          <div className="card-header">
            <h3>能力分析</h3>
          </div>
          <div className="card-content">
            <div className="ability-analysis">
              <div className="ability-analysis__tags">
                <div className="ability-analysis__section">
                  <span className="ability-analysis__label ability-analysis__label--success">
                    <span className="ability-analysis__dot ability-analysis__dot--success" />
                    优势领域
                  </span>
                  <div className="ability-analysis__tag-group">
                    {profileData.strong_topics.map((topic, i) => (
                      <div key={i} className="ability-item">
                        <div className="ability-item__head">
                          <span className="ability-item__name">{topic.name}</span>
                          <span className="ability-item__pct">{topic.mastery}%</span>
                        </div>
                        <div className="ability-meter">
                          <span className="ability-meter__fill ability-meter__fill--strong" style={{ width: `${topic.mastery}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="ability-analysis__section">
                  <span className="ability-analysis__label ability-analysis__label--warning">
                    <span className="ability-analysis__dot ability-analysis__dot--warning" />
                    待提升领域
                  </span>
                  <div className="ability-analysis__tag-group">
                    {profileData.weak_topics.map((topic, i) => (
                      <div key={i} className="ability-item">
                        <div className="ability-item__head">
                          <span className="ability-item__name">{topic.name}</span>
                          <span className="ability-item__pct">{topic.mastery}%</span>
                        </div>
                        <div className="ability-meter">
                          <span className="ability-meter__fill ability-meter__fill--weak" style={{ width: `${topic.mastery}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 行动建议：撑满卡片下方，给出下一步 + 主色 CTA */}
              <div className="ability-action">
                <p className="ability-action__tip">
                  <span className="ability-action__tip-icon">✦</span>
                  {profileData.weak_topics.length ? (
                    <>建议优先攻克 <strong>{profileData.weak_topics[0].name}</strong>，预计 3 节课可提升</>
                  ) : (
                    <>各维度较均衡，建议按学习路径稳步推进</>
                  )}
                </p>
                <button className="ability-action__cta" type="button">生成针对性练习 →</button>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

        {/* 推荐学习路径 + 推荐动态 双栏 */}
        <div className="dashboard__dual" data-reveal>
          {/* 左栏 2/3：学习路径 */}
          <motion.div className="dashboard__card dashboard__dual__main" variants={itemVariants}>
            <div className="card-header">
              <h3>推荐学习路径</h3>
              <button className="card-action">查看全部 →</button>
            </div>
            <div className="card-content">
              <div className="learning-path-preview">
                <LearningPathCard
                  sequence={1}
                  topic="神经网络基础"
                  difficulty="初级"
                  status="completed"
                  progress={100}
                />
                <LearningPathCard
                  sequence={2}
                  topic="注意力机制原理"
                  difficulty="中级"
                  status="in_progress"
                  progress={45}
                />
                <LearningPathCard
                  sequence={3}
                  topic="Transformer架构详解"
                  difficulty="高级"
                  status="pending"
                  progress={0}
                />
              </div>
            </div>
          </motion.div>

          {/* 右栏 1/3：推荐动态 */}
          <motion.div className="dashboard__card dashboard__dual__side" variants={itemVariants}>
            <div className="card-header">
              <h3>推荐动态</h3>
              <span className="card-badge">AI</span>
            </div>
            <div className="card-content">
              <div className="recommend-panel">
                <div className="recommend-panel__icon">
                  <svg viewBox="0 0 24 24" fill="none">
                    <defs>
                      <linearGradient id="rec-icon" x1="0" y1="0" x2="24" y2="24">
                        <stop style={{ stopColor: 'var(--primary)' }} /><stop offset="1" style={{ stopColor: 'var(--primary-d)' }} />
                      </linearGradient>
                    </defs>
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="url(#rec-icon)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <p className="recommend-panel__text">
                  基于你的画像诊断，建议加强 <strong>'神经网络基础'</strong>、<strong>'大模型微调'</strong> 等核心组件
                </p>
                <div className="recommend-panel__list">
                  <div className="recommend-panel__item">
                    <span className="recommend-panel__dot recommend-panel__dot--blue" />
                    <span className="recommend-panel__item-name">注意力机制原理</span>
                    <span className="recommend-panel__item-progress">45%</span>
                  </div>
                  <div className="recommend-panel__item">
                    <span className="recommend-panel__dot recommend-panel__dot--purple" />
                    <span className="recommend-panel__item-name">大模型微调前沿</span>
                    <span className="recommend-panel__item-progress">20%</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Agent 状态 + 互动面板 双栏 */}
        <div className="dashboard__dual" data-reveal>
          {/* 左栏 2/3：Agent 状态 */}
          <motion.div className="dashboard__card dashboard__dual__main" variants={itemVariants}>
            <div className="card-header">
              <h3>Agent状态</h3>
              <span className="card-badge">3 Active</span>
            </div>
            <div className="card-content">
              <div className="agent-list">
                <AgentStatusCard
                  name="学情诊断Agent"
                  status="success"
                  lastAction="画像生成完成"
                />
                <AgentStatusCard
                  name="领域知识生成Agent"
                  status="running"
                  lastAction="正在生成学习资源..."
                />
                <AgentStatusCard
                  name="内容审核校验Agent"
                  status="idle"
                  lastAction="等待校验任务"
                />
              </div>
            </div>
          </motion.div>

          {/* 右栏 1/3：互动面板 */}
          <motion.div className="dashboard__card dashboard__dual__side" variants={itemVariants}>
            <div className="card-header">
              <h3>互动面板</h3>
            </div>
            <div className="card-content">
              <div className="interaction-panel">
                <div className="interaction-panel__item">
                  <div className="interaction-panel__avatar interaction-panel__avatar--green">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 4-7 8-7s8 3 8 7" />
                    </svg>
                  </div>
                  <div className="interaction-panel__body">
                    <span className="interaction-panel__agent">学情诊断Agent</span>
                    <p className="interaction-panel__msg">我已完成你的诊断，点击复习巩固。</p>
                    <button className="interaction-panel__btn">Review Now</button>
                  </div>
                </div>
                <div className="interaction-panel__divider" />
                <div className="interaction-panel__item">
                  <div className="interaction-panel__avatar interaction-panel__avatar--blue">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 12l2 2 4-4" /><circle cx="12" cy="12" r="10" />
                    </svg>
                  </div>
                  <div className="interaction-panel__body">
                    <span className="interaction-panel__agent">内容审核校验Agent</span>
                    <p className="interaction-panel__msg">校验通过，幻觉率 2.1%。</p>
                    <button className="interaction-panel__btn">查看报告</button>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
    </motion.div>
  )
}