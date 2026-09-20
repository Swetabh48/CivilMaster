"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";
import { apiFeedback, apiGetAssignment, type Assignment } from "@/lib/api";

type Solution = {
  explanation?: string;
  final_answers?: Array<{ label: string; value: number; unit: string; formula_id: string }>;
  diagram_svg?: string | null;
  rag_context?: Array<{ source_name: string; score: number; content: string }>;
  confidence?: number;
  method?: string;
  subject?: string;
};

export default function SolveDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const [item, setItem] = useState<Assignment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [facultyKey, setFacultyKey] = useState("");
  const [notes, setNotes] = useState("");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!token || !params.id) return;
    apiGetAssignment(token, params.id)
      .then(setItem)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [token, params.id]);

  const solution = (item?.solution || {}) as Solution;

  const answers = useMemo(() => solution.final_answers || [], [solution.final_answers]);

  async function sendFeedback(is_correct: boolean, e?: FormEvent) {
    e?.preventDefault();
    if (!token || !item) return;
    setFeedbackMsg(null);
    try {
      await apiFeedback(token, {
        assignment_id: item.id,
        is_correct,
        faculty_key: facultyKey || undefined,
        notes: notes || undefined,
      });
      setFeedbackMsg("Thanks — feedback queued for admin review.");
    } catch (err) {
      setFeedbackMsg(err instanceof Error ? err.message : "Feedback failed");
    }
  }

  return (
    <main className="shell">
      <SiteHeader />
      {!item && !error ? <p className="muted">Loading solution…</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {item ? (
        <>
          <section className="hero" style={{ paddingTop: "0.25rem" }}>
            <p className="muted">{item.subject || "general"} · {item.status}</p>
            <h1 style={{ fontSize: "2rem", maxWidth: "none" }}>{item.title}</h1>
          </section>

          <div className="grid-2 fade-in">
            <div className="panel">
              <h2>Question</h2>
              <pre className="steps">{item.raw_text}</pre>
              <h2 style={{ marginTop: "1.5rem" }}>Solution</h2>
              <div className="steps">{solution.explanation || "No explanation yet."}</div>
              {answers.length ? (
                <>
                  <h3 style={{ marginTop: "1.25rem" }}>Final answers</h3>
                  <ul className="list">
                    {answers.map((a) => (
                      <li key={a.formula_id + a.label}>
                        <span>
                          {a.label}
                          <div className="muted mono" style={{ fontSize: "0.8rem" }}>
                            {a.formula_id}
                          </div>
                        </span>
                        <strong className="mono">
                          {a.value} {a.unit}
                        </strong>
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>

            <div>
              <div className="panel">
                <h2>Diagram</h2>
                {solution.diagram_svg ? (
                  <div
                    className="diagram"
                    dangerouslySetInnerHTML={{ __html: solution.diagram_svg }}
                  />
                ) : (
                  <p className="muted">No diagram for this problem type.</p>
                )}
              </div>

              <div className="panel">
                <h2>Corpus matches</h2>
                {(solution.rag_context || []).length === 0 ? (
                  <p className="muted">No retrieved chunks. Admin can ingest corpus.</p>
                ) : (
                  <ul className="list">
                    {(solution.rag_context || []).map((h) => (
                      <li key={h.source_name + h.score}>
                        <div>
                          <strong>{h.source_name}</strong>
                          <div className="muted" style={{ fontSize: "0.85rem" }}>
                            {h.content.slice(0, 160)}…
                          </div>
                        </div>
                        <span className="badge">{h.score}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <form className="panel" onSubmit={(e) => sendFeedback(false, e)}>
                <h2>Improve CivilMaster</h2>
                <p className="muted">
                  Mark correctness. Optional faculty key goes to the admin review queue for
                  periodic LoRA refresh — not live weight updates.
                </p>
                <div className="field">
                  <label htmlFor="faculty">Faculty / correct solution (optional)</label>
                  <textarea
                    id="faculty"
                    value={facultyKey}
                    onChange={(e) => setFacultyKey(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="notes">Notes</label>
                  <input id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
                </div>
                <div className="stack">
                  <button className="btn" type="button" onClick={() => sendFeedback(true)}>
                    Mark correct
                  </button>
                  <button className="btn secondary" type="submit">
                    Mark wrong + submit key
                  </button>
                </div>
                {feedbackMsg ? <p className="ok">{feedbackMsg}</p> : null}
              </form>
            </div>
          </div>
        </>
      ) : null}
    </main>
  );
}
