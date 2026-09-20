"use client";

import Link from "next/link";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { user, loading } = useAuth();

  return (
    <main className="shell">
      <SiteHeader />
      <section className="hero">
        <div className="hero-frame">
          <p className="kicker">Civil engineering workspace</p>
          <h1>CivilMaster</h1>
          <p className="lead">
            Upload a B.Tech assignment. Get step-by-step solutions grounded in verified
            formulas and your semester notes — not guessed chatbot arithmetic.
          </p>
          <div className="stack">
            {!loading && user ? (
              <Link className="btn" href="/dashboard">
                Open solver
              </Link>
            ) : (
              <>
                <Link className="btn" href="/register">
                  Create account
                </Link>
                <Link className="btn secondary" href="/login">
                  Sign in
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="feature-row fade-in">
        <div className="feature">
          <h3>Verified formulas</h3>
          <p>SoM and Concrete equations run in a deterministic engine with unit checks.</p>
        </div>
        <div className="feature">
          <h3>Your corpus</h3>
          <p>Retrieves matching notes, labs, and books from your civil semester materials.</p>
        </div>
        <div className="feature">
          <h3>Lab diagrams</h3>
          <p>SVG sketches for beams, sections, and RCC detailing driven by solved numbers.</p>
        </div>
      </section>
    </main>
  );
}
