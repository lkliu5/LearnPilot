import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion'

export const VIDEO_FPS = 30
export const VIDEO_W = 1280
export const VIDEO_H = 720
export const VIDEO_DURATION = 900 // 30s

/* 各场景对应的旁白脚本（供 TTS 朗读 + 字幕，时间与 Sequence 对齐）*/
export const NARRATION = [
  { from: 0, text: '欢迎学习神经网络基础。本视频由领域知识生成智能体为你定制。' },
  { from: 90, text: '一个神经元完成三步运算：加权求和、加上偏置、再经过激活函数输出。' },
  { from: 300, text: '前向传播时，输入与权重相乘求和，加偏置得到 z，再用 ReLU 激活得到输出。' },
  { from: 540, text: '常见激活函数有 ReLU、Sigmoid 和 Tanh，其中 ReLU 计算快、最常用。' },
  { from: 720, text: '神经元、前向传播、激活、反向传播更新，构成了神经网络学习的完整闭环。' },
]

const C = {
  bg1: '#0a1024',
  bg2: '#111a3a',
  blue: '#60a5fa',
  purple: '#a78bfa',
  green: '#34d399',
  amber: '#fbbf24',
  text: '#f1f5f9',
  sub: '#94a3b8',
}

const fade = (frame: number, inEnd: number, outStart: number, outEnd: number) =>
  interpolate(frame, [0, inEnd, outStart, outEnd], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })

/* 场景 1：封面 */
const TitleScene = () => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const s = spring({ frame, fps, config: { damping: 14 } })
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: fade(frame, 15, 70, 90) }}>
      <div style={{ transform: `scale(${0.8 + s * 0.2})`, textAlign: 'center' }}>
        <div style={{ fontSize: 28, color: C.blue, letterSpacing: 6, marginBottom: 16 }}>AI 讲解视频</div>
        <div style={{ fontSize: 84, fontWeight: 800, color: C.text }}>神经网络基础</div>
        <div style={{ fontSize: 24, color: C.sub, marginTop: 20 }}>领域知识生成智能体 · 难度：初级</div>
      </div>
    </AbsoluteFill>
  )
}

/* 场景 2：神经元三步 */
const steps = [
  { label: '① 加权求和', expr: 'Σ wᵢ·xᵢ', color: C.blue },
  { label: '② 加上偏置', expr: '+ b', color: C.purple },
  { label: '③ 激活函数', expr: 'ReLU(z)', color: C.green },
]
const NeuronScene = () => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 36 }}>
      <div style={{ fontSize: 44, fontWeight: 700, color: C.text, marginBottom: 10 }}>神经元的三步运算</div>
      <div style={{ display: 'flex', gap: 28 }}>
        {steps.map((st, i) => {
          const s = spring({ frame: frame - i * 18, fps, config: { damping: 13 } })
          return (
            <div
              key={st.label}
              style={{
                width: 280, padding: '32px 24px', borderRadius: 20,
                background: 'rgba(255,255,255,0.05)', border: `1.5px solid ${st.color}55`,
                boxShadow: `0 0 40px ${st.color}22`,
                opacity: s, transform: `translateY(${(1 - s) * 40}px)`, textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 26, color: st.color, fontWeight: 700, marginBottom: 14 }}>{st.label}</div>
              <div style={{ fontSize: 40, color: C.text, fontFamily: 'monospace' }}>{st.expr}</div>
            </div>
          )
        })}
      </div>
    </AbsoluteFill>
  )
}

