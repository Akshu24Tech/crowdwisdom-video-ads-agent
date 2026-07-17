import { Composition } from "remotion";
import { CWTAd } from "./CWTAd";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CWTAd"
        component={CWTAd}
        durationInFrames={45 * 30}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "cwt-ad-demo",
          hook: "Stop guessing which way the market moves.",
          script:
            "CrowdWisdomTrading aggregates sentiment from thousands of traders across YouTube, X, and Discord into one weighted read. Every call ships with a transparent confidence score and a full structured trade plan with clear targets and stop levels.",
          duration_target_seconds: 45,
          brand: "CrowdWisdomTrading",
          cta: "Get your free weekly briefing at crowdwisdomtrading.com",
        }}
      />
    </>
  );
};
