import React from 'react'
import { Composition } from 'remotion'
import { DemoVideo, type DemoVideoProps } from './DemoVideo'

const defaultProps: DemoVideoProps = {
  scenes: [
    {
      id: 'placeholder',
      image: 'screens/01-welcome.png',
      audio: 'audio/01-welcome.mp3',
      title: '智学中枢',
      chapter: '演示视频',
      narration: '智学中枢',
      durationInFrames: 150,
      focus: [[50, 50]],
    },
  ],
}

export const RemotionRoot: React.FC = () => (
  <Composition
    id="ZhixueDemo"
    component={DemoVideo}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={defaultProps}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.max(
        1,
        (props as DemoVideoProps).scenes.reduce((sum, scene) => sum + scene.durationInFrames, 0),
      ),
    })}
  />
)