/* 场景 3：前向传播数值流动 */
const ForwardScene = () => {
  const frame = useCurrentFrame()
  const prog = interpolate(frame, [0, 200], [0, 1], { extrapolateRight: 'clamp' })
  const nodes = [
    { label: 'x·w', sub: '加权求和', v: '0.78', at: 0.15 },
    { label: 'z', sub: '+ 偏置 0.1', v: '0.88', at: 0.45 },
    { label: 'a', sub: 'ReLU 输出', v: '0.88', at: 0.78 },
  ]
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 50 }}>
      <div style={{ fontSize: 44, fontWeight: 700, color: C.text }}>前向传播</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
        {nodes.map((n, i) => {
          const active = prog >= n.at
          return (
            <div key={n.label} style={{ display: 'flex', alignItems: 'center' }}>
              <div
                style={{
                  width: 150, height: 150, borderRadius: '50%',
                  background: active ? 'radial-gradient(circle,#2563eb,#1e3a8a)' : 'rgba(255,255,255,0.04)',
                  border: `2px solid ${active ? C.blue : '#33415555'}`,
                  boxShadow: active ? `0 0 50px ${C.blue}88` : 'none',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  transition: 'none',
                }}
              >
                <div style={{ fontSize: 38, fontWeight: 800, color: C.text, fontFamily: 'monospace' }}>{n.label}</div>
                <div style={{ fontSize: 30, color: active ? C.green : C.sub, fontFamily: 'monospace' }}>{active ? n.v : '—'}</div>
                <div style={{ fontSize: 15, color: C.sub, marginTop: 4 }}>{n.sub}</div>
              </div>
              {i < nodes.length - 1 && (
                <div style={{ width: 90, height: 3, background: prog >= nodes[i + 1].at ? C.blue : '#33415566', margin: '0 4px' }} />
              )}
            </div>
          )
        })}
      </div>
    </AbsoluteFill>
  )
}

/* 场景 4：激活函数 */
const acts = [
  { name: 'ReLU', desc: 'max(0, x) · 最常用', color: C.green },
  { name: 'Sigmoid', desc: '压缩到 (0,1)', color: C.blue },
  { name: 'Tanh', desc: '范围 (-1,1) · 零均值', color: C.purple },
]
const ActivationScene = () => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 40 }}>
      <div style={{ fontSize: 44, fontWeight: 700, color: C.text }}>常见激活函数</div>
      <div style={{ display: 'flex', gap: 28 }}>
        {acts.map((a, i) => {
          const s = spring({ frame: frame - i * 16, fps, config: { damping: 13 } })
          return (
            <div key={a.name} style={{
              width: 260, padding: 30, borderRadius: 20, textAlign: 'center',
              background: 'rgba(255,255,255,0.05)', border: `1.5px solid ${a.color}55`,
              opacity: s, transform: `scale(${0.85 + s * 0.15})`,
            }}>
              <div style={{ fontSize: 34, fontWeight: 800, color: a.color, marginBottom: 12 }}>{a.name}</div>
              <div style={{ fontSize: 18, color: C.sub }}>{a.desc}</div>
            </div>
          )
        })}
      </div>
    </AbsoluteFill>
  )
}

/* 场景 5：小结闭环 */
const loop = ['神经元', '前向传播', '激活', '反向传播']
const SummaryScene = () => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 36 }}>
      <div style={{ fontSize: 44, fontWeight: 700, color: C.text }}>学习闭环</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        {loop.map((l, i) => {
          const s = spring({ frame: frame - i * 14, fps, config: { damping: 14 } })
          return (
            <div key={l} style={{ display: 'flex', alignItems: 'center', opacity: s }}>
              <div style={{
                padding: '18px 26px', borderRadius: 14, fontSize: 24, fontWeight: 600, color: C.text,
                background: 'linear-gradient(135deg,#2563eb,#7c3aed)', boxShadow: '0 0 30px rgba(37,99,235,0.4)',
              }}>{l}</div>
              {i < loop.length - 1 && <div style={{ fontSize: 32, color: C.sub, margin: '0 10px' }}>→</div>}
            </div>
          )
        })}
      </div>
      <div style={{ fontSize: 22, color: C.sub, marginTop: 20, opacity: fade(frame, 50, 999, 1000) }}>
        下一步建议学习「深度学习原理」
      </div>
    </AbsoluteFill>
  )
}

export const LectureVideo = () => {
  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${C.bg1}, ${C.bg2})`, fontFamily: 'system-ui, sans-serif' }}>
      <Sequence durationInFrames={90}>{<TitleScene />}</Sequence>
      <Sequence from={90} durationInFrames={210}>{<NeuronScene />}</Sequence>
      <Sequence from={300} durationInFrames={240}>{<ForwardScene />}</Sequence>
      <Sequence from={540} durationInFrames={180}>{<ActivationScene />}</Sequence>
      <Sequence from={720} durationInFrames={180}>{<SummaryScene />}</Sequence>
    </AbsoluteFill>
  )
}
