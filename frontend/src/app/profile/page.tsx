"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SiteHeader } from "@/components/SiteHeader";
import { useAuth } from "@/lib/auth";
import { apiChangePassword, apiUpdateProfile } from "@/lib/api";

export default function ProfilePage() {
  const { user, token, loading, refreshUser } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [college, setCollege] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setCollege(user.college || "");
    }
  }, [user]);

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setMessage(null);
    try {
      await apiUpdateProfile(token, { full_name: fullName, college });
      await refreshUser();
      setMessage("Profile updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setMessage(null);
    try {
      await apiChangePassword(token, {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Password changed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed");
    }
  }

  if (!user) {
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
      <h1>Profile</h1>
      <div className="grid-2 fade-in">
        <form className="panel" onSubmit={saveProfile}>
          <h2>Account</h2>
          <div className="field">
            <label>Email</label>
            <input value={user.email} disabled />
          </div>
          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="college">College</label>
            <input id="college" value={college} onChange={(e) => setCollege(e.target.value)} />
          </div>
          <button className="btn" type="submit">
            Save profile
          </button>
        </form>

        <form className="panel" onSubmit={changePassword}>
          <h2>Password</h2>
          <div className="field">
            <label htmlFor="current">Current password</label>
            <input
              id="current"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="next">New password</label>
            <input
              id="next"
              type="password"
              minLength={12}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn secondary" type="submit">
            Change password
          </button>
        </form>
      </div>
      {message ? <p className="ok">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </main>
  );
}
