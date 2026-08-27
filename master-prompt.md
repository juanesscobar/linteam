\# MASTER PROMPT / LINTEAM



You are a senior software architect, staff engineer, AI systems engineer, product designer, security engineer, and enterprise workflow specialist.



Your task is to design and implement a production-grade internal operations platform for \*\*Lin Group\*\*, provisionally called:



\*\*LINTEAM\*\*



The platform must NOT be designed as a simple ticketing application or Jira clone.



It must become a modular \*\*organizational operating system\*\* that connects:



\* employees;

\* departments;

\* requests;

\* tasks;

\* tickets;

\* projects;

\* approvals;

\* deliverables;

\* notifications;

\* communications;

\* workflows;

\* existing company software;

\* company data;

\* automation;

\* and eventually AI agents.



The application will initially coexist with existing production systems and MUST NOT replace or modify those systems without explicit integration boundaries.



\---



\# 1. CORE PRODUCT PRINCIPLE



Design the system around a universal entity called:



`WorkItem`



A WorkItem may represent:



\* TASK

\* REQUEST

\* TICKET

\* INCIDENT

\* APPROVAL

\* PURCHASE\_REQUEST

\* HR\_REQUEST

\* LEGAL\_REQUEST

\* COLLECTION\_CASE

\* CUSTOMER\_CASE

\* IT\_REQUEST

\* DELIVERABLE

\* FOLLOW\_UP

\* PROJECT\_TASK

\* MAINTENANCE\_REQUEST

\* COMMERCIAL\_OPPORTUNITY

\* CUSTOM



Do not hardcode business logic around only "tickets".



The architecture must allow additional WorkItem types to be configured later.



\---



\# 2. INITIAL ORGANIZATION



Create an editable organization structure for Lin Group.



Initial departments and members:



Administrative



Human Resources



\* Liz



Legal Advisory



\* Raquel



Collections



\* Juan Ayala



Customer Service



\* Griselda



Marketing



\* John



Finance



\* Nancy



Construction and Logistics



\* William

\* Houff



Purchasing



\* Claudio



Information Technology



\* Giuliano Catella

\* Juan Andrés



Commercial and Sales



\* Juan



Pawn / Empeños



Consulting



\* José



José is the CEO / executive user.



IMPORTANT:



Departments, teams, positions and users MUST NOT be hardcoded.



Administrators must be able to:



\* create departments;

\* edit departments;

\* archive departments;

\* create teams;

\* add members;

\* move members;

\* define supervisors;

\* define roles;

\* define permissions.



\---



\# 3. MULTI-TENANT READY ARCHITECTURE



Even if Lin Group is initially the only organization, design the data model to support:



Organization

BusinessUnit

Department

Team

Member



Do not prematurely implement complex SaaS billing.



However, avoid architectural decisions that would make multi-organization support impossible later.



Every business entity must be properly scoped to an organization.



\---



\# 4. USER PROFILES



Each employee must have a professional profile containing:



\* id

\* name

\* profile image

\* job title

\* organization

\* business unit

\* department

\* team

\* supervisor

\* email

\* phone

\* WhatsApp identifier

\* Telegram identifier

\* status

\* timezone

\* work schedule

\* location / branch

\* responsibilities

\* specialties

\* permissions

\* system role

\* notification preferences



Show operational information such as:



\* active assignments;

\* upcoming deadlines;

\* overdue tasks;

\* completed tasks;

\* requests created;

\* pending approvals;

\* current workload.



Do NOT expose employee performance rankings by default.



\---



\# 5. RBAC + PERMISSIONS



Implement secure role-based access control.



Example roles:



SUPER\_ADMIN

ORG\_ADMIN

EXECUTIVE

DEPARTMENT\_MANAGER

TEAM\_LEAD

EMPLOYEE

VIEWER

SYSTEM\_INTEGRATION

AGENT



Permissions must be granular.



Examples:



workitem.create

workitem.view

workitem.update

workitem.assign

workitem.delete

workitem.approve



department.manage



member.manage



workflow.manage



integration.manage



agent.manage



audit.view



analytics.view



executive.view



Never rely only on frontend permission checks.



Authorization must also be enforced server-side.



\---



\# 6. WORK ITEM MODEL



