const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Alert = {
  id: number;
  kind: string;
  severity: string;
  title: string;
  message: string;
};

export type DashboardData = {
  courses: Array<{ id: string; name: string }>;
  announcements: Array<{
    id: string;
    course_name: string;
    title: string;
    body?: string;
    posted_at?: string;
  }>;
  assignments: Array<{
    id: string;
    course_name: string;
    title: string;
    due_at?: string;
    status?: string;
  }>;
  grades: Array<{
    id: string;
    course_name: string;
    item_name: string;
    score?: string;
    max_score?: string;
    percentage?: string;
  }>;
  alerts: Alert[];
  last_sync?: { status: string; finished_at?: string; message?: string };
  week_label?: string;
};

export type StatusData = {
  session_exists: boolean;
  ollama_available: boolean;
  blackboard_login_url: string;
  blackboard_courses_url: string;
};

export type LoginStatus = {
  status: "idle" | "running" | "success" | "failed";
  message: string;
  error?: string | null;
  current_url?: string | null;
  session_exists?: boolean;
};

function parseError(detail: string, status: number): string {
  if (!detail.trim()) {
    return `Erro ${status} ao falar com o backend.`;
  }

  try {
    const parsed = JSON.parse(detail) as { detail?: string | string[] };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }
    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      return parsed.detail.join(", ");
    }
  } catch {
    // keep raw text below
  }

  return detail;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new Error(
      "Backend offline. Rode start-backend.ps1 e confira http://localhost:8000/health",
    );
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(parseError(detail, response.status));
  }

  return response.json() as Promise<T>;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const api = {
  health: () => request<{ ok: boolean }>("/health"),
  status: () => request<StatusData>("/status"),
  dashboard: () => request<DashboardData>("/dashboard"),
  sync: () => request<{ ok: boolean }>("/sync", { method: "POST" }),
  loginStatus: () => request<LoginStatus>("/auth/login/status"),
  login: async () => {
    await request<{ ok: boolean; message: string }>("/auth/login", { method: "POST" });

    for (let attempt = 0; attempt < 360; attempt += 1) {
      const status = await request<LoginStatus>("/auth/login/status");
      if (status.status === "success") {
        return { ok: true, message: status.message };
      }
      if (status.status === "failed") {
        throw new Error(status.error || status.message || "Falha ao conectar o Blackboard");
      }
      await sleep(2000);
    }

    throw new Error("Tempo esgotado. Conclua o login SSO no navegador e tente novamente.");
  },
  briefing: () => request<{ briefing: string }>("/briefing"),
  chat: (message: string) =>
    request<{ reply: string }>("/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};
