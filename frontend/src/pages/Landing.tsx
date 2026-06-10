import { useRef, useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'
import ParticleVortex from '../components/ParticleVortex'
import GhostCursor from '@/components/GhostCursor/GhostCursor'
import BlurText from '@/components/BlurText/BlurText'
import './Landing.css'

gsap.registerPlugin(useGSAP, ScrollTrigger)

interface LandingProps {
  onEnter: () => void
}

/** 读取深色 Hero 主题色（青绿/暖金/浅点），并随右下角主题切换器实时更新 */
function useHeroColors() {
  const read = () => {
    const cs = typeof document !== 'undefined' ? getComputedStyle(document.documentElement) : null
    return {
      primary: cs?.getPropertyValue('--hero-primary').trim() || '#6FB3A6',
      accent: cs?.getPropertyValue('--hero-accent').trim() || '#E0A458',
      light: cs?.getPropertyValue('--hero-light').trim() || '#CBE3DC',
      themeKey: document.documentElement.getAttribute('data-theme') === 'ink' ? 'ink' : 'sage',
    }
  }
  const [hero, setHero] = useState(read)
  useEffect(() => {
    const el = document.documentElement
    const obs = new MutationObserver(() => setHero(read()))
    obs.observe(el, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])
  return hero
}

/* 滚动钉合聚光的四大能力（talizen 式巨字序列）*/
const capabilities = [
  { word: '学情诊断', en: 'DIAGNOSIS', desc: '对话式交互精准识别知识盲区，构建动态学情画像' },
  { word: '资源生成', en: 'GENERATION', desc: '基于画像生成适配难度的定制讲义、实操与分阶测试' },
  { word: '多智能体协同', en: 'MULTI-AGENT', desc: 'LangGraph 编排诊断 / 生成 / 审核 Agent 协同决策' },
  { word: '防幻觉校验', en: 'ANTI-HALLUCINATION', desc: 'RAG 检索增强 + 多 Agent 交叉校验，幻觉率压至 <5%' },
]

export default function Landing({ onEnter }: LandingProps) {
  const root = useRef<HTMLDivElement>(null)
  const hero = useHeroColors()

  useGSAP(() => {
    const sections = gsap.utils.toArray<HTMLElement>('.landing-cap')

    sections.forEach((sec) => {
      const word = sec.querySelector('.landing-cap__inner')
      // 进入中心：淡入 + 放大 + 去模糊（scrub 跟随滚动）
      gsap.fromTo(
        word,
        { opacity: 0, scale: 0.8, filter: 'blur(14px)', y: 60 },
        {
          opacity: 1, scale: 1, filter: 'blur(0px)', y: 0, ease: 'power2.out',
          scrollTrigger: { trigger: sec, start: 'top 78%', end: 'top 34%', scrub: 0.6 },
        }
      )
      // 离开中心：压暗 + 上移虚化，形成"聚光让位"
      gsap.to(word, {
        opacity: 0.12, scale: 1.06, filter: 'blur(10px)', y: -50, ease: 'power2.in',
        scrollTrigger: { trigger: sec, start: 'bottom 60%', end: 'bottom 18%', scrub: 0.6 },
      })
    })

    // 字体/布局就绪后刷新测量，避免错位
    const refresh = () => ScrollTrigger.refresh()
    if (document.fonts) document.fonts.ready.then(refresh)
    return () => ScrollTrigger.getAll().forEach((t) => t.kill())
  }, { scope: root })

  return (
    <div className="landing" ref={root}>
      {/* 幽灵光标拖尾（固定全屏覆盖层，pointer-events:none 不拦截操作）*/}
      <div key={`cursor-${hero.themeKey}`} style={{ position: 'fixed', inset: 0, zIndex: 9, pointerEvents: 'none' }}>
        <GhostCursor
          color={hero.primary}
          trailLength={26}
          inertia={0.42}
          brightness={0.85}
          bloomStrength={0.07}
          bloomRadius={0.5}
          maxDevicePixelRatio={1}
          mixBlendMode="screen"
          zIndex={9}
        />
      </div>

      {/* 背景（固定层：贯穿整页，滚动时持续）*/}
      <div className="landing__bg">
        <div className="landing__grid" />
        <div className="landing__orb landing__orb--1" />
        <div className="landing__orb landing__orb--2" />
        {/* three.js 粒子漩涡 - 全页持续背景（颜色随主题，切换时按 key 重建上色）*/}
        <ParticleVortex
          key={`particles-${hero.themeKey}`}
          className="landing__particles"
          primary={hero.primary}
          accent={hero.accent}
          light={hero.light}
        />
        {/* 全局可读性遮罩：中心竖带轻微压暗，保证标题/巨字清晰 */}
        <div className="landing__scrim" />
      </div>

      {/* 顶栏 */}
      <header className="landing__nav">
        <div className="landing__brand">
          <span className="landing__brand-dot" />
          智学中枢
        </div>
        <button className="landing__nav-cta" onClick={onEnter}>进入系统</button>
      </header>

      {/* Hero */}
      <section className="landing__hero">
        {/* 主标题：BlurText 逐字揭示（两行），保留选择性蓝紫渐变（见 CSS nth-child）*/}
        <div className="landing__headline">
          <BlurText className="landing__hl landing__hl-1" text="诊断学情。" animateBy="chars" delay={70} stepDuration={0.4} />
          <BlurText className="landing__hl landing__hl-2" text="生成每一课。" animateBy="chars" delay={70} stepDuration={0.4} />
        </div>
        <BlurText
          className="landing__sub"
          text="多智能体协同 · 个性化学习路径 · 从画像到资源，分钟级生成。"
          animateBy="words"
          delay={110}
          stepDuration={0.4}
        />
        <motion.div
          className="landing__cta-row"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45, duration: 0.6 }}
        >
          <button className="landing__cta landing__cta--primary" onClick={onEnter}>
            进入系统
          </button>
          <a className="landing__cta landing__cta--ghost" href="#explore">了解能力 ↓</a>
        </motion.div>

        <div className="landing__scroll-cue" id="explore">
          <span>向下滚动 · 探索系统能力</span>
          <div className="landing__scroll-line" />
        </div>
      </section>

      {/* 滚动巨字聚光序列（逐屏点亮）*/}
      <div className="landing__caps">
        {capabilities.map((c, i) => (
          <section className="landing-cap" key={c.word}>
            <div className="landing-cap__inner">
              <div className="landing-cap__glow" />
              <span className="landing-cap__en">{String(i + 1).padStart(2, '0')} · {c.en}</span>
              <h2 className="landing-cap__word">{c.word}</h2>
              <p className="landing-cap__desc">{c.desc}</p>
            </div>
          </section>
        ))}
      </div>

      {/* 结尾 CTA */}
      <section className="landing__final">
        {/* BlurText：主要标题模糊揭示（按字逐个进入视口时触发）*/}
        <BlurText
          text="准备好开启个性化学习了吗？"
          className="landing__final-title"
          animateBy="chars"
          direction="top"
          delay={80}
          stepDuration={0.4}
        />
        <motion.button
          className="landing__cta landing__cta--primary landing__cta--lg"
          onClick={onEnter}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.15, duration: 0.6 }}
        >
          立即进入系统
        </motion.button>
      </section>
    </div>
  )
}
