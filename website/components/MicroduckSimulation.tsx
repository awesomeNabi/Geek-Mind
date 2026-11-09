import { useState } from 'react';
import { ArrowRight, ArrowUpRight, Check, ChevronDown, Expand, Play, Square, Terminal } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useLanguage } from '@/lib/i18n';
import validation from '../../docs/assets/microduck-validation.json';

const repo = 'https://github.com/awesomeNabi/Geek-Mind';
const flow = [
  ['Instruct', 'A natural-language goal and current robot state enter MAGIC’s TaskPlanner.'],
  ['Orchestrate', 'TaskRuntime and ExecutionGateway dispatch ordered actions through MCP.'],
  ['Move', 'The ROS 2 bridge connects MuJoCo, learned motion policies, and Nav2.'],
  ['Observe', 'Robot state, action receipts, and two camera views show what happened.'],
];

export default function MicroduckSimulation() {
  const { t } = useLanguage();
  const [playing, setPlaying] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const { replay } = validation;
  const replaySource = `./media/${playing ? replay.gif : replay.poster}`;
  const replayControl = (imageId: string) => (
    <button type="button" onClick={() => setPlaying(value => !value)} aria-pressed={playing} aria-controls={imageId}>
      {playing ? <Square size={14} /> : <Play size={14} />}
      {t(playing ? 'Stop replay' : 'Play replay')}
    </button>
  );
  return (
    <>
      <div className="benchmark-heading microduck-heading">
        <div>
          <span className="eyebrow">MICRODUCK / MUJOCO + ROS 2</span>
          <h3>{t("Give the instruction. Watch the robot.")}</h3>
        </div>
        <a href="https://github.com/Arjunros/microduck_ros2" target="_blank" rel="noopener noreferrer" className="inline-link">
          {t("Simulation stack")} <ArrowUpRight size={15} />
        </a>
      </div>
      <p className="section-intro">
        {t("MAGIC now controls the Microduck robot in a simulated apartment. Start one terminal session, give instructions in natural language, and follow each action as it runs. A browser shows the robot’s body and head-camera view alongside its pose, task plan, and execution events.")}
      </p>

      <figure className="frontend-figure microduck-preview">
        <div className="media-topline">
          <span><span className="status-dot" />{t("MICRODUCK / OPERATOR VIEW")}</span>
          {replayControl('microduck-replay-image')}
        </div>
        <Dialog>
          <DialogTrigger className="microduck-preview-trigger" aria-label={t("Enlarge recorded Microduck operator view")}>
            <img id="microduck-replay-image" src={replaySource} width={replay.width} height={replay.height} loading="lazy" alt={t("Recorded Microduck replay: walking, sitting, standing, a look command, and a snapshot, with two camera views and changing agent status.")} />
            <span className="enlarge-label"><Expand size={15} />{t("Inspect operator view")}</span>
          </DialogTrigger>
          <DialogContent className="architecture-dialog microduck-dialog">
            <DialogTitle>{t("Microduck operator view")}</DialogTitle>
            <DialogDescription>{t("A recorded GIF from 9 November 2026. Watch the robot move and the agent status update through a fixed five-action demo in the actual simulator.")}</DialogDescription>
            <div className="media-topline">
              <span>{replay.duration_seconds} {t("s · 1× replay")}</span>
              {replayControl('microduck-dialog-image')}
            </div>
            <div className="microduck-image-scroll" role="region" aria-label={t("Full-size operator replay, scroll to inspect")} tabIndex={0}>
              <img id="microduck-dialog-image" src={replaySource} width={replay.width} height={replay.height} alt={t("Recorded Microduck replay: walking, sitting, standing, a look command, and a snapshot, with two camera views and changing agent status.")} />
            </div>
          </DialogContent>
        </Dialog>
        <figcaption><span>{t("04 / Robot body · Head camera · Agent state")}</span><span>{replay.duration_seconds} {t("s · 1× replay")} · GIF</span></figcaption>
      </figure>
      <p className="benchmark-replay-note">{t("Recorded simulation · Walk → sit → stand → look → snapshot. The robot views and agent status come from the same run; the fixed /demo sequence does not call the model planner.")}</p>

      <ol className="benchmark-flow" aria-label={t("MAGIC to Microduck execution flow")}>
        {flow.map(([title, description], index) => (
          <li key={title}>
            <div><span>0{index + 1}</span>{index < flow.length - 1 && <ArrowRight size={16} aria-hidden="true" />}</div>
            <h4>{t(title)}</h4><p>{t(description)}</p>
          </li>
        ))}
      </ol>

      <div className="microduck-session">
        <div className="microduck-session-copy">
          <span className="eyebrow">{t("ONE COMMAND / CONTINUOUS SESSION")}</span>
          <h3>{t("Speak in goals.")}<br />{t("Follow every step.")}</h3>
          <p>{t("The terminal keeps accepting new goals after each task. Watch planning, action status, and receipts as they arrive; use")} <code>/stop</code> {t("to cancel a task and block its remaining actions.")}</p>
          <ul className="capability-list">
            <li><Check size={15} />{t("Walk, turn, sit & stand")}</li>
            <li><Check size={15} />{t("Nav2 navigation")}</li>
            <li><Check size={15} />{t("Head view & snapshots")}</li>
            <li><Check size={15} />{t("Live terminal feedback")}</li>
          </ul>
        </div>
        <div className="microduck-terminal">
          <div className="media-topline"><span><Terminal size={14} />{t("TERMINAL / EXAMPLE SESSION")}</span></div>
          <pre aria-label={t("Start the Microduck console and give a Chinese natural-language command")}><code><span className="microduck-prompt">$ </span>cd magic_microduck{'\n'}<span className="microduck-prompt">$ </span>bash run.sh chat{'\n\n'}<span className="microduck-terminal-note">{t("# Browser: http://127.0.0.1:8780")}</span>{'\n'}<span className="microduck-prompt">› </span><span lang="zh-CN">向左转20度，然后坐下，再站起来</span>{'\n\n'}turn 20°   <span className="microduck-terminal-success">SUCCEEDED</span>{'\n'}sit        <span className="microduck-terminal-success">SUCCEEDED</span>{'\n'}stand      <span className="microduck-terminal-success">SUCCEEDED</span>{'\n\n'}<span className="microduck-terminal-note">/state   /stop   /quit</span></code></pre>
          <p>{t("Run in the prepared integration workspace. Enter commands in the terminal; the browser is a read-only viewer.")}</p>
        </div>
      </div>

      <dl className="microduck-checks" aria-label={t("Project-reported simulation validation")}>
        <div><dt>{t("Automated checks")}</dt><dd>{validation.automated_tests.passed}<span>{t("passed")}</span></dd></div>
        <div><dt>{t("Recorded demo")}</dt><dd>{validation.demo.actions.length}<span>{t("actions completed")}</span></dd></div>
        <div><dt>{t("Live observation")}</dt><dd>{validation.viewer.views.length}<span>{t("camera views")}</span></dd></div>
      </dl>
      <p className="benchmark-replay-note">{t("Project-reported integration checks ·")} <time dateTime={validation.verified_at}>{t("9 Nov 2026")}</time>{t(". Real-model commands and cancellation were tested separately from the fixed five-action demo shown above.")}</p>

      <details className="benchmark-trace">
        <summary>{t("Inspect the verified sequence & boundaries")} <ChevronDown size={16} aria-hidden="true" /></summary>
        <div className="benchmark-table-wrap" role="region" aria-label={t("Microduck simulation validation details")} tabIndex={0}>
          <table>
            <caption>{t("Fixed /demo sequence through the actual MAGIC runtime and MuJoCo simulator; no model call in this recorded run.")}</caption>
            <thead><tr><th scope="col">{t("Action")}</th><th scope="col">{t("Recorded result")}</th><th scope="col">{t("Status")}</th></tr></thead>
            <tbody>{validation.demo.actions.map(action => (
              <tr key={action.id}><th scope="row">{t(action.label)}</th><td>{t(action.evidence)}</td><td>{action.status}</td></tr>
            ))}</tbody>
          </table>
        </div>
        <p className="benchmark-replay-note microduck-boundaries">{t("Simulation validation only. A north-corridor navigation goal was reached; all-room coverage, object recognition, and physical hardware remain unverified. Learned sit/stand skills finish their current motion before cancellation completes. The look action confirms dispatch, not the final head pose.")}</p>
      </details>
      <div className="benchmark-links">
        <a href={`${repo}/blob/main/MICRODUCK.md`} target="_blank" rel="noopener noreferrer" className="inline-link">{t("Microduck integration guide")} <ArrowUpRight size={16} /></a>
        <a href="./media/microduck-validation.json" target="_blank" rel="noopener noreferrer" className="inline-link">{t("Validation summary")} <ArrowUpRight size={16} /></a>
        <a href={`./media/${replay.gif}`} download className="inline-link">{t("Download Microduck GIF")} <ArrowUpRight size={16} /></a>
      </div>
    </>
  );
}
