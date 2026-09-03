import React from 'react'
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion'

export type DemoScene = {
  id: string
  image: string
  audio: string
  title: string
  chapter: string
  narration: string
  durationInFrames: number
  focus?: number[][]
}

export type DemoVideoProps = {
  scenes: DemoScene[]
}

const splitCaption = (text: string) => {
  const sentences = text
    .split(/(?<=[。！？；])/)
    .map((s) => s.trim())
    .filter(Boolean)
  const chunks: string[] = []
  for (const sentence of sentences) {
    if (sentence.length <= 30) {
      chunks.push(sentence)
      continue
    }
    const parts = sentence.split(/(?<=[，、：])/)
    let line = ''
    for (const part of parts) {
      if (line && line.length + part.length > 30) {
        chunks.push(line)
        line = part
      } else {
        line += part
      }
    }
    if (line) chunks.push(line)
  }
  return chunks.length ? chunks : [text]
}

const Cursor: React.FC<{ focus?: number[][]; duration: number }> = ({ focus, duration }) => {
  const frame = useCurrentFrame()
  if (!focus?.length) return null
  const start = focus[0]
  const end = focus[1] ?? focus[0]
  const x = interpolate(frame, [0, duration * 0.78], [start[0], end[0]], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  const y = interpolate(frame, [0, duration * 0.78], [start[1], end[1]], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  const clickAt = Math.round(duration * 0.8)
  const pulse = interpolate(Math.abs(frame - clickAt), [0, 10], [1, 0], {
    extrapolateRight: 'clamp',
  })
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: `${x}%`,
          top: `${y}%`,
          width: 24,
          height: 24,
          borderRadius: '50%',
          background: '#fff',
          border: '3px solid #1f4d3c',
          boxShadow: '0 4px 15px rgba(0,0,0,.35)',
          transform: 'translate(-50%,-50%)',
          zIndex: 8,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: `${x}%`,
          top: `${y}%`,
          width: 60 + pulse * 80,
          height: 60 + pulse * 80,
          borderRadius: '50%',
          border: `4px solid rgba(111,166,140,${pulse})`,
          transform: 'translate(-50%,-50%)',
          zIndex: 7,
        }}
      />
    </>
  )
}

const Scene: React.FC<{ scene: DemoScene; index: number; total: number }> = ({
  scene,
  index,
  total,
}) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const duration = scene.durationInFrames
  const enter = spring({ frame, fps, config: { damping: 18, stiffness: 90 } })
  const fadeOut = interpolate(frame, [duration - 18, duration - 1], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  const scale = interpolate(frame, [0, duration], [1.015, 1.075])
  const panX = interpolate(frame, [0, duration], [-9, 9])
  const captions = splitCaption(scene.narration)
  const captionIndex = Math.min(
    captions.length - 1,
    Math.floor((frame / Math.max(1, duration - 12)) * captions.length),
  )

  return (
    <AbsoluteFill
      style={{
        background: 'linear-gradient(150deg,#dfe9e3 0%,#f2efe7 50%,#cadbd2 100%)',
        opacity: fadeOut,
        fontFamily: '"Microsoft YaHei","PingFang SC",system-ui,sans-serif',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 72,
          right: 72,
          top: 58,
          bottom: 130,
          borderRadius: 22,
          overflow: 'hidden',
          background: '#fff',
          boxShadow: '0 26px 75px rgba(29,55,44,.25)',
          transform: `translateY(${(1 - enter) * 30}px)`,
        }}
      >
        <div
          style={{
            height: 56,
            background: 'linear-gradient(#f7f7f7,#ececec)',
            borderBottom: '1px solid #d6d6d6',
            display: 'flex',
            alignItems: 'center',
            padding: '0 22px',
            gap: 11,
            position: 'relative',
            zIndex: 4,
          }}
        >
          {['#ff5f57', '#febc2e', '#28c840'].map((c) => (
            <span key={c} style={{ width: 15, height: 15, borderRadius: '50%', background: c }} />
          ))}
          <div
            style={{
              position: 'absolute',
              left: '28%',
              right: '28%',
              height: 32,
              borderRadius: 9,
              background: '#fff',
              border: '1px solid #d7d7d7',
              color: '#68736e',
              fontSize: 17,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            🔒 localhost:3000
          </div>
        </div>
        <div style={{ position: 'absolute', left: 0, right: 0, top: 56, bottom: 0, overflow: 'hidden' }}>
          <Img
            src={staticFile(scene.image)}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: 'top center',
              transform: `translateX(${panX}px) scale(${scale})`,
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: 30,
              top: 28,
              padding: '11px 17px',
              borderRadius: 12,
              color: '#fff',
              background: 'rgba(30,64,51,.88)',
              boxShadow: '0 8px 24px rgba(0,0,0,.18)',
            }}
          >
            <div style={{ fontSize: 15, opacity: 0.78, letterSpacing: 2 }}>{scene.chapter}</div>
            <div style={{ fontSize: 26, fontWeight: 700, marginTop: 3 }}>{scene.title}</div>
          </div>
          <Cursor focus={scene.focus} duration={duration} />
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 160,
          right: 160,
          bottom: 31,
          minHeight: 66,
          padding: '13px 28px',
          borderRadius: 18,
          background: 'rgba(15,24,21,.90)',
          color: '#fff',
          fontSize: 30,
          lineHeight: 1.35,
          textAlign: 'center',
          boxShadow: '0 10px 35px rgba(0,0,0,.22)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {captions[captionIndex]}
      </div>

      <div
        style={{
          position: 'absolute',
          right: 94,
          top: 76,
          zIndex: 10,
          color: '#315c4b',
          fontSize: 18,
          fontWeight: 700,
          letterSpacing: 1,
        }}
      >
        智学中枢 · {String(index + 1).padStart(2, '0')}/{String(total).padStart(2, '0')}
      </div>
      <Audio src={staticFile(scene.audio)} volume={1} />
    </AbsoluteFill>
  )
}

export const DemoVideo: React.FC<DemoVideoProps> = ({ scenes }) => {
  let from = 0
  return (
    <AbsoluteFill style={{ background: '#dfe9e3' }}>
      {scenes.map((scene, index) => {
        const start = from
        from += scene.durationInFrames
        return (
          <Sequence key={scene.id} from={start} durationInFrames={scene.durationInFrames}>
            <Scene scene={scene} index={index} total={scenes.length} />
          </Sequence>
        )
      })}
    </AbsoluteFill>
  )
}

