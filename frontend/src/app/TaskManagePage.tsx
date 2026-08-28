import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, session, type WorkItem } from "../lib/api";

export function TaskManagePage() {
  const queryClient = useQueryClient();
  const tasks = useQuery({ queryKey: ["work-items"], queryFn: () => api<WorkItem[]>("/work-items") });

  if (!session.token) {
    window.location.assign("/login");
    return null;
  }

  const remove = async (task: WorkItem) => {
    if (!window.confirm(`¿Eliminar ${task.human_readable_id}: ${task.title}? Se archivará y se conservará en el historial.`)) return;
    await api(`/work-items/${task.id}`, { method: "DELETE" });
    await queryClient.invalidateQueries({ queryKey: ["work-items"] });
  };

  return <main className="auth-page setup-page"><section className="auth-card"><strong className="logo"><span>L</span> LINTEAM</strong><p className="eyebrow">Administración</p><h2>Tareas</h2><p className="muted">Verificá o archivá tareas creadas. Archivar las quita del Kanban sin borrar su historial.</p>{tasks.isLoading && <p>Cargando tareas…</p>}{tasks.isError && <p className="error">No se pudieron cargar las tareas.</p>}<div className="work-list">{tasks.data?.filter((task) => task.status !== "ARCHIVED").map((task) => <article className="work-row" key={task.id}><b className="ref">{task.human_readable_id}</b><div><strong>{task.title}</strong><small>{task.status.replaceAll("_", " ")}</small></div><button className="secondary" type="button" onClick={() => remove(task)}>Eliminar</button></article>)}</div><p className="auth-link"><a href="/app">Volver a LINTEAM</a></p></section></main>;
}
