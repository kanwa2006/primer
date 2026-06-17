// Static methodology page — zero fabricated metrics, real architecture only (§7.5)

import { InstrumentCard } from "@/components/InstrumentCard";

export default function MethodologyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="mb-10">
        <p className="t-eyebrow mb-2.5">How it works</p>
        <h1 className="t-h1 text-[var(--text-primary)]">Methodology</h1>
        <p className="t-lead mt-3 max-w-[54ch]">
          How PRIMER produces an honest, verifiable answer to one question: does this <code className="t-data text-[var(--accent-signal)] text-[0.9em]">CLAUDE.md</code> help?
        </p>
      </div>

      <div className="flex flex-col gap-12">

        {/* 1. Controlled before/after */}
        <Section title="Controlled before-and-after design">
          <p>
            PRIMER runs the same deterministic tasks through the same agent twice per evaluation — once without the context file (the <em>without</em> arm) and once with it (the <em>with</em> arm). Both arms use the same Docker image, the same agent flags, the same task suite, and the same number of repetitions. The only difference between arms is whether the context file is present in <code>/work</code>.
          </p>
          <p>
            This controlled design means that any difference in success rate is attributable to the context file — not to the agent version, the model, the environment, or the task selection.
          </p>
        </Section>

        {/* 2. Docker isolation */}
        <Section title="Docker isolation — sha256-pinned container">
          <p>
            Each run executes inside a pinned Docker container identified by a <code>sha256</code> digest. Pinning by digest (not tag) guarantees byte-for-byte reproducibility: the same digest in a future run is provably the same environment.
          </p>
          <p>
            The base image digest is recorded in every evaluation export and shown in the Instrument Status Bar and the Methods panel.
          </p>
          <ThinDiagram lines={[
            "CLI → docker pull image@sha256:<digest>",
            "      docker run --rm [--network <mode>] \\",
            "        -v task_dir:/work \\",
            "        image@sha256:<digest>",
            "        <agent command>",
          ]} />
        </Section>

        {/* 3. Egress enforcement */}
        <Section title="Egress enforcement — deny-by-default proxy">
          <p>
            When <code>network_mode</code> is <code>proxy-egress</code>, a deny-by-default outbound proxy runs on every container. The proxy logs all outbound connection attempts and blocks everything not on an explicit allow-list. This prevents the agent from phoning home, fetching external resources, or exfiltrating data — making the measurement environment reproducible across runs.
          </p>
          <p>
            When <code>egress_enforced</code> is <code>false</code> (live data currently shows <em>egress open</em>), the container uses an open bridge network. The status bar renders an amber indicator to make this visible without asserting enforcement.
          </p>
        </Section>

        {/* 4. Deterministic task derivation */}
        <Section title="Deterministic task derivation">
          <p>
            Tasks are derived from the repository's own test suite. PRIMER supports two task types:
          </p>
          <ul>
            <li>
              <strong>stub_function</strong> — a function is replaced with a stub (e.g., <code>raise NotImplementedError</code>). The agent must implement it so the pytest suite passes.
            </li>
            <li>
              <strong>revert_reimplement</strong> — a working implementation is reverted to an older commit. The agent must re-implement it so tests pass.
            </li>
          </ul>
          <p>
            The sole verdict for each task run is the <strong>pytest exit code</strong>: 0 = pass, non-zero = fail. No partial credit, no heuristics.
          </p>
        </Section>

        {/* 5. Variance & noise envelope */}
        <Section title="Variance and noise envelope">
          <p>
            Each arm runs <em>N</em> repetitions per task. The variance across runs (<code>success_stddev</code>) captures natural run-to-run fluctuation. The noise envelope is defined as:
          </p>
          <BlockCode>noise_threshold = max(1 / n_tasks, success_stddev)</BlockCode>
          <p>
            This formula sets a floor of <code>1 / n_tasks</code> — the minimum observable delta for a single-task flip — and raises it if the measured variance is higher. A delta within this envelope is classified as <em>within-noise</em>, not positive or negative.
          </p>
          <p>
            With 5 tasks, the floor is ±20 pp. This means a single task flipping from fail to pass or vice versa is not enough to declare a verdict — multiple tasks must agree.
          </p>
        </Section>

        {/* 6. Two-stream cost */}
        <Section title="Two-stream cost accounting">
          <p>
            PRIMER tracks two separate cost streams that are <strong>never combined</strong>:
          </p>
          <ul>
            <li>
              <strong>Eval cost</strong> (<code>cost_without</code>, <code>cost_with</code>) — the token/API cost incurred by the agent under test during the controlled runs.
            </li>
            <li>
              <strong>PRIMER overhead</strong> (<code>primer_overhead_usd</code>) — the cost of generating the context file using the Layer-1 provider (e.g., Anthropic). This is always shown on a separate line and never summed into the eval cost delta.
            </li>
          </ul>
          <p>
            Cost confidence is <em>exact</em> when provider APIs report exact usage, <em>estimated</em> when costs are approximate, and <em>free</em> for locally-run models.
          </p>
        </Section>

        {/* 7. Refusal rules */}
        <Section title="Refusal rules — when PRIMER says 'not comparable'">
          <p>
            PRIMER issues a <em>refused</em> verdict and sets <code>success_delta = null</code> when:
          </p>
          <ul>
            <li>The two arms used different models or providers — a delta across different models cannot be attributed to the context file alone.</li>
            <li>Isolation settings changed between compared evaluations (shown as isolation mismatch warning).</li>
          </ul>
          <p>
            Refusal is a first-class outcome. It means "we cannot give you an honest answer here" — not a failure.
          </p>
        </Section>

        {/* 8. Two-layer architecture */}
        <Section title="Two-layer architecture — generation provider vs measured agent">
          <p>
            PRIMER distinguishes between two roles:
          </p>
          <ul>
            <li>
              <strong>Layer 1 — generation provider</strong> (<code>provider</code>/<code>model</code>): the model that <em>writes</em> the <code>CLAUDE.md</code> file. Supports Anthropic, OpenAI, Gemini, OpenRouter, and Ollama.
            </li>
            <li>
              <strong>Layer 2 — agent under test</strong> (<code>agent_adapter</code>): the coding agent that <em>runs</em> inside Docker and attempts the tasks. Default is <code>claude_code</code>; the <code>gemini</code> adapter is <strong>experimental</strong>.
            </li>
          </ul>
          <p>
            The generation provider's cost is always <em>PRIMER overhead</em>, not eval cost. The current live data uses the experimental Gemini adapter path — the UI reads this from <code>agent_adapter</code> in the export and never hardcodes "Claude Code."
          </p>
        </Section>

        {/* 9. Reproducibility */}
        <Section title="Reproducibility">
          <p>
            Every evaluation export includes all the information needed to reproduce the measurement: base image digest, agent adapter, provider/model, task count, runs per config, egress mode, and the exact repo commit. The JSON exports are versioned (<code>schema_version</code>) and available on the Export page.
          </p>
        </Section>

      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <InstrumentCard
      lift={false}
      glow={false}
      reveal
      className="flex flex-col gap-4 px-6 py-7 sm:px-8 sm:py-8"
    >
      <h2 className="t-h2 text-[var(--text-primary)]">{title}</h2>
      <div className="flex flex-col gap-3 t-body text-[var(--text-secondary)] [&_code]:font-mono [&_code]:text-[0.85em] [&_code]:text-[var(--text-primary)] [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-2 [&_ul]:ml-4 [&_li]:list-disc [&_em]:not-italic [&_em]:text-[var(--text-primary)]">
        {children}
      </div>
    </InstrumentCard>
  );
}

function ThinDiagram({ lines }: { lines: string[] }) {
  return (
    <pre className="text-[11px] font-mono text-[var(--text-tertiary)] bg-[var(--surface-raised)] rounded-md px-4 py-3 overflow-x-auto leading-relaxed">
      {lines.join("\n")}
    </pre>
  );
}

function BlockCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="block font-mono text-xs text-[var(--text-primary)] bg-[var(--surface-raised)] rounded-md px-4 py-2 my-1">
      {children}
    </code>
  );
}
