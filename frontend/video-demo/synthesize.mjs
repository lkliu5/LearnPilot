import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { scenes } from './scenes.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const audioDir = path.join(here, 'public', 'audio')
mkdirSync(audioDir, { recursive: true })

const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'learner_001', password: '123456', remember: true }),
})
const loginEnvelope = await loginResponse.json()
if (!loginResponse.ok || loginEnvelope.code !== 0) {
  throw new Error(`登录失败：${JSON.stringify(loginEnvelope)}`)
}
const token = loginEnvelope.data.token

const ffprobe = path.resolve(
  here,
  '..',
  'node_modules',
  '@remotion',
  'compositor-win32-x64-msvc',
  'ffprobe.exe',
)
const generated = []

for (let i = 0; i < scenes.length; i += 1) {
  const scene = scenes[i]
  const number = String(i + 1).padStart(2, '0')
  const filename = `${number}-${scene.id}.mp3`
  const output = path.join(audioDir, filename)
  const response = await fetch('http://localhost:8000/api/v1/tts/synthesize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      text: scene.narration,
      voice: 'zh-CN-XiaoxiaoNeural',
      rate: '-12%',
      pitch: '+0Hz',
    }),
  })
  const contentType = response.headers.get('content-type') || ''
  if (!response.ok || !contentType.includes('audio/mpeg')) {
    throw new Error(`第 ${number} 段 TTS 失败：${await response.text()}`)
  }
  writeFileSync(output, Buffer.from(await response.arrayBuffer()))
  const probe = spawnSync(
    ffprobe,
    ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', output],
    { encoding: 'utf8' },
  )
  if (probe.status !== 0) throw new Error(`ffprobe 失败：${probe.stderr}`)
  const seconds = Number.parseFloat(probe.stdout.trim())
  const durationInFrames = Math.ceil((seconds + 0.7) * 30)
  generated.push({
    ...scene,
    audio: `audio/${filename}`,
    durationInFrames,
    audioSeconds: seconds,
  })
  console.log(`[tts] ${number}/${scenes.length} ${scene.title} ${seconds.toFixed(2)}s`)
}

const metadataPath = path.join(here, 'generated-scenes.json')
writeFileSync(metadataPath, JSON.stringify(generated, null, 2), 'utf8')
const total = generated.reduce((sum, scene) => sum + scene.durationInFrames, 0) / 30
console.log(`[tts] 总时长 ${total.toFixed(2)}s，元数据 ${metadataPath}`)

