"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";
import { apiSolveText, apiUpload, type Assignment } from "@/lib/api";

export default function DashboardPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("Assignment");
  const [text, setText] = useState(
    "A steel bar carries axial load P = 100000 N on area A = 500 mm2. Find the axial stress."
  );
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<Assignment | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  async function solveText(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiSolveText(token, { title, text });
      setLast(result);
      router.push(`/solve/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Solve failed");
    } finally {
      setBusy(false);
    }
  }

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!token || !file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiUpload(token, file, title);
      setLast(result);
      router.push(`/solve/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <main className="shell">
        <SiteHeader />
        <p className="muted">Loading…</p>
      </main>
    );
  }

  return (
    <main className="shell">
      <SiteHeader />
      <section className="hero" style={{ paddingTop: "0.5rem" }}>
        <div className="hero-frame" style={{ padding: "1.5rem 1.5rem 1.35rem" }}>
          <p className="kicker">Assignment solver</p>
          <h1 style={{ fontSize: "1.85rem", maxWidth: "none" }}>Solve assignment</h1>
          <p className="lead">
            Paste the question or upload a PDF / image. Engine covers SoM, Concrete, and growing
            Geotech/Steel formulas — grounded in your indexed notes.
          </p>
        </div>
      </section>

      <div className="grid-2 fade-in">
        <form className="panel" onSubmit={solveText}>
          <h2>Paste text</h2>
          <div className="field">
            <label htmlFor="title">Title</label>
            <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="text">Question</label>
            <textarea id="text" value={text} onChange={(e) => setText(e.target.value)} required />
          </div>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Solving…" : "Solve with formulas"}
          </button>
        </form>

        <form className="panel" onSubmit={upload}>
          <h2>Upload file</h2>
          <p className="muted">PDF, PNG, JPG, WEBP, or TXT. Max 20 MB.</p>
          <div className="field">
            <label htmlFor="file">File</label>
            <input
              id="file"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </div>
          <button className="btn secondary" type="submit" disabled={busy || !file}>
            {busy ? "Uploading…" : "Upload & solve"}
          </button>
          {last ? (
            <p className="muted" style={{ marginTop: "1rem" }}>
              Last: <Link href={`/solve/${last.id}`}>{last.title}</Link>
            </p>
          ) : null}
        </form>
      </div>
      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
