import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { api, session } from "../lib/api";

const schema = z.object({
  email: z.string().email("Ingresá un correo válido"),
  expires_in_days: z.coerce.number().int().min(1).max(30),
});

type InviteValues = z.infer<typeof schema>;
type Invitation = { email: string; organization_code: string; invitation_token: string; expires_at: string };

export function InvitePage() {
  const form = useForm<InviteValues>({
    resolver: zodResolver(schema),
    defaultValues: { expires_in_days: 7 },
  });
  const [result, setResult] = useState<Invitation | null>(null);
  const [error, setError] = useState("");

  if (!session.token) {
    window.location.assign("/login");
    return null;
  }

  const submit = form.handleSubmit(async (values) => {
    setError("");
    setResult(null);
    try {
      setResult(await api<Invitation>("/invitations", { method: "POST", body: values }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo crear la invitación.");
    }
  });

  return <main className="auth-page setup-page"><section className="auth-card"><strong className="logo"><span>L</span> LINTEAM</strong><p className="eyebrow">Administración</p><h2>Invitar a un miembro</h2><p className="muted">La invitación es de un solo uso y está vinculada al correo indicado.</p><form onSubmit={submit}><label className="field"><span>Correo del miembro</span><input type="email" {...form.register("email")} /></label><label className="field"><span>Vence en</span><select {...form.register("expires_in_days")}><option value="1">1 día</option><option value="7">7 días</option><option value="14">14 días</option><option value="30">30 días</option></select></label><button className="primary" type="submit">Generar invitación</button><p className="error">{error}</p></form>{result && <section className="card" aria-live="polite"><b>Invitación creada para {result.email}</b><p>Compartí estos valores por un canal seguro.</p><label className="field"><span>Código de empresa</span><input readOnly value={result.organization_code} /></label><label className="field"><span>Invitación</span><input readOnly value={result.invitation_token} /></label><small>Vence: {new Date(result.expires_at).toLocaleString("es")}. Se muestra una sola vez.</small></section>}<p className="auth-link"><a href="/app">Volver a LINTEAM</a></p></section></main>;
}
