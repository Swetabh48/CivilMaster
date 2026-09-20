"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";
import { apiListAssignments, type Assignment } from "@/lib/api";

export default function HistoryPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState<Assignment[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!token) return;
    apiListAssignments(token)
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [token]);

  return (
    <main className="shell">
      <SiteHeader />
      <h1>History</h1>
      <p className="lead">Recent solves for your account.</p>
      <div className="panel fade-in">
        {error ? <p className="error">{error}</p> : null}
        {!items.length && !error ? <p className="muted">No assignments yet.</p> : null}
        <ul className="list">
          {items.map((item) => (
            <li key={item.id}>
              <div>
                <Link href={`/solve/${item.id}`}>
                  <strong>{item.title}</strong>
                </Link>
                <div className="muted" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
                  {new Date(item.created_at).toLocaleString()} · {item.subject || "general"}
                </div>
              </div>
              <span className="badge">{item.status}</span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
