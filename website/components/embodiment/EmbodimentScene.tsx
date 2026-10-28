"use client";
import { useEffect, useId, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { armPortrait, dogPortrait, portraitDefs } from "./portraits";
import { rangerDefs, rangerPortrait } from "./ranger";
import { ANIMATION, sampleTimeline } from "./timeline";
import { useLanguage } from "@/lib/i18n";
import "./embodiment.css";

/** Hand-authored SVG showcase. fixedTime is useful for reproducible visual QA. */
export default function EmbodimentScene({
  fixedTime,
  debug = false,
}: {
  fixedTime?: number;
  debug?: boolean;
}) {
  const { t } = useLanguage();
  const id = useId().replaceAll(":", "");
  const root = useRef<HTMLElement>(null),
    dog = useRef<SVGGElement>(null),
    ranger = useRef<SVGGElement>(null),
    arm = useRef<SVGGElement>(null);
  const progress = useRef<SVGPathElement>(null);
  const dogShadow = useRef<SVGGElement>(null),
    rangerShadow = useRef<SVGGElement>(null),
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
      lastRanger = "",
      lastArm = "";
    let renderCount = 0,
      worstRenderMs = 0;
    const render = (time: number) => {
      const renderStarted = performance.now();
      const state = sampleTimeline(time);
      dogShadow.current?.setAttribute("opacity", String(state.dogOpacity));
      rangerShadow.current?.setAttribute("opacity", String(state.rangerOpacity));
      rangerShadow.current?.setAttribute("transform", `matrix(${state.rangerTransform.join(" ")})`);
      armShadow.current?.setAttribute("opacity", String(state.armOpacity));
      if (dog.current) {
        dog.current.setAttribute("opacity", String(state.dogOpacity));
        dog.current.setAttribute("transform", `matrix(${state.dogTransform.join(" ")})`);
        const dogKey = JSON.stringify(state.dog);
        if (state.dogOpacity > 0.003 && dogKey !== lastDog) {
          lastDog = dogKey;
          // Keep the original curved silver shells in every dog frame. The
          // showcase moves this whole group; it never swaps to another model.
          dog.current.innerHTML = portraitDefs(`${id}-dog`) + dogPortrait(`${id}-dog`, state.dog);
        }
      }
      if (ranger.current) {
        ranger.current.setAttribute("opacity", String(state.rangerOpacity));
        ranger.current.setAttribute("transform", `matrix(${state.rangerTransform.join(" ")})`);
        const rangerKey = JSON.stringify(state.ranger);
        if (state.rangerOpacity > 0.003 && rangerKey !== lastRanger) {
          lastRanger = rangerKey;
          ranger.current.innerHTML = rangerDefs(`${id}-ranger`) + rangerPortrait(`${id}-ranger`, state.ranger);
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
      data-scene-version="20261028-ranger-v7"
      ref={root}
      aria-label={t("Geek Mind: quadruped, wheeled quadruped, Ranger mobile base and PiPER arm showcase")}
    >
      <svg
        viewBox="0 0 640 640"
        role="img"
        aria-labelledby={`${id}-title ${id}-desc`}
        className="embodiment-svg"
      >
        <title id={`${id}-title`}>Geek Mind · {t("Universal embodied intelligence")}</title>
        <desc id={`${id}-desc`}>
          {t("The original silver quadruped steps, changes to wheels and gently tilts. A Ranger mobile base then steers its four wheels and moves sideways, followed by a PiPER arm reaching and opening its gripper before the loop restarts.")}
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
          {t("Universal embodied intelligence")}
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
        <g ref={rangerShadow} data-shadow="ranger" opacity="0">
          <ellipse cx="325" cy="520" rx="190" ry="18" fill="#46514e" opacity=".16" filter={`url(#${id}-shadow)`} />
          <ellipse cx="303" cy="551" rx="42" ry="5" fill="#28342e" opacity=".14" filter={`url(#${id}-contact)`} />
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
          <g ref={ranger} data-model="ranger" opacity="0" />
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
          {["01 Legged", "02 Wheeled", "03 Ranger", "04 PiPER"].map((label, i) => (
            <span key={label} className={i === stage ? "active" : ""}>
              {t(label)}
            </span>
          ))}
        </span>
        <button
          type="button"
          onClick={() => {
            if (reduced) setReduced(false);
            else setPaused(!paused);
          }}
          aria-label={t(paused || reduced ? "Play robot animation" : "Pause robot animation")}
          aria-pressed={paused || reduced}
        >
          {paused || reduced ? <Play size={13} /> : <Pause size={13} />}
        </button>
      </figcaption>
      {debug && (
        <div className="scene-debug-controls">
          <label>
            {t("Time")}{" "}
            <input
              aria-label={t("Animation time")}
              type="range"
              min="0"
              max={ANIMATION.duration - 0.01}
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
            {t("Loop")}
          </button>
          {[0, 2.2, 4.6, 6.4, 9.4, 10.6, 11.2, 12, 12.8, 14.2, 15.2, 16.2, 17.2, 18, 20, 22, 23.6].map((t) => (
            <button key={t} onClick={() => setSeek(t)}>
              {t}s
            </button>
          ))}
        </div>
      )}
    </figure>
  );
}
