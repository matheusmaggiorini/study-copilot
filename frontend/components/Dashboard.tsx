"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, DashboardData, StatusData } from "@/lib/api";

const severityStyles: Record<string, string> = {
  high: "border-rose-400/40 bg-rose-500/10",
  medium: "border-amber-400/40 bg-amber-500/10",
  info: "border-sky-400/40 bg-sky-500/10",
};

export function Dashboard() {
  const [status, setStatus] = useState<StatusData | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [briefing, setBriefing] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<Array<{ role: "user" | "assistant"; text: string }>>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [loginHint, setLoginHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      await api.health();
    } catch (err) {
      setStatus(null);
      setData(null);
      throw err;
    }

    const [nextStatus, dashboard] = await Promise.all([api.status(), api.dashboard()]);
    setStatus(nextStatus);
    setData(dashboard);
  }, []);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  const weekLabel = data?.week_label ?? "esta semana";
  const weekAssignments = data?.assignments ?? [];

  async function handleSync() {
    try {
      setLoading("sync");
      setError(null);
      await api.sync();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no sync");
    } finally {
      setLoading(null);
    }
  }

  async function handleLogin() {
    try {
      setLoading("login");
      setError(null);
      setLoginHint("Abrindo navegador... faça login com sua conta da Humber (Microsoft/SSO).");
      const result = await api.login();
      setLoginHint(result.message);
      await refresh();
    } catch (err) {
      setLoginHint(null);
      setError(err instanceof Error ? err.message : "Falha no login");
    } finally {
      setLoading(null);
    }
  }

  async function handleBriefing() {
    try {
      setLoading("briefing");
      setError(null);
      const result = await api.briefing();
      setBriefing(result.briefing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no briefing");
    } finally {
      setLoading(null);
    }
  }

  async function handleChat(event: FormEvent) {
    event.preventDefault();
    if (!chatInput.trim()) return;

    const message = chatInput.trim();
    setChatInput("");
    setChatLog((prev) => [...prev, { role: "user", text: message }]);

    try {
      setLoading("chat");
      setError(null);
      const result = await api.chat(message);
      setChatLog((prev) => [...prev, { role: "assistant", text: result.reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no chat");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      <header className="glass rounded-3xl p-6 md:p-8">
        <p className="text-sm uppercase tracking-[0.2em] text-sky-300/80">Study Copilot</p>
        <h1 className="mt-2 text-3xl font-bold md:text-4xl">Bom dia. Vamos organizar seu dia?</h1>
        <p className="mt-3 max-w-2xl text-slate-300">
          Sync do Blackboard, alertas de lições, leitura de anúncios e análise de notas — tudo local e
          zero custo.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <ActionButton onClick={handleLogin} loading={loading === "login"}>
            Conectar Blackboard
          </ActionButton>
          <ActionButton onClick={handleSync} loading={loading === "sync"} variant="secondary">
            Sincronizar agora
          </ActionButton>
          <ActionButton onClick={handleBriefing} loading={loading === "briefing"} variant="secondary">
            Briefing do dia
          </ActionButton>
        </div>

        <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-400">
          <span>Sessão: {status?.session_exists ? "ativa" : "não configurada"}</span>
          <span>Ollama: {status?.ollama_available ? "online" : "offline"}</span>
          <span>Humber: {status?.blackboard_courses_url ?? "—"}</span>
        </div>

        {loginHint ? (
          <p className="mt-4 rounded-xl border border-sky-400/30 bg-sky-500/10 p-3 text-sm text-sky-100">
            {loginHint}
          </p>
        ) : null}

        {error ? <p className="mt-4 rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">{error}</p> : null}
      </header>

      <section className="grid gap-6 lg:grid-cols-3">
        <Panel title="Alertas" subtitle={`${data?.alerts.length ?? 0} · semana ${weekLabel}`} className="lg:col-span-1">
          <div className="space-y-3">
            {(data?.alerts ?? []).map((alert) => (
              <article
                key={alert.id}
                className={`rounded-2xl border p-4 ${severityStyles[alert.severity] ?? severityStyles.info}`}
              >
                <h3 className="font-semibold">{alert.title}</h3>
                <p className="mt-1 text-sm text-slate-300">{alert.message}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Lições desta semana" subtitle={`${weekAssignments.length} · ${weekLabel}`} className="lg:col-span-1">
          <ItemList
            empty="Nenhuma lição ou entrega nesta semana."
            items={weekAssignments.map((item) => ({
              title: item.title,
              meta: item.course_name,
              detail: item.due_at
                ? `Quando: ${item.due_at.slice(0, 10)}`
                : (item as { when?: string }).when
                  ? `Quando: ${(item as { when?: string }).when}`
                  : undefined,
            }))}
          />
        </Panel>

        <Panel title="Anúncios desta semana" subtitle={`${data?.announcements.length ?? 0} · ${weekLabel}`} className="lg:col-span-1">
          <ItemList
            empty="Nenhum anúncio com prazo nesta semana."
            items={(data?.announcements ?? []).map((item) => ({
              title: item.title,
              meta: item.course_name,
              detail: item.body
                ? `${(item as { when?: string }).when ? `Quando: ${(item as { when?: string }).when} · ` : ""}${item.body.slice(0, 140)}${item.body.length > 140 ? "..." : ""}`
                : (item as { when?: string }).when
                  ? `Quando: ${(item as { when?: string }).when}`
                  : undefined,
            }))}
          />
        </Panel>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <Panel title="Notas" subtitle={`${data?.grades.length ?? 0} itens com nota lançada`}>
          <ItemList
            empty="Nenhuma nota sincronizada ainda."
            items={(data?.grades ?? []).slice(0, 12).map((grade) => ({
              title: grade.item_name,
              meta: grade.course_name,
              detail: grade.percentage ?? [grade.score, grade.max_score].filter(Boolean).join(" / "),
            }))}
          />
        </Panel>

        <Panel title="Chat pessoal" subtitle="Pergunte o que fazer primeiro">
          <div className="mb-4 max-h-72 space-y-3 overflow-y-auto rounded-2xl border border-slate-700/60 bg-slate-950/40 p-4">
            {chatLog.length === 0 ? (
              <p className="text-sm text-slate-400">
                Ex.: &quot;O que preciso entregar hoje?&quot; ou &quot;Como estão minhas notas em Cálculo?&quot;
              </p>
            ) : (
              chatLog.map((entry, index) => (
                <div
                  key={`${entry.role}-${index}`}
                  className={`rounded-2xl px-4 py-3 text-sm ${
                    entry.role === "user"
                      ? "ml-8 bg-sky-500/15 text-sky-50"
                      : "mr-8 bg-violet-500/10 text-violet-50"
                  }`}
                >
                  {entry.text}
                </div>
              ))
            )}
          </div>

          <form onSubmit={handleChat} className="flex gap-2">
            <input
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Converse com seu copilot..."
              className="flex-1 rounded-2xl border border-slate-700 bg-slate-950/50 px-4 py-3 text-sm outline-none ring-sky-400 focus:ring"
            />
            <button
              type="submit"
              disabled={loading === "chat"}
              className="rounded-2xl bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-60"
            >
              Enviar
            </button>
          </form>

          {briefing ? (
            <div className="mt-4 rounded-2xl border border-violet-400/20 bg-violet-500/10 p-4 text-sm whitespace-pre-wrap text-violet-50">
              {briefing}
            </div>
          ) : null}
        </Panel>
      </section>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass rounded-3xl p-5 md:p-6 ${className}`}>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">{title}</h2>
        {subtitle ? <p className="text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function ItemList({
  items,
  empty,
}: {
  items: Array<{ title: string; meta?: string; detail?: string | null }>;
  empty: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">{empty}</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <article key={`${item.title}-${item.meta}`} className="rounded-2xl border border-slate-700/60 bg-slate-950/30 p-4">
          <h3 className="font-medium">{item.title}</h3>
          {item.meta ? <p className="text-xs uppercase tracking-wide text-sky-300/80">{item.meta}</p> : null}
          {item.detail ? <p className="mt-2 text-sm text-slate-300">{item.detail}</p> : null}
        </article>
      ))}
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  loading,
  variant = "primary",
}: {
  children: React.ReactNode;
  onClick: () => void;
  loading?: boolean;
  variant?: "primary" | "secondary";
}) {
  const styles =
    variant === "primary"
      ? "bg-sky-400 text-slate-950"
      : "border border-slate-600 bg-slate-900/60 text-slate-100";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`rounded-2xl px-4 py-2.5 text-sm font-semibold transition hover:opacity-90 disabled:opacity-60 ${styles}`}
    >
      {loading ? "Aguarde..." : children}
    </button>
  );
}