Create a flexible WorkItem domain model.



Recommended properties:



id



humanReadableId



organizationId



type



title



description



status



priority



impact



urgency



sourceDepartmentId



destinationDepartmentId



createdBy



assignedTo



followers



watchers



category



tags



location



branch



createdAt



updatedAt



startedAt



dueAt



completedAt



SLA



estimatedEffort



actualEffort



expectedDeliverable



deliverableStatus



relatedEntities



relatedWorkItems



externalReferences



customFields



metadata



The system must support:



\* comments;

\* attachments;

\* checklists;

\* subtasks;

\* dependencies;

\* mentions;

\* activity history;

\* internal notes;

\* deliverables;

\* approvals.



\---



\# 7. PRIORITY SYSTEM



Separate:



Priority



LOW

NORMAL

HIGH

CRITICAL



from:



Impact



INDIVIDUAL

TEAM

DEPARTMENT

ORGANIZATION

CUSTOMER

FINANCIAL

LEGAL

OPERATIONAL



Architecture must allow a future computed Priority Score using:



urgency

impact

deadline

financial exposure

customer impact

legal risk

operational risk



Do not make the AI score authoritative.



Allow humans to override it.



\---



\# 8. WORKFLOW ENGINE



Implement configurable workflows.



Do not hardcode every department flow.



Default workflow:



NEW

ASSIGNED

ACCEPTED

IN\_PROGRESS

WAITING

BLOCKED

REVIEW

APPROVAL\_REQUIRED

COMPLETED

REJECTED

CANCELLED

ARCHIVED



Allow specialized workflows.



Example PURCHASE workflow:



REQUESTED

QUOTING

WAITING\_APPROVAL

APPROVED

PURCHASED

IN\_TRANSIT

RECEIVED

CLOSED



Example COLLECTION workflow:



NEW

CONTACT\_REQUIRED

CONTACTED

PROMISE\_TO\_PAY

FOLLOW\_UP

PAID

ESCALATED

LEGAL

CLOSED



Each workflow must define:



states

allowed transitions

permissions

SLA

automations

notifications

approval requirements



\---



\# 9. APPROVAL ENGINE



Approvals must be first-class entities.



Support:



single approval



sequential approval



multiple approvals



manager approval



department approval



executive approval



Create:



ApprovalRequest



with:



requestedBy

requestedFrom

relatedWorkItem

reason

amount

status

createdAt

approvedAt

rejectedAt

comments



Every approval must generate audit records.



\---



\# 10. DELIVERABLES



A task being marked as completed is not equivalent to delivering the expected result.



Support:



ExpectedDeliverable



Deliverable



Examples:



PDF

document

image

report

contract

spreadsheet

link

file

text

confirmation



Allow:



submission

review

approval

rejection

revision



\---



\# 11. MOBILE-FIRST UX



Most employees may primarily use mobile devices.



Design MOBILE FIRST.



Provide:



responsive web interface



installable PWA



fast authentication



large touch targets



minimal forms



quick actions



voice-friendly interfaces



camera upload



document upload



photo evidence



push notifications



Creating a WorkItem from mobile should require minimal friction.



Primary action:



"+ Create"



Allow users to simply describe the request using natural language.



Example:



"The air conditioner at Branch 2 stopped working and we need it repaired today."



The system may suggest:



Type: INCIDENT

Department: Construction \& Logistics

Suggested Owner: William

Priority: HIGH

Deadline: TODAY



The human must confirm before creation when AI has inferred important fields.



\---



\# 12. OMNICHANNEL WORK ITEM CREATION



Implement an abstraction:



InboundChannel



Supported or planned channels:



APP

WEB

EMAIL

WHATSAPP

TELEGRAM

API

AGENT

SYSTEM



Each created WorkItem must record its source.



Example:



source:

WHATSAPP



Never bind the core WorkItem service directly to WhatsApp or Telegram.



Use adapters.



\---



\# 13. WHATSAPP INTEGRATION



Prepare integration architecture for WhatsApp Business API.



Potential interaction:



Employee:



"Necesito comprar 20 cajas de vasos para el local del centro antes del viernes."



System:



"Solicitud detectada:



20 cajas de vasos

Local Centro

Departamento: Compras

