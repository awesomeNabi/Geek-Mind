import { useState } from 'react';
import { ArrowRight, ArrowUpRight, Check, ChevronDown, Play, Square } from 'lucide-react';
import benchmark from '../../docs/assets/optimus-benchmark.json';

import { useLanguage } from '@/lib/i18n';

const repo = 'https://github.com/awesomeNabi/Geek-Mind';
const upstream = 'https://github.com/iLearn-Lab/NeurIPS24-Optimus-1';
const flow = [
  ['Observe', 'Inventory, equipment, life and location become text context.'],
  ['Decide', 'MAGIC calls DeepSeek to choose one bounded skill.'],
  ['Execute', 'STEVE-1 controls movement; native helpers craft, smelt and equip.'],
  ['Check', 'Inventory changes determine success and feed the next decision.'],
];

export default function OptimusBenchmark() {
  const { t, locale } = useLanguage();
  const [playing, setPlaying] = useState(false);
  const { overall, integration, replay } = benchmark;
  const rate = overall.success_rate_percent.toFixed(2);

  return (
    <article id="optimus" className="benchmark-block" aria-labelledby="optimus-title">
      <div className="benchmark-heading">
        <div>
          <span className="eyebrow">{t("MINECRAFT / LONG-HORIZON TASKS")}</span>
          <h3 id="optimus-title">Optimus-1</h3>
        </div>
        <a href={upstream} target="_blank" rel="noopener noreferrer" className="inline-link">{t("Official benchmark")}<ArrowUpRight size={15} />
        </a>
      </div>
      <p className="section-intro">{t("From gathering wood to crafting tools, MAGIC chooses the next skill from the observed game state. STEVE-1 turns short instructions and first-person images into controls; Optimus helpers handle the crafting interface.")}</p>

      <div className="benchmark-results">
        <div className="benchmark-score">
          <span className="eyebrow">{t("CURRENT OVERALL SUCCESS RATE")}</span>
          <div className="benchmark-score-value">{rate}<span>%</span></div>
          <div className="benchmark-score-track" aria-hidden="true">
            <span style={{ width: `${rate}%` }} />
          </div>
          <p>{t("Mean success rate across the five advanced task groups, following the official overall definition.")}</p>
          <ul className="benchmark-groups" aria-label={t("Groups included in overall")}>
            {integration.groups.filter(group => group.included_in_overall).map(group => (
              <li key={group.id}>{t(group.label)}</li>
            ))}
          </ul>
          <small>{t("Project-reported result ·")} <time dateTime={benchmark.updated_at}>{new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(benchmark.updated_at))}</time></small>
        </div>
        <div className="benchmark-setup">
          <span className="eyebrow">{t("INTEGRATION AT A GLANCE")}</span>
          <dl>
            <div><dt>{t("Source task catalog")}</dt><dd>{integration.source_tasks} {t("tasks /")} {integration.groups.length} {t("groups")}</dd></div>
            <div><dt>{t("High-level observation")}</dt><dd>{t("Public game state → text")}</dd></div>
            <div><dt>{t("Native skill interface")}</dt><dd>{t("Policy · craft · smelt · equip")}</dd></div>
            <div><dt>{t("Success check")}</dt><dd>{t("Target inventory increase")}</dd></div>
          </dl>
          <p>{t("The source catalog contains 73 tasks; alignment to the paper’s exact 67-task protocol is still pending.")}</p>
        </div>
      </div>

      <ol className="benchmark-flow" aria-label={t("MAGIC to Optimus decision loop")}>
        {flow.map(([title, description], index) => (
          <li key={title}>
            <div><span>0{index + 1}</span>{index < flow.length - 1 && <ArrowRight size={16} aria-hidden="true" />}</div>
            <h4>{t(title)}</h4>
            <p>{t(description)}</p>
          </li>
        ))}
      </ol>

      <figure className="frontend-figure optimus-replay">
        <div className="media-topline">
          <span><span className="status-dot" />{t("OPTIMUS / WOODEN SHOVEL")}</span>
          <button type="button" onClick={() => setPlaying(!playing)} aria-pressed={playing} aria-controls="optimus-replay-image">
            {playing ? <Square size={14} /> : <Play size={14} />}
            {t(playing ? 'Stop replay' : 'Play 4× replay')}
          </button>
        </div>
        <div className="benchmark-replay-stage">
          <img
            id="optimus-replay-image"
            src={`./media/${playing ? replay.gif : replay.poster}`}
            alt={t("MAGIC in Minecraft: gather logs, craft planks, a crafting table and sticks, then complete a wooden shovel.")}
            width={replay.width}
            height={replay.height}
            loading="lazy"
          />
          {!playing && (
            <button type="button" className="frontend-play" onClick={() => setPlaying(true)} aria-label={t("Play Optimus wooden shovel replay at 4 times speed")}>
              <Play size={22} fill="currentColor" />
            </button>
          )}
        </div>
        <figcaption>
          <span><Check size={14} /> {t("Task completed · DeepSeek Flash")}</span>
          <span>{replay.env_steps.toLocaleString(locale)} {t("control steps ·")} {replay.episode_seconds.toFixed(1)} {t("s ·")} {replay.actions} {t("actions")}</span>
        </figcaption>
      </figure>
      <p className="benchmark-replay-note">{t("A successful wooden-shovel episode, shown at 4× speed from published game frames. This replay illustrates execution; Wooden tasks are outside the five-group overall metric.")}</p>

      <details className="benchmark-trace">
        <summary>{t("Inspect the")} {replay.actions} {t("recorded actions")} <ChevronDown size={16} aria-hidden="true" /></summary>
        <div className="benchmark-table-wrap" role="region" aria-label={t("Recorded Optimus action trace")} tabIndex={0}>
          <table>
            <caption>{t("Actual control steps for the wooden-shovel replay (original commands)")}</caption>
            <thead><tr><th scope="col">#</th><th scope="col">{t("Skill")}</th><th scope="col">{t("Instruction")}</th><th scope="col">{t("Steps")}</th></tr></thead>
            <tbody>{replay.action_trace.map(action => (
              <tr key={action.step}>
                <th scope="row">{action.step}</th><td>{action.skill}</td><td>{action.instruction}</td><td>{action.actual_steps}</td>
              </tr>
            ))}</tbody>
            <tfoot><tr><th scope="row" colSpan={3}>{t("Total native control steps")}</th><td>{replay.env_steps.toLocaleString(locale)}</td></tr></tfoot>
          </table>
        </div>
      </details>

      <div className="benchmark-links">
        <a href={`${repo}/blob/main/OPTIMUS.md`} target="_blank" rel="noopener noreferrer" className="inline-link">{t("Optimus integration guide")}<ArrowUpRight size={16} />
        </a>
        <a href={`./media/${replay.gif}`} download className="inline-link">{t("Download GIF (12 MB)")} <ArrowUpRight size={16} /></a>
        <a href="./media/optimus-benchmark.json" target="_blank" rel="noopener noreferrer" className="inline-link">{t("Result & replay metadata")}<ArrowUpRight size={16} />
        </a>
      </div>
    </article>
  );
}
