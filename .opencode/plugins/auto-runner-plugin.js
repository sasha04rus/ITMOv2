/**
 * Auto-runner plugin: after file edits in practice_04/service, run runner and attach results to context.
 * Compatible with opencode 1.18.x hook surface: use event bus and tool.execute.after as fallback.
 */

export default async ({ client, project, directory, $ }) => {
  const path = (await import("path")).default;
  const fs = (await import("fs")).default;
  const { spawn } = await import("child_process");

  const RESULTS_DIR = path.join(directory, ".opencode", "hooks", "results");
  const SERVICE_DIR = path.join(directory, "practices", "practice_04", "service");
  const EVIDENCE = path.join(directory, "practices", "practice_04", "evidence");

  const ensureDirs = () => {
    for (const d of [RESULTS_DIR, EVIDENCE]) {
      if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
    }
  };

  let running = false;
  let pending = false;
  const runRunner = () => new Promise((resolve) => {
    ensureDirs();
    const runnerPath = path.join(directory, ".opencode", "hooks", "runner.sh");
    if (running) { pending = true; return resolve({ code: -1, out: "skipped:running", err: "" }); }
    running = true;
    const child = spawn(runnerPath, [], { stdio: ["ignore", "pipe", "pipe"] });
    let out = ""; let err = "";
    child.stdout.on("data", (d) => out += d.toString());
    child.stderr.on("data", (d) => err += d.toString());
    child.on("close", (code) => {
      // Write summary to evidence; avoid triggering watcher by excluding service dir
      try {
        fs.appendFileSync(path.join(EVIDENCE, "runner_auto.log"), `code=${code}\n${out}\n`);
      } catch (e) {
        console.error("[auto-runner] evidence write error:", e?.message || e);
      }
      running = false;
      if (pending) { pending = false; setTimeout(() => runRunner(), 50); }
      // Inject latest runner result as a system message so the model sees it
      try {
        const latestPath = path.join(RESULTS_DIR, "latest.json");
        const data = JSON.parse(fs.readFileSync(latestPath, "utf-8"));
        const summary = `[runner] status=${data.status}; messages=${(data.messages||[]).join("; ")}`;
        // no-op: delivery handled in tool.execute.after
      } catch (e) {
        console.error("[auto-runner] system message error:", e?.message || e);
      }
      resolve({ code, out, err });
    });
  });

  return {
    async config(cfg) {
      ensureDirs();
    },
    async "tool.execute.after"(input, output) {
      try {
        // Trigger only after successful edit tool executions
        const toolName = input?.tool || "";
        if (!toolName) return;
        const isEdit = toolName.startsWith("edit") || toolName.includes("apply_patch");
        if (!isEdit) return;
        const res = await runRunner();
        // Attach latest runner result into the tool output for the agent to react
        const latestPath = path.join(RESULTS_DIR, "latest.json");
        const data = JSON.parse(fs.readFileSync(latestPath, "utf-8"));
        const summary = `[runner] status=${data.status}; messages=${(data.messages||[]).join("; ")}`;
        // Mutate output in place: add runner summary to output.output and details to metadata
        if (output && typeof output === 'object') {
          const base = typeof output.output === 'string' ? output.output : '';
          output.output = base ? `${base}\n${summary}` : summary;
          output.metadata = Object.assign({}, output.metadata || {}, { runner: data });
        }
      } catch (e) {
        console.error("[auto-runner] tool.execute.after error:", e?.message || e);
      }
    }
  };
};