Responsable sugerido: Claudio

Fecha requerida: viernes



Create / Modify / Cancel"



Only create the request after user confirmation.



Design the system so incoming messages pass through:



Webhook

→ Channel Adapter

→ Identity Resolution

→ Intent Parser

→ Work Item Draft

→ Validation

→ User Confirmation

→ Work Item Service



\---



\# 14. TELEGRAM INTEGRATION



Create adapter architecture for Telegram Bot API.



Support future commands such as:



/new



/mytasks



/today



/urgent



/approve



/status



Also support natural language.



Examples:



"Mostrame mis tareas para hoy."



"Marcar LG-1042 como terminado."



"Asignar LG-1045 a William."



Any sensitive or destructive operation must require authorization and confirmation.



\---



\# 15. EMAIL



Implement email notifications through a provider abstraction.



Potential events:



assignment



mention



deadline approaching



overdue



approval requested



approval result



deliverable submitted



task completed



executive escalation



Allow digest notifications.



Example:



daily digest



weekly digest



critical immediately



\---



\# 16. NOTIFICATION SERVICE



Implement centralized:



NotificationService



Channels:



IN\_APP

PUSH

EMAIL

WHATSAPP

TELEGRAM



Users must configure preferences.



Example:



New assignment:

In-app + Telegram



Critical:

Push + WhatsApp



Comments:

In-app



Daily summary:

Email



Never send every notification through every channel.



Implement notification deduplication and throttling.



\---



\# 17. PERSONAL INBOX



Every user should have a simple "My Work" dashboard.



Sections:



Today



Urgent



Upcoming



Overdue



Waiting



Blocked



Approvals



Created by Me



Watching



Completed



Provide clear counters.



Avoid unnecessary project-management complexity.



\---



\# 18. EXECUTIVE DASHBOARD



Create an executive dashboard for José.



Display:



open work items



critical items



overdue



blocked



waiting approval



completed today



completed this week



department workload



deadline risk



SLA violations



approval bottlenecks



Do NOT create employee surveillance functionality.



Focus on operational health.



\---



\# 19. ASK CONCIENCIA



Prepare a conversational interface called:



Ask Conciencia



IMPORTANT:



This is NOT a separate chatbot product.



It is a transversal interface to the organizational operating system.



Initial capabilities should be READ-ONLY.



Examples:



"What tasks are overdue?"



"What is blocking Purchasing?"



"What needs my approval?"



"What does Raquel have pending this week?"



"Show critical IT issues."



"What departments have the biggest workload?"



Later versions may allow actions through:



READ

→ ANALYZE

→ RECOMMEND

→ PREPARE

→ APPROVAL

→ EXECUTE



Never allow autonomous destructive or high-impact production actions by default.



\---



\# 20. AGENT ARCHITECTURE



Create an Agent Registry.



Potential agents:



Executive Agent



Operations Agent



HR Agent



Legal Agent



Finance Agent



Collections Agent



Customer Service Agent



Marketing Agent



Purchasing Agent



IT Agent



Commercial Agent



Initially agents should:



read authorized context



summarize



classify



route



recommend



draft



detect anomalies



identify missing information



They must NOT autonomously execute consequential actions.



\---



\# 21. AGENT ROUTER



Prepare a routing mechanism.



Example:



Legal request

→ Legal Agent

→ Raquel



Purchase

→ Purchasing Agent

→ Claudio



IT incident

→ IT Agent

→ TI Team



Human Resource request

→ HR Agent

→ Liz



The routing configuration must be editable.



Do not encode employee names inside prompts.



Use organization metadata.



\---



\# 22. INTEGRATION LAYER



Existing Lin Group systems must initially remain independent.



Create:



Integration Registry



Connector interface



Potential connectors:



cafeteria\_adapter



credit\_adapter



employee\_adapter



customer\_adapter



finance\_adapter



future\_erp\_adapter



The new platform must not directly depend on their internal database schemas.



Use adapters or APIs.



Initially prefer READ-ONLY integrations.



\---



\# 23. ENTITY CONTEXT



WorkItems should be able to reference external business entities.



Examples:



customerId



creditId



branchId



employeeId



invoiceId



supplierId



projectId



saleId



contractId



