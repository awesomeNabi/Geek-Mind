import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, ArrowUpRight, Camera, Check, ChevronDown, ChevronLeft, ChevronRight, Circle, Clock3, Expand, Pause, Play, RotateCcw, ShieldCheck, X } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useLanguage } from '@/lib/i18n';
import sourceData from '../../docs/assets/microduck-recovery-case.json';
import './MicroduckRecovery.css';

type Step = { id: string; skill: string; arguments: Record<string, unknown>; label: string; kept: boolean; final_status: string };
type Revision = { number: number; at: number; end_event_id: number; kept_count: number; nodes: Step[]; input: { pose: { x: number; y: number; yaw_degrees: number }; remaining_actions: number; remaining_seconds: number; previous_results: { skill: string; status: string; error_code: string | null }[] }; model_plan: unknown };
type Event = { id: number; at: number; kind: string; revision: number; label: string; status?: string; nodes?: [string, string][]; node_id?: string };
type Replay = { kind: 'events' | 'robot'; gif: string; poster: string; width: number; height: number; speed: number; duration_seconds: number; source_session: string; result: string };
type RecoveryCase = { source: { session: string; date: string; model: string; event_ids: number[] }; goal: { original: string; english: string }; status: string; elapsed_seconds: number; metrics: { replans: number; actions: number; model_calls: number; successful_actions: number; failed_actions: number }; revisions: Revision[]; events: Event[]; actions: { node_id: string; revision: number; label: string; status: string; error_code: string | null; observation: { verification?: string; error_m?: number } }[]; photo: { file: string; width: number; height: number }; replay: Replay | null; rerun: Replay | null };
const recovery = sourceData as unknown as RecoveryCase;
const repo = 'https://github.com/awesomeNabi/Geek-Mind';
const clock = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
const statusLabel: Record<string, string> = { PENDING: 'Queued', BLOCKED: 'Running', RUNNING: 'Running', VERIFYING: 'Checking', SUCCEEDED: 'Verified', FAILED: 'Failed' };

