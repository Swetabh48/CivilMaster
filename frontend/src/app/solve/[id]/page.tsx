"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";
import {
  apiChatAboutSolution,
  apiFeedback,
  apiGetAssignment,
  downloadAssignmentExport,
  type Assignment,
} from "@/lib/api";

type PackProblem = {
  id?: string;
  title?: string;
  kind?: string;
  question?: string;
  explanation?: string;
  final_answers?: Array<{ label: string; value: number; unit: string; formula_id?: string }>;
  diagram_svg?: string | null;
  steps?: Array<Record<string, unknown>>;
  diagram_type?: string;
};

type Solution = {
  explanation?: string;
  final_answers?: Array<{ label: string; value: number; unit: string; formula_id: string }>;
  diagram_svg?: string | null;
  rag_context?: Array<{ source_name: string; score: number; content: string }>;
  confidence?: number;
  method?: string;
  subject?: string;
  pack?: boolean;
  problems?: PackProblem[];
  llm_used?: boolean;
};

type ChatMsg = { role: "user" | "assistant"; text: string };

function formatSolutionHtml(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .split("\n")
    .map((line) => {
      const t = line.trim();
      if (!t) return "<br/>";
      if (t.startsWith("## ")) return `<h3 class="sol-h">${t.slice(3)}</h3>`;
      if (t.startsWith("**") && t.endsWith("**")) {
        return `<p class="sol-strong">${t.slice(2, -2)}</p>`;
      }
      let out = t
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");
      if (out.startsWith("- ") || out.startsWith("* ")) {
        return `<p class="sol-li">• ${out.slice(2)}</p>`;
      }
      return `<p class="sol-p">${out}</p>`;
    })
    .join("");
}

