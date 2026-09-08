import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Paperclip, X } from "lucide-react";

import { api, upload, type WorkItem } from "../lib/api";

type Ticket = WorkItem & { description: string; created_at: string; updated_at: string };
type Member = { id: string; name: string; email: string };
type Attachment = { id:string; original_name:string; size:number };
const MAX_UPLOAD_BYTES=7*1024*1024;

const states = [
  ["NEW", "Nuevo"], ["ASSIGNED", "Asignado"], ["ACCEPTED", "Aceptado"],
  ["IN_PROGRESS", "En progreso"], ["WAITING", "En espera"], ["BLOCKED", "Bloqueado"],
  ["REVIEW", "En revisión"], ["APPROVAL_REQUIRED", "Requiere aprobación"],
  ["COMPLETED", "Completado"], ["CANCELLED", "Cancelado"],
] as const;

export function TicketDetailDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const client = useQueryClient();
  const ticket = useQuery({ queryKey: ["work-item", id], queryFn: () => api<Ticket>(`/work-items/${id}`) });
  const members = useQuery({ queryKey: ["work-item-assignees"], queryFn: () => api<Member[]>("/work-item-assignees") });
  const assignees = useQuery({ queryKey: ["work-item", id, "assignees"], queryFn: () => api<Member[]>(`/work-items/${id}/assignees`) });
  const attachments = useQuery({ queryKey: ["work-item", id, "attachments"], queryFn: () => api<Attachment[]>(`/work-items/${id}/attachments`) });
  const [status, setStatus] = useState("");
  const [assigneeIds, setAssigneeIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const uploadFile=useMutation({mutationFn:(file:File)=>upload<Attachment>(`/work-items/${id}/attachments`,file),onSuccess:()=>client.invalidateQueries({queryKey:["work-item",id,"attachments"]})});

  useEffect(() => setStatus(ticket.data?.status || ""), [ticket.data?.status]);
  useEffect(() => setAssigneeIds(assignees.data?.map((member) => member.id) || []), [assignees.data]);
  const toggleAssignee = (memberId: string) => setAssigneeIds((current) => current.includes(memberId) ? current.filter((id) => id !== memberId) : [...current, memberId]);
  const save = async () => {
    const assignmentsChanged = JSON.stringify([...assigneeIds].sort()) !== JSON.stringify((assignees.data || []).map((member) => member.id).sort());
    if ((!status || status === ticket.data?.status) && !assignmentsChanged) return;
    setSaving(true); setError("");
    try {
      if (assignmentsChanged) await api(`/work-items/${id}/assignees`, { method: "PUT", body: { assignee_ids: assigneeIds } });
      if (status && status !== ticket.data?.status) await api(`/work-items/${id}/status`, { method: "POST", body: { status } });
      await Promise.all([ticket.refetch(), assignees.refetch(), client.invalidateQueries({ queryKey: ["pipeline"] }), client.invalidateQueries({ queryKey: ["my-work"] })]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo actualizar el estado."); }
    finally { setSaving(false); }
  };
  const attachmentsSection=<section className="attachments"><div className="section-title"><h3>Archivos</h3><label className="secondary upload-button"><Paperclip size={15}/> Adjuntar<input type="file" hidden onChange={event=>{const file=event.target.files?.[0];event.currentTarget.value="";if(!file)return;if(file.size>MAX_UPLOAD_BYTES){setError("El archivo supera el límite de 7 MB.");return}setError("");uploadFile.mutate(file)}}/></label></div><small className="muted">Máximo 7 MB por archivo.</small>{uploadFile.isPending&&<p>Subiendo archivo…</p>}{attachments.data?.length?<div className="file-list">{attachments.data.map(file=><a key={file.id} href={`/api/v1/attachments/${file.id}/content`} target="_blank" rel="noreferrer"><Download size={15}/>{file.original_name}<small>{(file.size/1024/1024).toFixed(1)} MB</small></a>)}</div>:<p className="muted">Sin archivos adjuntos.</p>}</section>;

  const assignmentsChanged = JSON.stringify([...assigneeIds].sort()) !== JSON.stringify((assignees.data || []).map((member) => member.id).sort());
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="dialog" role="dialog" aria-modal="true" aria-label="Detalle de tarea"><div className="dialog-head"><h2>{ticket.data?.human_readable_id || "Tarea"}</h2><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X /></button></div>{ticket.isLoading && <p>Cargando detalles…</p>}{ticket.isError && <p className="error">No se pudo cargar esta tarea.</p>}{ticket.data && <><h3>{ticket.data.title}</h3><p className="muted">{ticket.data.description || "Sin descripción."}</p><p><b>Prioridad:</b> {ticket.data.priority}</p><p><b>Fecha límite:</b> {ticket.data.due_at ? new Date(ticket.data.due_at).toLocaleString("es") : "Sin fecha"}</p><fieldset className="field"><legend>Responsables</legend>{members.isLoading && <small>Cargando miembros…</small>}{members.isError && <small className="error">No se pudieron cargar los miembros.</small>}{members.data?.map((member) => <label key={member.id}><input type="checkbox" checked={assigneeIds.includes(member.id)} onChange={() => toggleAssignee(member.id)} /> {member.name} <small>({member.email})</small></label>)}</fieldset><label className="field"><span>Estado</span><select value={status} onChange={(event) => setStatus(event.target.value)}>{states.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label><section className="attachments"><div className="section-title"><h3>Archivos</h3><label className="secondary upload-button"><Paperclip size={15}/> Adjuntar<input type="file" hidden onChange={event=>{const file=event.target.files?.[0];event.currentTarget.value="";if(!file)return;if(file.size>MAX_UPLOAD_BYTES){setError("El archivo supera el límite de 7 MB.");return;}setError("");uploadFile.mutate(file);}}/></label></div><small className="muted">Máximo 7 MB por archivo.</small>{uploadFile.isPending&&<p>Subiendo archivo…</p>}{attachments.data?.length?<div className="file-list">{attachments.data.map(file=><a key={file.id} href={`/api/v1/attachments/${file.id}/content`} target="_blank" rel="noreferrer"><Download size={15}/>{file.original_name}<small>{(file.size/1024/1024).toFixed(1)} MB</small></a>)}</div>:<p className="muted">Sin archivos adjuntos.</p>}</section><p className="error">{error || (uploadFile.error instanceof Error ? uploadFile.error.message : "")}</p><div className="dialog-actions"><button className="secondary" type="button" onClick={onClose}>Cerrar</button><button className="primary" type="button" onClick={save} disabled={saving || (status === ticket.data.status && !assignmentsChanged)}>{saving ? "Guardando…" : "Guardar cambios"}</button></div></>}</section></div>;
}
