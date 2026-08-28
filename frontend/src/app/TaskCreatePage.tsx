import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";

import { api, session } from "../lib/api";

type Member = { id: string; name: string; email: string };
type Values = { title: string; description: string; type_code: string; priority: string; assignee_ids: string[]; due_at: string };

export function TaskCreatePage() {
  const form = useForm<Values>({ defaultValues: { title: "", description: "", type_code: "REQUEST", priority: "NORMAL", assignee_ids: [], due_at: "" } });
  const members = useQuery({ queryKey: ["work-item-assignees"], queryFn: () => api<Member[]>("/work-item-assignees") });
  const [error, setError] = useState("");

  if (!session.token) {
    window.location.assign("/login");
    return null;
  }

  const submit = form.handleSubmit(async (values) => {
    setError("");
    try {
      await api("/work-items", {
        method: "POST",
        body: { ...values, due_at: values.due_at || null },
      });
      window.location.assign("/app/my-work");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo crear la tarea.");
    }
  });

  return <main className="auth-page setup-page"><section className="auth-card"><strong className="logo"><span>L</span> LINTEAM</strong><p className="eyebrow">Nueva tarea</p><h2>¿Qué necesitás?</h2><p className="muted">Asigná uno o varios miembros; el primero será el responsable principal.</p><form onSubmit={submit}><label className="field"><span>Título</span><input autoFocus {...form.register("title", { required: true, minLength: 3 })} /></label><label className="field"><span>Descripción</span><textarea rows={4} {...form.register("description")} /></label><div className="form-grid"><label className="field"><span>Tipo</span><select {...form.register("type_code")}><option value="REQUEST">Solicitud</option><option value="TASK">Tarea</option><option value="IT_REQUEST">Soporte TI</option></select></label><label className="field"><span>Prioridad</span><select {...form.register("priority")}><option value="NORMAL">Normal</option><option value="HIGH">Alta</option><option value="CRITICAL">Crítica</option><option value="LOW">Baja</option></select></label></div><label className="field"><span>Fecha límite</span><input type="datetime-local" {...form.register("due_at")} /></label><fieldset className="field"><legend>Asignar a</legend>{members.isLoading && <small>Cargando miembros…</small>}{members.isError && <small className="error">No tenés permiso para asignar tareas.</small>}{members.data?.map((member) => <label key={member.id}><input type="checkbox" value={member.id} {...form.register("assignee_ids")} /> {member.name} <small>({member.email})</small></label>)}</fieldset><button className="primary" type="submit">Crear tarea</button><p className="error">{error}</p></form><p className="auth-link"><a href="/app">Cancelar</a></p></section></main>;
}