Never duplicate entire external records unless necessary.



Use canonical external references.



\---



\# 24. AUTOMATION ENGINE



Create an event-driven automation architecture.



Structure:



TRIGGER

CONDITIONS

ACTIONS



Example:



WHEN:

WorkItem.created



IF:

department = LEGAL

AND priority = CRITICAL



THEN:

assign legal owner

notify legal

notify executive

set SLA



Another:



WHEN:

WorkItem.overdue



IF:

overdue > 24h



THEN:

notify owner



IF:

overdue > 48h



THEN:

notify manager



Automations must be visible, editable and auditable.



\---



\# 25. EVENT ARCHITECTURE



Create domain events such as:



WorkItemCreated



WorkItemAssigned



WorkItemAccepted



WorkItemUpdated



WorkItemBlocked



WorkItemCompleted



DeadlineApproaching



WorkItemOverdue



ApprovalRequested



ApprovalGranted



ApprovalRejected



DeliverableSubmitted



CommentCreated



AgentRecommendationCreated



IntegrationEventReceived



Use events to decouple notifications, analytics, integrations and automation.



\---



\# 26. AUDIT LOG



Auditability is mandatory.



Every meaningful action must record:



actor



actorType



action



entity



entityId



previousState



newState



timestamp



source



IP if appropriate



device/session where appropriate



Possible actorType:



HUMAN

AGENT

AUTOMATION

SYSTEM

API



Possible sources:



WEB

APP

WHATSAPP

TELEGRAM

EMAIL

API

SYSTEM



Audit records must be immutable from normal application interfaces.



\---



\# 27. ACTIVITY TIMELINE



Each WorkItem must show a human-readable timeline.



Example:



14:03

Griselda created request via WhatsApp



14:03

Conciencia suggested category: Purchasing



14:04

Assigned to Claudio



14:08

Claudio accepted



15:47

Quote uploaded



16:03

Nancy approved



16:12

Purchase initiated



\---



\# 28. SEARCH



Implement powerful search.



Support:



title



description



ID



employee



department



status



date



type



priority



tags



related entity



Later prepare semantic search over authorized content.



Semantic search must respect RBAC.



\---



\# 29. COMMAND BAR



Desktop application should provide a Command Bar.



Example shortcut:



Ctrl/Cmd + K



Actions:



Create Work Item



Search



Open Employee



Open Department



Assign



Change Status



Ask Conciencia



Go to My Work



Go to Approvals



\---



\# 30. GLOBAL CREATE



A universal create action must exist throughout the application.



"+"



Possible creation types:



Task



Request



Incident



Approval



Purchase



Customer Case



IT Issue



Project



Follow-up



The application should remember frequent actions per user.



\---



\# 31. COMMENTS + COLLABORATION



Support:



comments



mentions



replies



attachments



internal notes



activity



watchers



Example:



@Nancy can you approve this?



Mention notifications must respect notification preferences.



\---



\# 32. FILES



Allow files to be attached to:



WorkItems



comments



deliverables



approvals



profiles



projects



Use secure object storage.



Do not expose raw public URLs for private organizational documents.



Use signed URLs or equivalent authorization controls.



\---



\# 33. ANALYTICS



Build operational analytics around processes, not employee surveillance.



Metrics:



average resolution time



average first response



average approval duration



SLA compliance



tasks created



tasks completed



overdue rate



blocked rate



department workload



workflow bottlenecks



cross-department dependencies



common request categories



repeat incidents



automation rate



manual interventions



\---



\# 34. PROCESS INTELLIGENCE



Prepare architecture for future process intelligence.



Conciencia should eventually identify patterns such as:



"Purchase requests spend most of their time waiting for financial approval."



"Legal requests related to collections have increased."



"Repeated IT incidents are occurring in the same branch."



"Many repetitive tasks could potentially be automated."



Never automatically modify workflows based only on AI analysis.



Generate recommendations for human review.



\---



\# 35. DATA MODEL



Design a normalized and extensible schema for at least:



Organization



BusinessUnit



Department



Team



User



Membership



Role



Permission



WorkItem



WorkItemType



Workflow



WorkflowState



WorkflowTransition



Assignment



Comment



Attachment



Checklist



ChecklistItem