export default function MicroduckSimulation() {
  const { t, locale } = useLanguage();
  const [cursor, setCursor] = useState(recovery.events.length - 1);
  const [playing, setPlaying] = useState(false);
  const [gifPlaying, setGifPlaying] = useState(() => !window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [rerunOpen, setRerunOpen] = useState(false);
  const [rerunPlaying, setRerunPlaying] = useState(false);
  const snapshot = useMemo(() => {
    let number = 1;
    let states: Record<string, string> = {};
    for (const event of recovery.events.slice(0, cursor + 1)) {
      if (event.kind === 'plan') {
        number = event.revision;
        states = Object.fromEntries(recovery.revisions[number - 1].nodes.map(node => [node.id, node.kept ? 'SUCCEEDED' : 'PENDING']));
      }
      if (event.nodes) states = Object.fromEntries(event.nodes);
      if (event.kind === 'action' && event.node_id && event.status === 'RUNNING') states[event.node_id] = 'RUNNING';
    }
    return { revision: recovery.revisions[number - 1], states };
  }, [cursor]);
  useEffect(() => {
    if (!playing) return;
    if (cursor === recovery.events.length - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setCursor(value => value + 1), 850);
    return () => window.clearTimeout(timer);
  }, [cursor, playing]);
  const seek = (value: number) => { setPlaying(false); setCursor(value); };
  const selectRevision = (revision: Revision) => seek(recovery.events.findIndex(event => event.id === revision.end_event_id));
  const replay = recovery.replay;
  const rerun = recovery.rerun;
  const imageSource = replay ? `./media/${gifPlaying ? replay.gif : replay.poster}` : undefined;
  const revision = snapshot.revision;
  const current = recovery.events[cursor];
  const latestFailure = [...revision.input.previous_results].reverse().find(result => result.status === 'FAILED');
  const failures = recovery.events.slice(0, cursor + 1).filter(event => event.kind === 'action' && event.status === 'FAILED').length;
  const gifControl = (id: string) => <button type="button" onClick={() => setGifPlaying(value => !value)} aria-controls={id} aria-pressed={gifPlaying}>{gifPlaying ? <Pause size={14} /> : <Play size={14} />}{t(gifPlaying ? 'Pause recording' : 'Play recording')}</button>;

  return <div className="microduck-case">
    <div className="benchmark-heading microduck-heading">
      <div><span className="eyebrow">{t('MICRODUCK / PLANNING & RECOVERY')}</span><h3>{t('One goal. Four plans. A recovered task.')}</h3></div>
      <span className="md-outcome"><ShieldCheck size={16} />{t('Task verified')}</span>
    </div>
    <p className="section-intro">{t('A real model-planned task in the apartment simulator. Three attempts fail along the way. MAGIC keeps the verified work, feeds the failures back to the model, and completes the remaining steps.')}</p>
    <div className="md-instruction"><span className="eyebrow">{t('THE USER REQUEST')}</span><blockquote lang={locale === 'zh-CN' ? 'zh-CN' : 'en'}>“{locale === 'zh-CN' ? recovery.goal.original : recovery.goal.english}”</blockquote>{locale === 'en' && <p lang="zh-CN">{recovery.goal.original}</p>}</div>
    <dl className="md-metrics" aria-label={t('Recorded task results')}>
      <div><dt>{t('Model replans')}</dt><dd>{recovery.metrics.replans}<span>{t('after execution failures')}</span></dd></div>
      <div><dt>{t('Action attempts')}</dt><dd>{recovery.metrics.actions}<span>{recovery.metrics.successful_actions} {t('succeeded')} · {recovery.metrics.failed_actions} {t('failed')}</span></dd></div>
      <div><dt>{t('Task duration')}</dt><dd>{clock(recovery.elapsed_seconds)}<span>{t('instruction to verified result')}</span></dd></div>
    </dl>

    {replay && <figure className="frontend-figure md-recording">
      <div className="media-topline"><span><span className="status-dot" />{t('RECORDED DECISIONS / GIF REPLAY')}</span>{gifControl('microduck-recovery-gif')}</div>
      <Dialog>
        <DialogTrigger className="microduck-preview-trigger" aria-label={t('Enlarge the recorded task')}>
          <img id="microduck-recovery-gif" src={imageSource} width={replay.width} height={replay.height} loading="lazy" alt={t('The successful task log replayed as readable plans: failures trigger new proposals while verified steps stay complete.')} />
          <span className="enlarge-label"><Expand size={15} />{t('Inspect the recording')}</span>
        </DialogTrigger>
        <DialogContent className="architecture-dialog microduck-dialog"><DialogTitle>{t('The recorded planning and recovery loop')}</DialogTitle><DialogDescription>{t('The successful task events reconstructed as readable plans. Waiting time is compressed. This animation is a log replay, not robot camera footage.')}</DialogDescription><div className="media-topline"><span>{t('Pauses compressed')} · GIF</span>{gifControl('microduck-recovery-dialog-gif')}</div><img id="microduck-recovery-dialog-gif" src={imageSource} width={replay.width} height={replay.height} alt={t('The successful task log replayed as readable plans: failures trigger new proposals while verified steps stay complete.')} /></DialogContent>
      </Dialog>
      <figcaption><span>{t('04 / Plans · Failures · Verified progress')}</span><span>{replay.duration_seconds.toFixed(1)} {t('s playback')} · {t('Pauses compressed')}</span></figcaption>
      <p className="md-recording-note">{t('The GIF and interactive explorer reconstruct the same successful task log. Actual robot footage from an independent repeat run is available below.')}</p>
    </figure>}

    <div className="md-explorer" id="microduck-plan-explorer">
      <div className="md-explorer-heading"><div><span className="eyebrow">{t('THE PLAN, MADE READABLE')}</span><h4>{t('Follow the decisions, not the JSON.')}</h4></div><span className="md-source-date">{recovery.source.date} · {t('Recorded task')}</span></div>
      <p className="md-explorer-intro">{t('Choose a plan to inspect its outcome, or replay the recorded decisions. Green steps carry forward; they are not executed again.')}</p>
      <div className="md-revisions" role="group" aria-label={t('Select a plan version')}>
        {recovery.revisions.map(plan => {
          const failed = plan.nodes.some(node => node.final_status === 'FAILED');
          return <button key={plan.number} type="button" aria-pressed={plan.number === revision.number} onClick={() => selectRevision(plan)} data-revision={plan.number}>
            <span>{plan.number === 1 ? t('Initial plan') : `${t('Replan')} ${plan.number - 1}`}</span>
            <strong>{plan.number === 1 ? t('Break down the goal') : plan.number === recovery.revisions.length ? t('Recover and finish') : plan.nodes.some(node => !node.kept && node.skill === 'walk') ? t('Change the approach') : t('Retry navigation')}</strong>
            <small className={failed ? 'md-failed-text' : 'md-verified-text'}>{failed ? <X size={12} /> : <Check size={12} />}{t(failed ? 'Attempt failed' : 'Task completed')}</small>
          </button>;
        })}
      </div>
      <div className="md-plan-layout">
        <div className="md-plan-list">
          <div className="md-plan-topline"><span>{t('Plan')} {revision.number} / {recovery.revisions.length}</span><span>{revision.kept_count} {t('verified steps kept')}</span></div>
          <ol aria-label={`${t('Plan')} ${revision.number}`}>
            {revision.nodes.map((node, index) => {
              const status = snapshot.states[node.id] ?? 'PENDING';
              const verified = status === 'SUCCEEDED';
              return <li key={node.id} className={`md-step md-step-${status.toLowerCase()}${node.kept ? ' md-step-kept' : ''}`} data-node-status={status}>
                <span className="md-step-icon" aria-hidden="true">{verified ? <Check size={15} /> : status === 'FAILED' ? <X size={15} /> : status === 'RUNNING' || status === 'BLOCKED' ? <Clock3 size={15} /> : <Circle size={12} />}</span>
                <div className="md-step-copy"><strong>{t(node.label)}</strong><span>{node.kept ? t('Verified earlier · not repeated') : `${String(index + 1).padStart(2, '0')} / ${node.skill}`}</span></div>
                <span className="md-step-state">{t(statusLabel[status] ?? status)}</span>
              </li>;
            })}
          </ol>
        </div>
        <aside className="md-feedback">
          <span className="eyebrow">{t(revision.number === 1 ? 'FROM REQUEST TO ACTIONS' : 'FEEDBACK → NEXT PROPOSAL')}</span>
          <h4>{t(revision.number === 1 ? 'A finite, ordered plan.' : 'Continue from the latest state.')}</h4>
          <p>{t(revision.number === 1 ? 'The model turns the request into six ordered actions. A full circle becomes two 180° turns, within the available tool limits.' : 'The next model call receives the latest pose, verified progress, failed action receipts, and the remaining budget.')}</p>
          {latestFailure && <div className="md-failure-note"><X size={15} /><div><strong>{t(latestFailure.error_code === 'motion_timeout' ? 'Walking timed out' : 'Navigation failed')}</strong><span>{t(latestFailure.error_code === 'motion_timeout' ? 'The requested walking distance was not confirmed.' : 'Nav2 aborted the previous navigation attempt.')}</span></div></div>}
          <dl className="md-context"><div><dt>{t('Latest position')}</dt><dd>({revision.input.pose.x.toFixed(2)}, {revision.input.pose.y.toFixed(2)}) m</dd></div><div><dt>{t('Heading')}</dt><dd>{revision.input.pose.yaw_degrees.toFixed(1)}°</dd></div><div><dt>{t('Actions left at planning')}</dt><dd>{revision.input.remaining_actions} / 12</dd></div></dl>
          <div className="md-kept-note"><ShieldCheck size={18} /><p>{t(revision.kept_count > 0 ? 'Completed work stays verified. Only the remaining proposal is dispatched.' : 'Each action waits for its predecessor and a verification result.')}</p></div>
        </aside>
      </div>
      <div className="md-player">
        <div className="md-player-controls"><button type="button" className="md-play-button" onClick={() => { if (cursor >= recovery.events.length - 2) setCursor(0); setPlaying(value => !value); }} aria-pressed={playing}>{playing ? <Pause size={15} /> : <Play size={15} />}{t(playing ? 'Pause decisions' : 'Replay decisions')}</button><button type="button" onClick={() => seek(0)} aria-label={t('Restart decisions')}><RotateCcw size={15} /></button><button type="button" onClick={() => seek(Math.max(0, cursor - 1))} disabled={cursor === 0} aria-label={t('Previous event')}><ChevronLeft size={17} /></button><button type="button" onClick={() => seek(Math.min(recovery.events.length - 1, cursor + 1))} disabled={cursor === recovery.events.length - 1} aria-label={t('Next event')}><ChevronRight size={17} /></button><span className="md-player-time">{clock(current.at)} / {clock(recovery.elapsed_seconds)}</span></div>
        <input type="range" min="0" max={recovery.events.length - 1} value={cursor} onChange={event => seek(Number(event.target.value))} aria-label={t('Seek recorded decisions')} aria-valuetext={`${clock(current.at)} · ${t(current.label)}`} />
        <div className="md-current-event" aria-live="polite"><span><span className={current.status === 'FAILED' ? 'md-event-dot md-event-failed' : 'md-event-dot'} />{t(current.label)}{current.status && current.kind === 'action' ? ` · ${t(statusLabel[current.status] ?? current.status)}` : ''}</span><span>{failures} {t('failures observed')}</span></div>
        <p>{t('Event replay with pauses compressed. The displayed clock follows the original recording timestamps.')}</p>
      </div>
    </div>

    <div className="md-evidence">
      <figure><img src={`./media/${recovery.photo.file}`} width={recovery.photo.width} height={recovery.photo.height} loading="lazy" alt={t('The head-camera photo saved after verified arrival at the bathroom.')} /><figcaption><Camera size={15} />{t('The requested photo, saved at the bathroom.')}</figcaption></figure>
      <div><span className="eyebrow">{t('WHAT WAS ACTUALLY VERIFIED')}</span><h4>{t('Arrival before the next action.')}</h4><p>{t('Bathroom arrival was confirmed within 20.7 cm of its target. After recovery, kitchen arrival was confirmed within 22.4 cm. Only then did the robot finish the full turn and sit down.')}</p><div className="md-evidence-tags"><span><Check size={14} />{t('Arrival confirmed')}</span><span><Check size={14} />{t('Photo saved')}</span><span><Check size={14} />{t('Sit state observed')}</span></div></div>
    </div>

    {rerun && <details className="benchmark-trace md-rerun" onToggle={event => { const open = event.currentTarget.open; setRerunOpen(open); if (!open) setRerunPlaying(false); }}>
      <summary><span>{t('Watch an independent robot recording')} <span className="md-failed-text">· {t('Repeat run failed')}</span></span><ChevronDown size={16} /></summary>
      <p className="benchmark-replay-note">{t('Two additional recordings of the same instruction ended in failure. This GIF shows the second: real robot cameras, live plans, and three recovery attempts. It is a separate run from the successful case above.')}</p>
      <div className="media-topline"><span>{t('ACTUAL SIMULATOR CAPTURE')} · {rerun.speed}×</span><button type="button" aria-controls="microduck-rerun-gif" aria-pressed={rerunPlaying} onClick={() => setRerunPlaying(value => !value)}>{rerunPlaying ? <Pause size={14} /> : <Play size={14} />}{t(rerunPlaying ? 'Pause recording' : 'Play recording')}</button></div>
      {rerunOpen && <img id="microduck-rerun-gif" src={`./media/${rerunPlaying ? rerun.gif : rerun.poster}`} width={rerun.width} height={rerun.height} alt={t('An independent repeat run with real robot cameras and live task state; the run ends in failure after exhausting its recovery budget.')} />}
      <p className="md-source-note">{t('Source:')} {rerun.source_session} · {t('Recording result:')} {rerun.result}. <a className="inline-link" href={`./media/${rerun.gif}`} download>{t('Download robot recording')}<ArrowUpRight size={13} /></a></p>
    </details>}

    <details className="benchmark-trace md-inspector"><summary>{t('Inspect all attempts & model proposals')}<ChevronDown size={16} /></summary>
      <p className="benchmark-replay-note">{t('Successful and failed physical attempts are both retained. Earlier verified nodes are carried across plan versions without another robot command.')}</p>
      <div className="benchmark-table-wrap" role="region" tabIndex={0} aria-label={t('Recorded action attempts')}><table><caption>{t('Every dispatched action in this task')}</caption><thead><tr><th>{t('Plan')}</th><th>{t('Action')}</th><th>{t('Evidence or failure')}</th><th>{t('Result')}</th></tr></thead><tbody>{recovery.actions.map(action => <tr key={`${action.revision}:${action.node_id}`}><th scope="row">{action.revision}</th><td>{t(action.label)}</td><td>{action.observation.error_m !== undefined ? `${(action.observation.error_m * 100).toFixed(1)} cm · ${t('arrival error')}` : t(action.observation.verification ?? (action.error_code === 'motion_timeout' ? 'Walking distance not reached before timeout' : 'Nav2 aborted the attempt'))}</td><td className={action.status === 'FAILED' ? 'md-failed-text' : 'md-verified-text'}>{t(action.status === 'SUCCEEDED' ? 'Verified' : 'Failed')}</td></tr>)}</tbody></table></div>
      <details className="md-raw-plan"><summary>{t('Original structured proposal for the selected plan')}<ChevronDown size={14} /></summary><pre><code>{JSON.stringify(revision.model_plan, null, 2)}</code></pre></details>
      <p className="md-source-note">{t('Source:')} {recovery.source.session} · {t('events')} {recovery.source.event_ids.join('–')} · {recovery.source.model} · {recovery.metrics.model_calls} {t('model calls')}. {t('Only this task is included; later console commands are excluded.')}</p>
    </details>
    <p className="md-boundary">{t('One observed simulation run, not a benchmark success rate. Plans use live robot state and configured room coordinates; the model was not given camera images. The recording does not establish physical hardware support or general obstacle-avoidance ability.')}</p>
    <div className="benchmark-links"><a href="./media/microduck-recovery-case.json" target="_blank" rel="noopener noreferrer" className="inline-link">{t('Task evidence & plans')}<ArrowUpRight size={15} /></a>{replay && <a href={`./media/${replay.gif}`} download className="inline-link">{t('Download task GIF')}<ArrowUpRight size={15} /></a>}<a href={`${repo}/tree/main/integrations/microduck`} target="_blank" rel="noopener noreferrer" className="inline-link">{t('Microduck source code')}<ArrowUpRight size={15} /></a><a href={`${repo}/blob/main/MICRODUCK.md`} target="_blank" rel="noopener noreferrer" className="inline-link">{t('Integration guide')}<ArrowRight size={15} /></a></div>
  </div>;
}
