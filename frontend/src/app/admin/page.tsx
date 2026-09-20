"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";
import {
  apiCorpusStats,
  apiCurateTraining,
  apiHealth,
  apiIngestCorpus,
  apiListFeedback,
  apiReviewFeedback,
  apiTrainingExport,
} from "@/lib/api";

type FeedbackRow = {
  id: string;
  assignment_id: string | null;
  is_correct: boolean;
  faculty_key: string | null;
  notes: string | null;
  review_status: string;
  question_text: string | null;
  created_at: string;
};

type Stats = {
  chunks: number;
  sources: number;
  files_on_disk?: number;
  files_unindexed?: number;
  ocr_sidecars?: number;
};

export default function AdminPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<FeedbackRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<{
    llm_backend?: string;
    ollama?: boolean;
    ocr_enabled?: boolean;
    lora_adapter?: string | null;
  } | null>(null);

  useEffect(() => {
    if (!loading && (!user || !user.is_admin)) router.replace("/dashboard");
  }, [loading, user, router]);

  async function reload() {
    if (!token) return;
    const [data, st, h] = await Promise.all([
      apiListFeedback(token),
      apiCorpusStats(token),
      apiHealth().catch(() => null),
    ]);
    setRows(data);
    setStats(st);
    setHealth(h);
  }

  useEffect(() => {
    reload().catch((err) => setError(err instanceof Error ? err.message : "Load failed"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function ingest(force = false, onlyUnindexed = false) {
    if (!token) return;
    setMessage(null);
    setError(null);
    setBusy(true);
    try {
      const body = await apiIngestCorpus(token, {
        force,
        only_unindexed: onlyUnindexed,
        use_ocr: true,
      });
      setMessage(body.message);
      const st = await apiCorpusStats(token);
      setStats(st);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  async function review(id: string, status: "approved" | "rejected") {
    if (!token) return;
    await apiReviewFeedback(token, id, status);
    await reload();
  }

  async function exportTraining() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const data = await apiTrainingExport(token);
      setMessage(`Exported ${data.count} approved pairs${data.export_path ? ` → ${data.export_path}` : ""}`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "civilmaster_approved_feedback.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  async function curate() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const res = await apiCurateTraining(token);
      setMessage(
        res.ok
          ? `Curated SFT dataset (${res.count ?? 0} approved). ${res.stdout || ""}`
          : `Curate failed: ${res.stderr || res.stdout || "unknown"}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Curate failed");
    } finally {
      setBusy(false);
    }
  }

  if (!user?.is_admin) {
    return (
      <main className="shell">
        <SiteHeader />
        <p className="muted">Admin only.</p>
      </main>
    );
  }

  return (
    <main className="shell">
      <SiteHeader />
      <h1>Admin</h1>
      <p className="lead">
        Index corpus (with OCR), review feedback, and curate the next LoRA refresh.
      </p>

      <div className="panel fade-in">
        <h2>Runtime</h2>
        <div className="stack" style={{ marginBottom: "0.75rem" }}>
          <span className="stat-pill">
            LLM <strong style={{ color: "var(--ink)" }}>{health?.llm_backend ?? "—"}</strong>
          </span>
          <span className="stat-pill">
            Ollama <strong style={{ color: "var(--ink)" }}>{health?.ollama ? "up" : "down"}</strong>
          </span>
          <span className="stat-pill">
            OCR <strong style={{ color: "var(--ink)" }}>{health?.ocr_enabled ? "on" : "off"}</strong>
          </span>
          <span className="stat-pill">
            LoRA{" "}
            <strong style={{ color: "var(--ink)" }}>
              {health?.lora_adapter ? "installed" : "missing"}
            </strong>
          </span>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
          Narration priority: CUDA LoRA → Ollama → formula-engine text. Numbers always come from the
          registry.
        </p>
      </div>

      <div className="panel">
        <h2>Corpus</h2>
        <div className="stack" style={{ marginBottom: "1rem" }}>
          <span className="stat-pill">
            Sources <strong style={{ color: "var(--ink)" }}>{stats?.sources ?? "—"}</strong>
          </span>
          <span className="stat-pill">
            Chunks <strong style={{ color: "var(--ink)" }}>{stats?.chunks ?? "—"}</strong>
          </span>
          <span className="stat-pill">
            On disk <strong style={{ color: "var(--ink)" }}>{stats?.files_on_disk ?? "—"}</strong>
          </span>
          <span className="stat-pill">
            Unindexed{" "}
            <strong style={{ color: "var(--ink)" }}>{stats?.files_unindexed ?? "—"}</strong>
          </span>
          <span className="stat-pill">
            OCR sidecars{" "}
            <strong style={{ color: "var(--ink)" }}>{stats?.ocr_sidecars ?? "—"}</strong>
          </span>
        </div>
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Incremental ingest skips unchanged files. OCR runs automatically on low-text PDFs and
          caches <code>*.pdf.ocr.txt</code> sidecars. For bulk scanned books, run{" "}
          <code>python scripts/ocr_reingest.py</code>.
        </p>
        <div className="stack">
          <button className="btn" type="button" disabled={busy} onClick={() => ingest(false)}>
            {busy ? "Indexing…" : "Ingest new files"}
          </button>
          <button
            className="btn secondary"
            type="button"
            disabled={busy}
            onClick={() => ingest(false, true)}
          >
            OCR + index unindexed
          </button>
          <button
            className="btn secondary"
            type="button"
            disabled={busy}
            onClick={() => ingest(true)}
          >
            Force re-index
          </button>
        </div>
        {message ? <p className="ok">{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </div>

      <div className="panel">
        <h2>Training loop</h2>
        <p className="muted" style={{ marginBottom: "1rem" }}>
          Approve feedback below, then export or curate into{" "}
          <code>training/datasets/civilmaster_sft.jsonl</code> for the next Colab QLoRA run.
        </p>
        <div className="stack">
          <button className="btn" type="button" disabled={busy} onClick={exportTraining}>
            Export approved JSON
          </button>
          <button className="btn secondary" type="button" disabled={busy} onClick={curate}>
            Curate SFT dataset
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Pending feedback</h2>
        {!rows.length ? <p className="muted">No pending items.</p> : null}
        <ul className="list">
          {rows.map((row) => (
            <li key={row.id} style={{ alignItems: "flex-start" }}>
              <div style={{ flex: 1 }}>
                <strong>{row.is_correct ? "Marked correct" : "Marked wrong"}</strong>
                <div className="muted" style={{ fontSize: "0.85rem", marginTop: "0.35rem" }}>
                  {(row.question_text || "").slice(0, 220)}
                </div>
                {row.faculty_key ? (
                  <pre className="steps" style={{ marginTop: "0.75rem" }}>
                    {row.faculty_key}
                  </pre>
                ) : null}
              </div>
              <div className="stack" style={{ flexDirection: "column" }}>
                <button className="btn" type="button" onClick={() => review(row.id, "approved")}>
                  Approve
                </button>
                <button
                  className="btn secondary"
                  type="button"
                  onClick={() => review(row.id, "rejected")}
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
