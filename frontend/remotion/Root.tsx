import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Composition,
  OffthreadVideo,
  Sequence,
  useCurrentFrame,
} from 'remotion';

export interface CaptionCue {
  startFrame: number;
  endFrame: number;
  text: string;
}

export interface SceneClip {
  id: string;
  title: string;
  src: string;
  fromFrame: number;
  durationInFrames: number;
}

export interface ShowcaseProps {
  fps: number;
  width: number;
  height: number;
  totalFrames: number;
  scenes: SceneClip[];
  audioSrc: string;
  captions: CaptionCue[];
}

const DEFAULT_PROPS: ShowcaseProps = {
  fps: 30,
  width: 1920,
  height: 1080,
  totalFrames: 300,
  scenes: [
    {
      id: 'placeholder',
      title: 'placeholder',
      src: '',
      fromFrame: 0,
      durationInFrames: 300,
    },
  ],
  audioSrc: '',
  captions: [],
};

const CaptionLayer: React.FC<{captions: CaptionCue[]}> = ({captions}) => {
  const frame = useCurrentFrame();
  const currentCue = captions.find((cue) => frame >= cue.startFrame && frame < cue.endFrame);
  if (!currentCue) {
    return null;
  }

  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 64, pointerEvents: 'none'}}>
      <div
        style={{
          maxWidth: '86%',
          color: '#ffffff',
          fontSize: 44,
          fontWeight: 700,
          lineHeight: 1.22,
          textAlign: 'center',
          textShadow: '0 4px 12px rgba(0, 0, 0, 0.9)',
          backgroundColor: 'rgba(0, 0, 0, 0.42)',
          borderRadius: 14,
          padding: '14px 20px',
          whiteSpace: 'pre-wrap',
        }}
      >
        {currentCue.text}
      </div>
    </AbsoluteFill>
  );
};

const ShowcaseComposition: React.FC<ShowcaseProps> = ({scenes, audioSrc, captions}) => {
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      {scenes.map((scene) => (
        <Sequence key={scene.id} from={scene.fromFrame} durationInFrames={scene.durationInFrames}>
          {scene.src ? (
            <OffthreadVideo
              src={scene.src}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                backgroundColor: '#000',
              }}
            />
          ) : (
            <AbsoluteFill style={{backgroundColor: '#000'}} />
          )}
        </Sequence>
      ))}
      {audioSrc ? <Audio src={audioSrc} /> : null}
      <CaptionLayer captions={captions} />
    </AbsoluteFill>
  );
};

export const Root: React.FC = () => {
  return (
    <Composition
      id="Main"
      component={ShowcaseComposition}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={300}
      defaultProps={DEFAULT_PROPS}
      calculateMetadata={({props}) => {
        const typed = props as ShowcaseProps;
        const fps = Math.max(1, Number(typed.fps) || 30);
        const width = Math.max(320, Number(typed.width) || 1920);
        const height = Math.max(180, Number(typed.height) || 1080);
        const totalFrames = Math.max(1, Number(typed.totalFrames) || 300);
        return {
          fps,
          width,
          height,
          durationInFrames: totalFrames,
        };
      }}
    />
  );
};
