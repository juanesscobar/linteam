import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";

import { api, type WorkItem } from "../lib/api";

type Ticket = WorkItem & { description: string; created_at: string; updated_at: string };

const states = [
  ["NEW", "Nuevo"], ["ASSIGNED", "Asignado"], ["ACCEPTED", "Aceptado"],
  ["IN_PROGRESS", "En progreso"], ["WAITING", "En espera"], ["BLOCKED", "Bloqueado"],
  ["REVIEW", "En revisión"], ["APPROVAL_REQUIRED", "Requiere aprobación"],
  ["COMPLETED", "Completado"], ["CANCELLED", "Cancelado"],
] as const;

export function TicketDetailDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const client = useQueryClient();
  const ticket = useQuery({ queryKey: ["work-item", id], queryFn: () => api<Ticket>(`/work-items/${id}`) });
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => setStatus(ticket.data?.status || ""), [ticket.data?.status]);
  const save = async () => {
    if (!status || status === ticket.data?.status) return;
    setSaving(true); setError("");
    try {
      await api(`/work-items/${id}/status`, { method: "POST", body: { status } });
      await Promise.all([ticket.refetch(), client.invalidateQueries({ queryKey: ["pipeline"] }), client.invalidateQueries({ queryKey: ["my-work"] })]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo actualizar el estado."); }
    finally { setSaving(false); }
  };

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="dialog" role="dialog" aria-modal="true" aria-label="Detalle de tarea"><div className="dialog-head"><h2>{ticket.data?.human_readable_id || "Tarea"}</h2><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X /></button></div>{ticket.isLoading && <p>Cargando detalles…</p>}{ticket.isError && <p className="error">No se pudo cargar esta tarea.</p>}{ticket.data && <><h3>{ticket.data.title}</h3><p className="muted">{ticket.data.description || "Sin descripción."}</p><p><b>Prioridad:</b> {ticket.data.priority}</p><p><b>Fecha límite:</b> {ticket.data.due_at ? new Date(ticket.data.due_at).toLocaleString("es") : "Sin fecha"}</p><label className="field"><span>Estado</span><select value={status} onChange={(event) => setStatus(event.target.value)}>{states.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label><p className="error">{error}</p><div className="dialog-actions"><button className="secondary" type="button" onClick={onClose}>Cerrar</button><button className="primary" type="button" onClick={save} disabled={saving || status === ticket.data.status}>{saving ? "Guardando…" : "Guardar estado"}</button></div></>}</section></div>;
}
