import { useState } from "react";
import type { ReactNode } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { api, session } from "../lib/api";

const schema = z
  .object({
    organization_code: z.string().min(2, "Ingresá el código de empresa"),
    invitation_token: z.string().min(20, "Ingresá la invitación recibida"),
    name: z.string().min(2, "Ingresá tu nombre"),
    email: z.string().email("Ingresá un correo válido"),
    password: z.string().min(12, "La contraseña debe tener al menos 12 caracteres"),
    confirm_password: z.string(),
  })
  .refine((value) => value.password === value.confirm_password, {
    message: "Las contraseñas no coinciden",
    path: ["confirm_password"],
  });

type JoinValues = z.infer<typeof schema>;

export function JoinPage() {
  const form = useForm<JoinValues>({ resolver: zodResolver(schema) });
  const [error, setError] = useState("");

  const submit = form.handleSubmit(async ({ confirm_password: _confirm, ...values }) => {
    setError("");
    try {
      const tokens = await api<{ access_token: string; refresh_token: string }>("/auth/join", {
        method: "POST",
        body: { ...values, organization_code: values.organization_code.trim().toUpperCase() },
      });
      session.save(tokens);
      window.location.assign("/app");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No pudimos crear tu usuario.");
    }
  });

  return (
    <main className="auth-page">
      <section className="auth-story">
        <strong className="logo light"><span>L</span> LINTEAM</strong>
        <div>
          <p className="eyebrow">Lin Group</p>
          <h1>Unite a tu equipo,<br /><em>de forma segura.</em></h1>
          <p>Tu invitación confirma que podés acceder a la organización.</p>
        </div>
      </section>
      <section className="auth-card">
        <strong className="logo"><span>L</span> LINTEAM</strong>
        <p className="eyebrow">Invitación de equipo</p>
        <h2>Crear mi usuario</h2>
        <p className="muted">Pedí al administrador el código y la invitación.</p>
        <form onSubmit={submit}>
          <Field label="Código de empresa" error={form.formState.errors.organization_code?.message}>
            <input autoCapitalize="characters" placeholder="LINTEAM" {...form.register("organization_code")} />
          </Field>
          <Field label="Invitación" error={form.formState.errors.invitation_token?.message}>
            <input autoComplete="one-time-code" {...form.register("invitation_token")} />
          </Field>
          <Field label="Nombre completo" error={form.formState.errors.name?.message}>
            <input autoComplete="name" {...form.register("name")} />
          </Field>
          <Field label="Correo" error={form.formState.errors.email?.message}>
            <input type="email" autoComplete="email" {...form.register("email")} />
          </Field>
          <Field label="Contraseña" error={form.formState.errors.password?.message}>
            <input type="password" autoComplete="new-password" {...form.register("password")} />
          </Field>
          <Field label="Confirmar contraseña" error={form.formState.errors.confirm_password?.message}>
            <input type="password" autoComplete="new-password" {...form.register("confirm_password")} />
          </Field>
          <button className="primary" type="submit">Crear mi usuario <span>→</span></button>
          <p className="error">{error}</p>
        </form>
        <p className="auth-link">¿Ya tenés usuario? <a href="/login">Ingresar</a></p>
      </section>
    </main>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}{error && <small className="error">{error}</small>}</label>;
}