Deliverable



ApprovalRequest



Notification



NotificationPreference



Automation



AutomationRun



Integration



ExternalEntityReference



Agent



AgentCapability



AgentRun



ActivityEvent



AuditEvent



SLA



Tag



CustomField



Project



\---



\# 36. API



Create a clean API architecture.



Example:



/api/v1/auth



/api/v1/users



/api/v1/departments



/api/v1/teams



/api/v1/work-items



/api/v1/projects



/api/v1/approvals



/api/v1/notifications



/api/v1/workflows



/api/v1/automations



/api/v1/integrations



/api/v1/agents



/api/v1/search



/api/v1/analytics



/api/v1/audit



/api/v1/inbound/whatsapp



/api/v1/inbound/telegram



Do not expose internal implementation details unnecessarily.



\---



\# 37. REALTIME



Support realtime updates where useful.



Examples:



new assignments



comments



status changes



approval requests



notifications



dashboard updates



Avoid unnecessary realtime synchronization for static data.



\---



\# 38. SECURITY



This is production enterprise software.



Implement:



secure authentication



RBAC



server-side authorization



encrypted transport



secure secrets management



rate limits



input validation



CSRF protection when applicable



secure cookies when applicable



token expiration



refresh token strategy where appropriate



audit logging



secure file access



environment separation



Do not log:



passwords



auth tokens



API secrets



private message contents unnecessarily



full sensitive customer records



\---



\# 39. ENVIRONMENTS



Create strict:



development



staging



production



separation.



Never use production credentials in development.



Integrations with existing cafeteria and credit systems must first run against:



mock data



sanitized snapshots



test environments



or read-only APIs.



\---



\# 40. AI SAFETY BOUNDARY



All AI operations must pass through an authorization layer.



Agents must know:



who is asking



their permissions



organization



department



accessible entities



allowed tools



action risk



No agent receives unrestricted database access.



Create:



AgentTool



AgentPermission



AgentRun



AgentActionProposal



AgentApproval



for future use.



\---



\# 41. OBSERVABILITY



Implement:



structured logging



error tracking



request tracing



job monitoring



integration monitoring



automation monitoring



agent run monitoring



notification failures



Webhook processing should be observable and retryable.



\---



\# 42. BACKGROUND JOBS



Use asynchronous/background jobs for:



notifications



email



WhatsApp



Telegram



file processing



scheduled reminders



SLA monitoring



integration synchronization



analytics



AI processing



Do not block synchronous API requests unnecessarily.



\---



\# 43. RESILIENCE



Implement:



idempotency



retry with backoff



dead-letter strategy



webhook signature validation



duplicate webhook protection



transaction boundaries



graceful external-service failures



A WhatsApp retry must never accidentally create three duplicate tasks.



\---



\# 44. UX PRINCIPLES



The product should feel simpler than Jira.



The primary employee experience should revolve around:



My Work



Create



Inbox



Search



Notifications



The management experience should include:



Overview



Departments



Work



Projects



Approvals



Analytics



Automations



People



The system/administrative experience may include:



Organization



Workflows



Integrations



Agents



Roles



Audit



Settings



Avoid exposing technical complexity to normal users.



\---



\# 45. INITIAL NAVIGATION



Suggested navigation:



HOME



MY WORK



INBOX



WORK



PROJECTS



APPROVALS



PEOPLE



DEPARTMENTS



ANALYTICS



ASK CONCIENCIA



Admin:



WORKFLOWS



AUTOMATIONS



INTEGRATIONS



AGENTS



ROLES \& PERMISSIONS



AUDIT



SETTINGS



\---



\# 46. TECHNICAL ARCHITECTURE



Prefer a modular monolith for the first production version unless the repository already has compelling reasons for microservices.



Use clear domains/modules.



Example:



auth



organization



people



work



workflow



projects



approvals



notifications



automation



integrations



agents



analytics



audit



files



search



Do not prematurely create microservices.



Preserve boundaries that could later be extracted if required.



\---



\# 47. IMPLEMENTATION STRATEGY



Do NOT attempt to build everything immediately.



First inspect the repository.



Create:



CURRENT\_STATE.md



ARCHITECTURE.md



DATA\_MODEL.md



