// Score guide page — example-only cards, no real data (§7.6)

import { VerdictBadge } from "@/components/VerdictBadge";
import { InstrumentCard } from "@/components/InstrumentCard";
import type { VerdictLabel } from "@/lib/types";

export default function ScoreGuidePage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="mb-10">
        <p className="t-eyebrow mb-2.5">Reference</p>
        <h1 className="t-h1 text-[var(--text-primary)]">Score guide</h1>
        <p className="t-lead mt-3 max-w-[52ch]">
          How to read a PRIMER result. All cards below are illustrative examples — not your data.
        </p>
        <p className="t-data text-[11px] text-[var(--text-tertiary)] mt-3 bg-[var(--surface-raised)] border border-[var(--border-hairline)] rounded-md px-3 py-1.5 inline-block">
          Example only — not your data
        </p>
      </div>

      <div className="flex flex-col gap-12">

        {/* The four verdicts */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-4">The four verdicts</h2>
          <div className="flex flex-col gap-4">
            <VerdictCard
              verdict="positive"
              exampleDelta="+18.0 pp"
              noise="±10.0 pp"
              explanation="The delta (+18.0 pp) lies outside the noise envelope (±10.0 pp). The context file improved agent success rate beyond what variance can explain."
            />
            <VerdictCard
              verdict="negative"
              exampleDelta="−14.0 pp"
              noise="±10.0 pp"
              explanation="The delta (−14.0 pp) lies outside the noise envelope (±10.0 pp) in the negative direction. The context file reduced agent success rate beyond variance."
            />
            <VerdictCard
              verdict="within-noise"
              exampleDelta="0.0 pp"
              noise="±20.0 pp"
              explanation="The delta (0.0 pp) is real but cannot be distinguished from natural variance at this task count. You're protected from acting on noise."
            />
            <VerdictCard
              verdict="refused"
              exampleDelta="N/A"
              noise="—"
              explanation="PRIMER refuses to compute a delta when the two arms used different models or providers. Any difference couldn't be attributed to the context file alone."
            />
          </div>
        </section>

        {/* Verdict rules */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-4">Exact verdict rules</h2>
          <div className="flex flex-col gap-3 text-sm text-[var(--text-secondary)] leading-relaxed">
            <RuleRow condition={<><code className="font-mono text-xs text-[var(--text-primary)]">success_delta == null</code></>} result="refused" />
            <RuleRow condition={<><code className="font-mono text-xs text-[var(--text-primary)]">|delta| ≤ noise_threshold</code></>} result="within-noise" />
            <RuleRow condition={<><code className="font-mono text-xs text-[var(--text-primary)]">delta &gt; noise_threshold</code></>} result="positive" />
            <RuleRow condition={<><code className="font-mono text-xs text-[var(--text-primary)]">delta &lt; −noise_threshold</code></>} result="negative" />
          </div>
          <p className="text-xs font-mono text-[var(--text-tertiary)] mt-3">
            Where <code>noise_threshold = max(1 / n_tasks, success_stddev)</code>
          </p>
        </section>

        {/* Delta definition */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-3">Delta definition</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            <code className="font-mono text-xs text-[var(--text-primary)]">success_delta = success_rate_with − success_rate_without</code>. Positive means the with-arm succeeded more often.
          </p>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed mt-2">
            The delta is always shown in percentage points (pp) with one decimal place and its noise envelope: <code className="font-mono text-xs text-[var(--text-primary)]">+5.0 pp ± 20.0 pp</code>.
          </p>
        </section>

        {/* Why 5 tasks → ±20pp floor */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-3">Why 5 tasks gives a ±20 pp noise floor</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            The noise floor is <code className="font-mono text-xs text-[var(--text-primary)]">1 / n_tasks</code>. With 5 tasks, that's 1/5 = 20 pp. This is the minimum observable delta: a single task flipping from fail to pass changes the success rate by exactly 1/5 = 20 pp. A delta smaller than this cannot be reliably attributed to the context file with 5 tasks.
          </p>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed mt-2">
            More tasks = lower floor = more sensitive measurement.
          </p>
        </section>

        {/* Flip states */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-4">Flip states</h2>
          <div className="flex flex-col gap-2">
            {[
              { state: "FAIL_TO_PASS", label: "Fixed by the file",       note: "Task failed without, passed with. Best case." },
              { state: "PASS_TO_FAIL", label: "Broken by the file",      note: "Task passed without, failed with. Harmful." },
              { state: "PASS_TO_PASS", label: "Passed with and without", note: "Context file had no effect on this task." },
              { state: "FAIL_TO_FAIL", label: "Failed with and without",  note: "Task unsolved regardless. Not attributable to the file." },
            ].map(({ state, label, note }) => (
              <div key={state} className="flex items-start gap-3 border border-[var(--border-hairline)] rounded-md p-3 bg-[var(--surface-elevated)] shadow-card">
                <code className="t-data text-[10px] text-[var(--text-tertiary)] w-36 shrink-0 mt-0.5">{state}</code>
                <div>
                  <p className="t-data text-xs font-medium text-[var(--text-primary)]">{label}</p>
                  <p className="t-caption mt-0.5">{note}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Cost streams */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-3">Cost streams</h2>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            Eval cost (<code className="font-mono text-xs text-[var(--text-primary)]">cost_without</code>, <code className="font-mono text-xs text-[var(--text-primary)]">cost_with</code>) is the agent's token/API cost during the runs. PRIMER overhead is the cost of generating the context file — always separate, never summed.
          </p>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed mt-2">
            Cost confidence: <em>exact</em> = provider-reported; <em>estimated</em> = approximate; <em>free</em> = local model, no cost.
          </p>
        </section>

        {/* Limitations */}
        <section className="reveal-on-scroll">
          <h2 className="t-h2 text-[var(--text-primary)] mb-3">Limitations</h2>
          <ul className="flex flex-col gap-2 text-sm text-[var(--text-secondary)] leading-relaxed ml-4">
            <li className="list-disc">Pass/fail is binary — no partial credit or output quality measurement.</li>
            <li className="list-disc">Small n means wide noise envelopes. More tasks = more sensitive measurement.</li>
            <li className="list-disc">Results are specific to this agent, this model version, and this commit.</li>
            <li className="list-disc">A positive verdict is evidence, not proof — the tasks may not represent all real-world use.</li>
            <li className="list-disc">Flaky tasks (inconsistent pass/fail across identical runs) reduce reliability; the <em>flaky tasks</em> warning flag alerts you when any task was flaky.</li>
          </ul>
        </section>

      </div>
    </div>
  );
}

function VerdictCard({
  verdict,
  exampleDelta,
  noise,
  explanation,
}: {
  verdict: VerdictLabel;
  exampleDelta: string;
  noise: string;
  explanation: string;
}) {
  return (
    <InstrumentCard className="p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <VerdictBadge verdict={verdict} size="md" />
        <span className="t-data text-[10px] text-[var(--text-tertiary)] bg-[var(--surface-raised)] px-2 py-1 rounded">
          Example only — not your data
        </span>
      </div>
      <div className="flex items-baseline gap-3">
        <span className="t-data text-3xl font-semibold text-[var(--text-primary)]">{exampleDelta}</span>
        {noise !== "—" && (
          <span className="t-data text-xs text-[var(--text-tertiary)]">{noise} noise</span>
        )}
      </div>
      <p className="t-body text-[var(--text-secondary)]">{explanation}</p>
    </InstrumentCard>
  );
}

function RuleRow({ condition, result }: { condition: React.ReactNode; result: VerdictLabel }) {
  return (
    <div className="flex items-center gap-4 border border-[var(--border-hairline)] rounded-md px-4 py-2.5 bg-[var(--surface-elevated)] shadow-card">
      <span className="flex-1 t-body text-[var(--text-secondary)]">{condition}</span>
      <span className="t-data text-[var(--text-tertiary)] text-xs">→</span>
      <VerdictBadge verdict={result} size="sm" />
    </div>
  );
}
