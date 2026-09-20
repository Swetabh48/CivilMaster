const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  college: string | null;
  is_admin: boolean;
  created_at: string;
};

export type Assignment = {
  id: string;
  title: string;
  original_filename: string | null;
  subject: string | null;
  status: string;
  raw_text: string | null;
  solution: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

function authHeaders(token?: string | null): HeadersInit {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(", ");
    }
    return JSON.stringify(data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function apiRegister(body: {
  email: string;
  password: string;
  full_name?: string;
  college?: string;
}): Promise<TokenPair> {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiLogin(body: { email: string; password: string }): Promise<TokenPair> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiMe(token: string): Promise<User> {
  const res = await fetch(`${API_URL}/api/auth/me`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiUpdateProfile(
  token: string,
  body: { full_name?: string; college?: string }
): Promise<User> {
  const res = await fetch(`${API_URL}/api/auth/me`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiChangePassword(
  token: string,
  body: { current_password: string; new_password: string }
): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/change-password`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function apiListAssignments(token: string): Promise<Assignment[]> {
  const res = await fetch(`${API_URL}/api/assignments`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiGetAssignment(token: string, id: string): Promise<Assignment> {
  const res = await fetch(`${API_URL}/api/assignments/${id}`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiSolveText(
  token: string,
  body: { title: string; text: string; subject?: string }
): Promise<Assignment> {
  const res = await fetch(`${API_URL}/api/assignments/solve-text`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiUpload(
  token: string,
  file: File,
  title?: string,
  subject?: string
): Promise<Assignment> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  if (subject) form.append("subject", subject);
  const res = await fetch(`${API_URL}/api/assignments/upload`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiFeedback(
  token: string,
  body: { assignment_id: string; is_correct: boolean; faculty_key?: string; notes?: string }
): Promise<void> {
  const res = await fetch(`${API_URL}/api/feedback`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function apiIngestCorpus(
  token: string,
  opts?: { force?: boolean; limit_files?: number; use_ocr?: boolean; only_unindexed?: boolean }
): Promise<{
  message: string;
  files_processed: number;
  chunks_created: number;
  files_skipped?: number;
  files_empty_text?: number;
  files_ocr_used?: number;
  chunks_total?: number;
}> {
  const params = new URLSearchParams();
  if (opts?.force) params.set("force", "true");
  if (opts?.limit_files) params.set("limit_files", String(opts.limit_files));
  if (opts?.use_ocr === true) params.set("use_ocr", "true");
  if (opts?.use_ocr === false) params.set("use_ocr", "false");
  if (opts?.only_unindexed) params.set("only_unindexed", "true");
  const qs = params.toString();
  const res = await fetch(`${API_URL}/api/corpus/ingest${qs ? `?${qs}` : ""}`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiCorpusStats(token: string): Promise<{
  chunks: number;
  sources: number;
  files_on_disk?: number;
  files_unindexed?: number;
  ocr_sidecars?: number;
}> {
  const res = await fetch(`${API_URL}/api/corpus/stats`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiTrainingExport(token: string): Promise<{
  count: number;
  pairs: unknown[];
  export_path?: string | null;
}> {
  const res = await fetch(`${API_URL}/api/admin/training-export?persist=true`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiCurateTraining(token: string): Promise<{
  ok: boolean;
  count?: number;
  stdout?: string;
  stderr?: string;
}> {
  const res = await fetch(`${API_URL}/api/admin/curate-training`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiHealth(): Promise<{
  status: string;
  llm_backend?: string;
  lora_adapter?: string | null;
  ollama?: boolean;
  ocr_enabled?: boolean;
}> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiListFeedback(token: string): Promise<
  Array<{
    id: string;
    assignment_id: string | null;
    is_correct: boolean;
    faculty_key: string | null;
    notes: string | null;
    review_status: string;
    question_text: string | null;
    created_at: string;
  }>
> {
  const res = await fetch(`${API_URL}/api/admin/feedback?status=pending`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function apiReviewFeedback(
  token: string,
  id: string,
  review_status: "approved" | "rejected"
): Promise<void> {
  const res = await fetch(`${API_URL}/api/admin/feedback/${id}/review`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ review_status }),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