SECURITY\_MODEL.md



IMPLEMENTATION\_PLAN.md



Then implement incrementally.



\---



\# 48. PHASE 1 — FOUNDATION



Implement:



authentication



organization



departments



members



roles



permissions



basic WorkItem



comments



activity log



basic notifications



mobile responsive UX



\---



\# 49. PHASE 2 — OPERATIONAL WORK



Implement:



assignments



deadlines



priority



status



checklists



subtasks



attachments



mentions



personal inbox



department views



executive overview



\---



\# 50. PHASE 3 — WORKFLOW



Implement:



workflow engine



approvals



deliverables



SLA



escalations



automation rules



\---



\# 51. PHASE 4 — OMNICHANNEL



Implement:



PWA



push notifications



email adapter



Telegram adapter



WhatsApp adapter



inbound message normalization



identity resolution



\---



\# 52. PHASE 5 — INTEGRATIONS



Create read-only adapters for:



cafeteria software



credit software



Do not modify existing production systems.



Expose business context through a normalized integration layer.



\---



\# 53. PHASE 6 — CONCIENCIA



Implement:



Ask Conciencia



Agent Registry



Agent Router



Agent permissions



read-only tools



summaries



classification



routing recommendations



executive queries



\---



\# 54. PHASE 7 — CONTROLLED AGENT ACTIONS



Only after previous phases are stable:



Agent prepares action



Human reviews



Human approves



System executes



Audit logs everything



No autonomous high-impact action.



\---



\# 55. PHASE 8 — PROCESS INTELLIGENCE



Use accumulated workflow data to discover:



bottlenecks



repeated work



automation opportunities



SLA failures



cross-department friction



inefficient approval chains



Generate recommendations.



Do not automatically restructure the organization.



\---



\# 56. MVP DEFINITION



The first usable MVP must allow:



Admin creates organization structure.



Admin adds departments and employees.



Employee logs in from mobile.



Employee creates a request in under 30 seconds.



Employee can assign or route a request.



Owner receives notification.



Owner accepts task.



Users comment and attach files.



Task receives deadline and priority.



Task moves through statuses.



Deliverable can be submitted.



Manager can approve.



All actions appear in activity history.



José sees an executive dashboard.



Users see My Work.



System maintains audit logs.



Architecture is prepared for WhatsApp, Telegram and AI integration.



Do not delay this MVP because of advanced AI functionality.



\---



\# 57. INITIAL SUCCESS CRITERION



A realistic Lin Group workflow should be possible end-to-end:



Griselda identifies a problem.



↓



Creates request from phone.



↓



System routes it to the appropriate department.



↓



Responsible employee receives notification.



↓



Employee accepts.



↓



Work progresses.



↓



Relevant people collaborate.



↓



Deliverable is submitted.



↓



Approval occurs if needed.



↓



Request closes.



↓



José can see what happened.



↓



Every event remains auditable.



That complete workflow must work reliably before building advanced autonomous agents.



\---



\# 58. ENGINEERING RULES



Do not rewrite working components unnecessarily.



Do not introduce dependencies without clear justification.



Do not expose production credentials.



Do not directly couple AI providers to business logic.



Do not directly couple messaging providers to WorkItem logic.



Do not hardcode employees into routing logic.



Do not put business authorization only in the UI.



Do not mix production cafeteria/credit databases into this application's database.



Use adapters.



Maintain clear boundaries.



Prefer boring, reliable infrastructure over unnecessary complexity.



\---



\# 59. FIRST ACTION



Before coding:



1\. Inspect the repository completely.

2\. Identify the existing stack.

3\. Identify reusable components.

4\. Map current authentication and database.

5\. Identify security risks.

6\. Create the proposed architecture.

7\. Create the domain model.

8\. Create implementation phases.

9\. Identify anything that could endanger production.

10\. Then begin Phase 1.



Do not implement all phases at once.



The priority is:



SAFE

→ SIMPLE

→ WORKING

→ OBSERVABLE

→ INTEGRATED

→ INTELLIGENT

→ AUTOMATED.



Build this as the first real enterprise implementation of the broader \*\*Conciencia organizational orchestration architecture\*\*, while keeping Lin Group's operational application reliable, simple and useful even without AI.

