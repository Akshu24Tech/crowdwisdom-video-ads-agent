import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

export type CWTAdProps = {
  title: string;
  hook: string;
  script: string;
  duration_target_seconds: number;
  brand: string;
  cta: string;
};

const COLORS = {
  bg: '#0B1220',
  accent: '#3DD9B3',
  text: '#F4F7F6',
  subtext: '#9BB0C3',
};

export const CWTAd: React.FC<CWTAdProps> = ({ hook, script, brand, cta }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Phase timings (in frames)
  const hookEnd = 3 * fps;
  const scriptEnd = durationInFrames - 5 * fps;

  const hookOpacity = interpolate(frame, [0, fps * 0.5, hookEnd - fps * 0.5, hookEnd], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const scriptProgress = interpolate(frame, [hookEnd, scriptEnd], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const words = script.split(' ');
  const visibleWordCount = Math.floor(words.length * scriptProgress);
  const visibleScript = words.slice(0, visibleWordCount).join(' ');

  const ctaSpring = spring({
    frame: frame - scriptEnd,
    fps,
    config: { damping: 200 },
  });

  const showHook = frame < hookEnd;
  const showScript = frame >= hookEnd && frame < scriptEnd;
  const showCTA = frame >= scriptEnd;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily: 'Helvetica, Arial, sans-serif' }}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', padding: 80 }}>
        {showHook && (
          <div style={{ opacity: hookOpacity, textAlign: 'center' }}>
            <div style={{ color: COLORS.accent, fontSize: 28, fontWeight: 600, marginBottom: 20, letterSpacing: 2 }}>
              {brand.toUpperCase()}
            </div>
            <div style={{ color: COLORS.text, fontSize: 64, fontWeight: 800, lineHeight: 1.2 }}>
              {hook}
            </div>
          </div>
        )}

        {showScript && (
          <div style={{ maxWidth: 900, textAlign: 'center' }}>
            <div style={{ color: COLORS.text, fontSize: 42, fontWeight: 500, lineHeight: 1.5 }}>
              {visibleScript}
            </div>
          </div>
        )}

        {showCTA && (
          <div
            style={{
              opacity: ctaSpring,
              transform: `translateY(${(1 - ctaSpring) * 40}px)`,
              textAlign: 'center',
            }}
          >
            <div style={{ color: COLORS.accent, fontSize: 30, fontWeight: 700, marginBottom: 16 }}>
              {brand}
            </div>
            <div style={{ color: COLORS.subtext, fontSize: 26 }}>
              {cta}
            </div>
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};