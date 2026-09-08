import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, session } from "../lib/api";

type ServiceAccount = {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
};

type ApiKey = {
  id: string;
  service_account_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  expires_at?: string | null;
  revoked_at?: string | null;
  last_used_at?: string | null;
  created_at: string;
};

type Webhook = {
  id: string;
  name: string;
  url: string;
  events: string[];
  active: boolean;
};

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-title">
        <div>
          <p className="eyebrow">Integraciones</p>
          <h2>{title}</h2>
          <p className="muted">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

export function AdminIntegrationsPage() {
  if (!session.token) {
    window.location.assign("/login");
    return null;
  }
  const queryClient = useQueryClient();
  const [accountName, setAccountName] = useState("");
  const [accountDescription, setAccountDescription] = useState("");
  const [selectedAccount, setSelectedAccount] = useState("");
  const [keyName, setKeyName] = useState("Conciencia");
  const [scopeText, setScopeText] = useState("workitems:read");
  const [webhookName, setWebhookName] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvents, setWebhookEvents] = useState("work_item.created");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const accounts = useQuery({ queryKey: ["service-accounts"], queryFn: () => api<ServiceAccount[]>("/service-accounts") });
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: () => api<ApiKey[]>("/api-keys") });
  const webhooks = useQuery({ queryKey: ["webhooks"], queryFn: () => api<Webhook[]>("/webhooks") });

  const createAccount = useMutation({
    mutationFn: () =>
      api<ServiceAccount>("/service-accounts", {
        method: "POST",
        body: { name: accountName, description: accountDescription },
      }),
    onSuccess: async (account) => {
      setAccountName("");
      setAccountDescription("");
      setSelectedAccount(account.id);
      await queryClient.invalidateQueries({ queryKey: ["service-accounts"] });
    },
  });

  const createKey = useMutation({
    mutationFn: () =>
      api<{ full_key: string }>("/service-accounts/" + selectedAccount + "/api-keys", {
        method: "POST",
        body: {
          name: keyName,
          scopes: scopeText.split(",").map((scope) => scope.trim()).filter(Boolean),
        },
      }),
    onSuccess: async (value) => {
      setCreatedKey(value.full_key);
      await queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const createWebhook = useMutation({
    mutationFn: () =>
      api<Webhook>("/webhooks", {
        method: "POST",
        body: {
          name: webhookName,
          url: webhookUrl,
          events: webhookEvents.split(",").map((event) => event.trim()).filter(Boolean),
        },
      }),
    onSuccess: async () => {
      setWebhookName("");
      setWebhookUrl("");
      setWebhookEvents("work_item.created");
      await queryClient.invalidateQueries({ queryKey: ["webhooks"] });
    },
  });

  const activeAccounts = useMemo(() => accounts.data ?? [], [accounts.data]);

  return (
    <main className="app-content">
      <div className="heading">
        <div>
          <p className="eyebrow">Administración</p>
          <h1>Integraciones</h1>
          <p className="muted">Service accounts, API keys y webhooks salientes.</p>
        </div>
      </div>

      <Section title="Service Accounts" subtitle="Crea identidades para bots y orquestadores internos.">
        <div className="form-grid">
          <label className="field">
            <span>Nombre</span>
            <input value={accountName} onChange={(event) => setAccountName(event.target.value)} />
          </label>
          <label className="field">
            <span>Descripción</span>
            <input value={accountDescription} onChange={(event) => setAccountDescription(event.target.value)} />
          </label>
        </div>
        <button className="primary" type="button" disabled={createAccount.isPending || !accountName.trim()} onClick={() => createAccount.mutate()}>
          Crear service account
        </button>
        {accounts.data?.length ? (
          <div className="work-list">
            {accounts.data.map((account) => (
              <article className="work-row" key={account.id}>
                <div>
                  <strong>{account.name}</strong>
                  <small>
                    {account.description || "Sin descripción"} · {account.status}
                  </small>
                </div>
                <span className="pill NORMAL">{account.id.slice(0, 8)}</span>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">Todavía no hay service accounts.</p>
        )}
      </Section>

      <Section title="API Keys" subtitle="Las claves se muestran completas una sola vez y luego solo queda el prefijo.">
        <div className="form-grid">
          <label className="field">
            <span>Service account</span>
            <select value={selectedAccount} onChange={(event) => setSelectedAccount(event.target.value)}>
              <option value="">Elegí una cuenta</option>
              {activeAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Scopes</span>
            <input value={scopeText} onChange={(event) => setScopeText(event.target.value)} />
          </label>
          <label className="field">
            <span>Nombre de la key</span>
            <input value={keyName} onChange={(event) => setKeyName(event.target.value)} />
          </label>
        </div>
        <button className="primary" type="button" disabled={createKey.isPending || !selectedAccount} onClick={() => createKey.mutate()}>
          Crear API key
        </button>
        {createdKey && (
          <div className="empty" style={{ marginTop: 16 }}>
            <strong>Clave creada</strong>
            <p className="muted">{createdKey}</p>
          </div>
        )}
        {keys.data?.length ? (
          <div className="work-list">
            {keys.data.map((key) => (
              <article className="work-row" key={key.id}>
                <div>
                  <strong>{key.name}</strong>
                  <small>
                    {key.prefix} · {key.scopes.join(", ") || "sin scopes"} · {key.revoked_at ? "revocada" : "activa"}
                  </small>
                </div>
                <span className="pill NORMAL">{key.last_used_at ? "usada" : "nueva"}</span>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">Aún no hay API keys.</p>
        )}
      </Section>

      <Section title="Webhooks" subtitle="Recibí eventos firmados con HMAC y revisá su historial de entregas.">
        <div className="form-grid">
          <label className="field">
            <span>Nombre</span>
            <input value={webhookName} onChange={(event) => setWebhookName(event.target.value)} />
          </label>
          <label className="field">
            <span>URL</span>
            <input value={webhookUrl} onChange={(event) => setWebhookUrl(event.target.value)} />
          </label>
        </div>
        <label className="field">
          <span>Eventos</span>
          <input value={webhookEvents} onChange={(event) => setWebhookEvents(event.target.value)} />
        </label>
        <button className="primary" type="button" disabled={createWebhook.isPending || !webhookName.trim() || !webhookUrl.trim()} onClick={() => createWebhook.mutate()}>
          Crear webhook
        </button>
        {webhooks.data?.length ? (
          <div className="work-list">
            {webhooks.data.map((webhook) => (
              <article className="work-row" key={webhook.id}>
                <div>
                  <strong>{webhook.name}</strong>
                  <small>
                    {webhook.url} · {webhook.events.join(", ") || "todos"} · {webhook.active ? "activo" : "inactivo"}
                  </small>
                </div>
                <span className={`pill ${webhook.active ? "NORMAL" : "HIGH"}`}>{webhook.active ? "activo" : "pausado"}</span>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">Todavía no hay webhooks.</p>
        )}
      </Section>
    </main>
  );
}