export default function SolveDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const [item, setItem] = useState<Assignment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [facultyKey, setFacultyKey] = useState("");
  const [notes, setNotes] = useState("");
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [dlBusy, setDlBusy] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([
    {
      role: "assistant",
      text: "Ask anything about this solution — steps, units, or why a formula was used.",
    },
  ]);

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
  const packProblems = useMemo(
    () => (solution.pack && Array.isArray(solution.problems) ? solution.problems : []),
    [solution.pack, solution.problems],
  );
  const isPack = packProblems.length > 0;
  const answers = useMemo(() => solution.final_answers || [], [solution.final_answers]);
  const relatedNotes = useMemo(() => (solution.rag_context || []).slice(0, 3), [solution.rag_context]);
  const backendLabel =
    solution.method === "topic_solver"
      ? "Topic solvers (computed steps + diagrams)"
      : solution.llm_used
        ? "Narration: trained model / chat backend"
        : solution.method === "assignment_pack"
          ? "Pack mode · topic solvers + CAD guidance"
          : solution.method === "unsolved"
            ? "Not solved — no matching solver inputs"
            : "Legacy / formula engine";

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
      setFeedbackMsg("Thanks — your feedback was saved.");
    } catch (err) {
      setFeedbackMsg(err instanceof Error ? err.message : "Could not save feedback");
    }
  }

  async function download(kind: "pdf" | "docx" | "dxf") {
    if (!token || !item) return;
    setDlBusy(kind);
    setError(null);
    try {
      await downloadAssignmentExport(token, item.id, kind);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDlBusy(null);
    }
  }

  async function sendChat(e: FormEvent) {
    e.preventDefault();
    if (!token || !item || !chatInput.trim()) return;
    const q = chatInput.trim();
    setChatInput("");
    setChatMsgs((m) => [...m, { role: "user", text: q }]);
    setChatBusy(true);
    try {
      const { reply } = await apiChatAboutSolution(token, item.id, q);
      setChatMsgs((m) => [...m, { role: "assistant", text: reply }]);
    } catch (err) {
      setChatMsgs((m) => [
        ...m,
        {
          role: "assistant",
          text: err instanceof Error ? err.message : "Could not answer right now.",
        },
      ]);
    } finally {
      setChatBusy(false);
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
            <p className="muted">
              {item.subject || "Civil"} · {item.status === "done" ? "ready" : item.status}
              {" · "}
              {backendLabel}
            </p>
            <h1 style={{ fontSize: "2rem", maxWidth: "none" }}>{item.title}</h1>
            <div className="stack" style={{ marginTop: "1rem" }}>
              <button
                className="btn"
                type="button"
                disabled={!!dlBusy}
                onClick={() => download("pdf")}
              >
                {dlBusy === "pdf" ? "Preparing…" : "Download PDF"}
              </button>
              <button
                className="btn secondary"
                type="button"
                disabled={!!dlBusy}
                onClick={() => download("docx")}
              >
                {dlBusy === "docx" ? "Preparing…" : "Download Word"}
              </button>
              <button
                className="btn secondary"
                type="button"
                disabled={!!dlBusy}
                onClick={() => download("dxf")}
              >
                {dlBusy === "dxf" ? "Preparing…" : "Download AutoCAD (DXF)"}
              </button>
              <button className="btn secondary" type="button" onClick={() => setChatOpen(true)}>
                Ask about this solution
              </button>
            </div>
          </section>

          {isPack ? (
            <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div className="panel">
                <h2>Uploaded sheet</h2>
                <pre className="steps" style={{ maxHeight: "12rem", overflow: "auto" }}>
                  {(item.raw_text || "").slice(0, 2500)}
                  {(item.raw_text || "").length > 2500 ? "…" : ""}
                </pre>
                <p className="muted" style={{ marginTop: "0.75rem" }}>
                  Split into {packProblems.length} questions. Each card has its own write-up and
                  diagram when values are available.
                </p>
              </div>
              {packProblems.map((prob, idx) => {
                const pans = prob.final_answers || [];
                return (
                  <div className="grid-2" key={prob.id || `p-${idx}`}>
                    <div className="panel">
                      <h2>{prob.title || `Question ${idx + 1}`}</h2>
                      {prob.kind ? (
                        <p className="muted" style={{ marginBottom: "0.75rem" }}>
                          Type: {prob.kind}
                        </p>
                      ) : null}
                      <h3 style={{ fontSize: "0.95rem" }}>Question</h3>
                      <pre className="steps">{prob.question || "—"}</pre>
                      <h3 style={{ marginTop: "1.25rem", fontSize: "0.95rem" }}>Solution</h3>
                      <div
                        className="solution-body"
                        dangerouslySetInnerHTML={{
                          __html: formatSolutionHtml(
                            prob.explanation || "No written steps yet for this question.",
                          ),
                        }}
                      />
                      {pans.length ? (
                        <>
                          <h3 style={{ marginTop: "1.25rem" }}>Final answers</h3>
                          <ul className="list">
                            {pans.map((a) => (
                              <li key={a.label + String(a.value)}>
                                <span>{a.label}</span>
                                <strong className="mono">
                                  {a.value} {a.unit}
                                </strong>
                              </li>
                            ))}
                          </ul>
                        </>
                      ) : null}
                    </div>
                    <div className="panel">
                      <h2>Diagram</h2>
                      {prob.diagram_svg ? (
                        <div
                          className="diagram"
                          dangerouslySetInnerHTML={{ __html: prob.diagram_svg }}
                        />
                      ) : (
                        <p className="muted">
                          No diagram (missing values, detailing task, or not solved numerically).
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
              <form className="panel" onSubmit={(e) => sendFeedback(false, e)}>
                <h2>Was this helpful?</h2>
                <div className="field">
                  <label htmlFor="faculty-pack">Correct solution from class (optional)</label>
                  <textarea
                    id="faculty-pack"
                    value={facultyKey}
                    onChange={(e) => setFacultyKey(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="notes-pack">Notes</label>
                  <input
                    id="notes-pack"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
                <div className="stack">
                  <button className="btn" type="button" onClick={() => sendFeedback(true)}>
                    Looks correct
                  </button>
                  <button className="btn secondary" type="submit">
                    Needs correction
                  </button>
                </div>
                {feedbackMsg ? <p className="ok">{feedbackMsg}</p> : null}
              </form>
            </div>
          ) : (
          <div className="grid-2 fade-in">
            <div className="panel">
              <h2>Question</h2>
              <pre className="steps">{item.raw_text}</pre>
              <h2 style={{ marginTop: "1.5rem" }}>Solution</h2>
              <div
                className="solution-body"
                dangerouslySetInnerHTML={{
                  __html: formatSolutionHtml(solution.explanation || "No written steps yet."),
                }}
              />
              {answers.length ? (
                <>
                  <h3 style={{ marginTop: "1.25rem" }}>Final answers</h3>
                  <ul className="list">
                    {answers.map((a) => (
                      <li key={a.label + String(a.value)}>
                        <span>{a.label}</span>
                        <strong className="mono">
                          {a.value} {a.unit}
                        </strong>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="muted" style={{ marginTop: "1rem" }}>
                  Not solved numerically — no matching formula with clear inputs.
                </p>
              )}
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
                  <p className="muted">
                    No sketch — required values were not extracted, or this type has no diagram.
                  </p>
                )}
                <p className="muted" style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
                  For CAD software, use <strong>Download AutoCAD (DXF)</strong> above.
                </p>
              </div>

              {relatedNotes.length ? (
                <div className="panel">
                  <h2>Related notes</h2>
                  <ul className="list">
                    {relatedNotes.map((h) => (
                      <li key={h.source_name + h.score}>
                        <div>
                          <strong>{h.source_name}</strong>
                          <div className="muted" style={{ fontSize: "0.85rem" }}>
                            {h.content.slice(0, 160)}…
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <form className="panel" onSubmit={(e) => sendFeedback(false, e)}>
                <h2>Was this helpful?</h2>
                <p className="muted">
                  Tell us if the answer looks right. If something is wrong, you can paste the
                  correct solution from class.
                </p>
                <div className="field">
                  <label htmlFor="faculty">Correct solution from class (optional)</label>
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
                    Looks correct
                  </button>
                  <button className="btn secondary" type="submit">
                    Needs correction
                  </button>
                </div>
                {feedbackMsg ? <p className="ok">{feedbackMsg}</p> : null}
              </form>
            </div>
          </div>
          )}

          {chatOpen ? (
            <div className="chat-dock" role="dialog" aria-label="Solution chat">
              <div className="chat-head">
                <strong>Ask about this solution</strong>
                <button type="button" className="linkish" onClick={() => setChatOpen(false)}>
                  Close
                </button>
              </div>
              <div className="chat-body">
                {chatMsgs.map((m, i) => (
                  <div key={i} className={`chat-bubble ${m.role}`}>
                    {m.text}
                  </div>
                ))}
              </div>
              <form className="chat-form" onSubmit={sendChat}>
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="e.g. Why is max moment wL²/8?"
                  disabled={chatBusy}
                />
                <button className="btn" type="submit" disabled={chatBusy || !chatInput.trim()}>
                  {chatBusy ? "…" : "Send"}
                </button>
              </form>
            </div>
          ) : (
            <button type="button" className="chat-fab" onClick={() => setChatOpen(true)}>
              Chat
            </button>
          )}
        </>
      ) : null}
    </main>
  );
}
