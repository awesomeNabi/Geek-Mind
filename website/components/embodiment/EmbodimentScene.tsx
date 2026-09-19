"use client";
import { useEffect, useId, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { renderSVG } from "./geometry";
import { buildDog } from "./robots";
import { armPortrait, dogPortrait, portraitDefs } from "./portraits";
import { ANIMATION, ramp, sampleTimeline } from "./timeline";
import "./embodiment.css";

/** Hand-authored SVG showcase. fixedTime is useful for reproducible visual QA. */
export default function EmbodimentScene({
  fixedTime,
  debug = false,
}: {
  fixedTime?: number;
  debug?: boolean;
}) {
  const id = useId().replaceAll(":", "");
  const root = useRef<HTMLElement>(null),
    dog = useRef<SVGGElement>(null),
    arm = useRef<SVGGElement>(null);
  const progress = useRef<SVGPathElement>(null);
  const dogShadow = useRef<SVGGElement>(null),
    armShadow = useRef<SVGGElement>(null);
  const elapsed = useRef(0),
    visible = useRef(true);
  const [paused, setPaused] = useState(false),
    [reduced, setReduced] = useState(false),
    [stage, setStage] = useState(0);
  const [seek, setSeek] = useState<number | undefined>(undefined);
  const [playOverride, setPlayOverride] = useState(false);
  const timeOverride = seek ?? (playOverride ? undefined : fixedTime);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible.current = entry.isIntersecting;
      },
      { threshold: 0.01 },
    );
    if (root.current) observer.observe(root.current);
    return () => {
      query.removeEventListener("change", update);
      observer.disconnect();
    };
  }, []);
  useEffect(() => {
    let frame = 0,
      previous = 0,
      lastDraw = -Infinity,
      lastStage = -1;
    let lastDog = "",
      lastArm = "";
    let orbitGeometry: ReturnType<typeof buildDog> | undefined;
    let renderCount = 0,
      worstRenderMs = 0;
    const render = (time: number) => {
      const renderStarted = performance.now();
      const state = sampleTimeline(time);
      dogShadow.current?.setAttribute("opacity", String(state.dogOpacity));
      armShadow.current?.setAttribute("opacity", String(state.armOpacity));
      if (!orbitGeometry && state.t >= ANIMATION.wheelsFade[1] && state.t <= ANIMATION.orbit[0]) {
        orbitGeometry = buildDog(sampleTimeline(ANIMATION.orbit[0]).dog);
      }
      if (dog.current) {
        dog.current.setAttribute("opacity", String(state.dogOpacity));
        const orbit = state.t > ANIMATION.orbit[0] && state.t < ANIMATION.orbit[1];
        const dogKey = orbit ? `orbit-${state.t}` : JSON.stringify(state.dog);
        if (state.dogOpacity > 0.003 && dogKey !== lastDog) {
          lastDog = dogKey;
          const portrait = portraitDefs(`${id}-dog`) + dogPortrait(`${id}-dog`, state.dog);
          if (orbit) {
            const blend =
              ramp(state.t, ANIMATION.orbit[0], ANIMATION.orbit[0] + ANIMATION.orbitBlend) *
              (1 - ramp(state.t, ANIMATION.orbit[1] - ANIMATION.orbitBlend, ANIMATION.orbit[1]));
            orbitGeometry ??= buildDog(state.dog);
            const geometry = renderSVG(
              orbitGeometry,
              {
                ...state.dogCamera,
                target: [0, 1.47, 0],
              },
              `${id}-orbit`,
            );
            dog.current.innerHTML = `<g opacity="${1 - blend}">${portrait}</g><g opacity="${blend}">${geometry}</g>`;
          } else dog.current.innerHTML = portrait;
        }
      }
      if (arm.current) {
        arm.current.setAttribute("opacity", String(state.armOpacity));
        const armKey = JSON.stringify(state.arm);
        if (state.armOpacity > 0.003 && armKey !== lastArm) {
          lastArm = armKey;
          arm.current.innerHTML = portraitDefs(`${id}-arm`) + armPortrait(`${id}-arm`, state.arm);
        }
      }
      if (progress.current)
        progress.current.setAttribute(
          "stroke-dasharray",
          `${(state.t / ANIMATION.duration) * 548} 548`,
        );
      if (lastStage !== state.stageIndex) {
        setStage(state.stageIndex);
        lastStage = state.stageIndex;
      }
      if (root.current) {
        root.current.dataset.time = state.t.toFixed(2);
        if (debug) {
          const cost = performance.now() - renderStarted;
          worstRenderMs = Math.max(worstRenderMs, cost);
          root.current.dataset.renderCount = String(++renderCount);
          root.current.dataset.renderMs = cost.toFixed(1);
          root.current.dataset.worstRenderMs = worstRenderMs.toFixed(1);
        }
      }
    };
    render(timeOverride ?? elapsed.current);
    const resetClock = () => {
      previous = 0;
    };
    document.addEventListener("visibilitychange", resetClock);
    const tick = (now: number) => {
      // Preserve source timing under slow frames; pause across backgrounding.
      const delta = previous ? (now - previous) / 1000 : 0;
      previous = now;
      if (
        !paused &&
        !reduced &&
        visible.current &&
        !document.hidden &&
        timeOverride === undefined
      ) {
        elapsed.current = (elapsed.current + delta) % ANIMATION.duration;
        if (now - lastDraw >= 1000 / ANIMATION.fps) {
          render(elapsed.current);
          const interval = 1000 / ANIMATION.fps;
          lastDraw = Number.isFinite(lastDraw) ? now - ((now - lastDraw) % interval) : now;
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("visibilitychange", resetClock);
    };
  }, [paused, reduced, timeOverride, id, debug]);
  return (
    <figure
      className={`embodiment-scene${debug ? " embodiment-debug" : ""}`}
      data-scene-version="20260919-svg-v4"
      ref={root}
      aria-label="Geek Mind 通用具身大脑：四足机械狗、轮足机械狗与松灵 PiPER 机械臂循环展示"
    >
      <svg
        viewBox="0 0 640 640"
        role="img"
        aria-labelledby={`${id}-title ${id}-desc`}
        className="embodiment-svg"
      >
        <title id={`${id}-title`}>Geek Mind 通用具身大脑</title>
        <desc id={`${id}-desc`}>
          银色四足机器人踏步，小腿淡出并切换为轮足机器人，环绕展示后淡出，出现松灵 PiPER
          机械臂；机械臂伸展并开合夹爪，随后回到四足形态。
        </desc>
        <defs>
          <radialGradient id={`${id}-floor`}>
            <stop stopColor="#878d86" stopOpacity=".15" />
            <stop offset="1" stopColor="#fdfaf4" stopOpacity="0" />
          </radialGradient>
          <filter id={`${id}-shadow`} x="-50%" y="-150%" width="200%" height="400%">
            <feGaussianBlur stdDeviation="9" />
          </filter>
          <filter id={`${id}-contact`} x="-50%" y="-150%" width="200%" height="400%">
            <feGaussianBlur stdDeviation="4" />
          </filter>
          <clipPath id={`${id}-bounds`}>
            <rect x="0" y="102" width="640" height="474" />
          </clipPath>
          <linearGradient id={`${id}-rule`}>
            <stop stopColor="#446c55" stopOpacity=".1" />
            <stop offset=".5" stopColor="#446c55" stopOpacity=".6" />
            <stop offset="1" stopColor="#446c55" stopOpacity=".1" />
          </linearGradient>
        </defs>
        <text x="320" y="58" textAnchor="middle" className="scene-heading">
          Geek Mind
        </text>
        <text x="320" y="88" textAnchor="middle" className="scene-subheading">
          通用具身大脑
        </text>
        <path d="M218 107H422" stroke={`url(#${id}-rule)`} />
        <ellipse cx="320" cy="522" rx="242" ry="50" fill={`url(#${id}-floor)`} />
        <g ref={dogShadow} data-shadow="dog">
          <ellipse
            cx="335"
            cy="512"
            rx="119"
            ry="12"
            fill="#696e66"
            opacity=".13"
            filter={`url(#${id}-shadow)`}
          />
        </g>
        <g ref={armShadow} data-shadow="arm" opacity="0">
          <ellipse
            cx="328"
            cy="547"
            rx="87"
            ry="11"
            fill="#696e66"
            opacity=".12"
            filter={`url(#${id}-shadow)`}
          />
          <ellipse
            cx="358"
            cy="558"
            rx="43"
            ry="7"
            fill="#353c36"
            opacity=".19"
            filter={`url(#${id}-contact)`}
          />
        </g>
        <g clipPath={`url(#${id}-bounds)`}>
          <g ref={dog} data-model="go2" />
          <g ref={arm} data-model="piper" opacity="0" />
        </g>
        <path d="M46 579H594" stroke="#dcd8cf" strokeWidth="1" />
        <path
          ref={progress}
          d="M46 579H594"
          stroke="#446c55"
          strokeWidth="1.5"
          strokeDasharray="0 548"
        />
      </svg>
      <figcaption className="scene-caption">
        <span className="scene-stages">
          {["01 足式", "02 轮式", "03 松灵 PiPER"].map((label, i) => (
            <span key={label} className={i === stage ? "active" : ""}>
              {label}
            </span>
          ))}
        </span>
        <button
          type="button"
          onClick={() => {
            if (reduced) setReduced(false);
            else setPaused(!paused);
          }}
          aria-label={paused || reduced ? "播放机器人动画" : "暂停机器人动画"}
        >
          {paused || reduced ? <Play size={13} /> : <Pause size={13} />}
        </button>
      </figcaption>
      {debug && (
        <div className="scene-debug-controls">
          <label>
            时间{" "}
            <input
              aria-label="动画时间"
              type="range"
              min="0"
              max="14.99"
              step=".01"
              value={timeOverride ?? 0}
              onChange={(e) => setSeek(Number(e.target.value))}
            />
          </label>
          <button
            onClick={() => {
              setSeek(undefined);
              setPlayOverride(true);
              elapsed.current = 0;
              setPaused(false);
            }}
          >
            循环
          </button>
          {[0, 2.2, 3.7, 4.6, 5.3, 5.6, 5.8, 6, 6.2, 6.5, 7, 8.2, 9, 11, 13, 14.6].map((t) => (
            <button key={t} onClick={() => setSeek(t)}>
              {t}s
            </button>
          ))}
        </div>
      )}
    </figure>
  );
}
