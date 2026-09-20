"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [college, setCollege] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({
        email,
        password,
        full_name: fullName || undefined,
        college: college || undefined,
      });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <SiteHeader />
      <div className="panel auth-card">
        <h1>Create account</h1>
        <p className="muted">
          Password must be 12+ characters with upper, lower, digit, and special character.
        </p>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              minLength={12}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="fullName">Full name (optional)</label>
            <input
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="college">College (optional)</label>
            <input id="college" value={college} onChange={(e) => setCollege(e.target.value)} />
          </div>
          {error ? <p className="error">{error}</p> : null}
          <div className="stack" style={{ marginTop: "1rem" }}>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create account"}
            </button>
            <Link className="btn secondary" href="/login">
              Sign in
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}
