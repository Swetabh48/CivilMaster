"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export function SiteHeader() {
  const { user, logout } = useAuth();

  return (
    <header className="site-header">
      <Link href={user ? "/dashboard" : "/"} className="brand">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand.svg" alt="" width={32} height={32} className="brand-logo" />
        <span>
          <strong>CivilMaster</strong>
          <span>B.Tech Civil · formula-verified</span>
        </span>
      </Link>
      <nav className="nav">
        {user ? (
          <>
            <Link href="/dashboard">Solve</Link>
            <Link href="/history">History</Link>
            <Link href="/profile">Profile</Link>
            {user.is_admin ? <Link href="/admin">Admin</Link> : null}
            <button type="button" className="linkish" onClick={logout}>
              Sign out
            </button>
          </>
        ) : (
          <>
            <Link href="/login">Sign in</Link>
            <Link href="/register">Create account</Link>
          </>
        )}
      </nav>
    </header>
  );
}
