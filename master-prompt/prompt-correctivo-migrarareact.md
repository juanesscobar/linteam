LINTEAM FRONTEND RESET — MIGRATE FROM VANILLA JS TO REACT + TYPESCRIPT



You are working inside the existing LINTEAM repository.



This is a corrective architecture task.



The backend and business/domain architecture are NOT being replaced.



The current Vanilla JavaScript frontend has reached a complexity level where

continuing to patch it is producing UI state bugs, rendering conflicts and a

poor user experience.



The current frontend contains approximately:



frontend/

&#x20;   app.js

&#x20;   display.css

&#x20;   display.html

&#x20;   display.js

&#x20;   icon.svg

&#x20;   index.html

&#x20;   manifest.webmanifest

&#x20;   styles.css

&#x20;   sw.js



The current implementation exhibits real production-facing problems:



\- unauthenticated Login and authenticated App Shell render simultaneously;

\- pages are effectively appearing vertically stacked;

\- session expiration leaves internal UI visible;

\- Create Ticket / WorkItem UI can become stuck open;

\- Close buttons sometimes do not work;

\- navigation has weak state management;

\- a growing app.js is responsible for too many UI concerns;

\- visual consistency is poor;

\- routing/layout boundaries are weak;

\- the current UI still resembles an engineering prototype;

\- adding Pipeline did not solve the underlying frontend architecture.



DO NOT continue patching the existing architecture.



Migrate the frontend deliberately to React.



==================================================

1\. PRESERVE THE BACKEND

==================================================



DO NOT rewrite:



FastAPI

PostgreSQL

SQLAlchemy

Alembic

domain models

working API contracts

authentication security

workflow engine

audit architecture



The frontend must consume the existing FastAPI API.



Only make backend changes when genuinely required to support a correct

frontend contract.



Document every required backend change.



==================================================

2\. TARGET FRONTEND STACK

==================================================



Migrate to:



React

TypeScript

Vite



React Router



TanStack Query



React Hook Form



Zod



Tailwind CSS



shadcn/ui / Radix primitives where appropriate



Lucide icons



dnd-kit for Pipeline drag and drop



Vite PWA integration where compatible



Do NOT add Redux unless a demonstrated state-management requirement exists.



Prefer:



server state → TanStack Query



local UI state → React state/context



forms → React Hook Form



validation → Zod



==================================================

3\. MIGRATION PRINCIPLE

==================================================



Do NOT simply create React components while the old frontend continues to

render.



React must become the authoritative presentation layer.



There must be ONE application root.



Example:



<div id="root"></div>



React mounts once.



Remove competing render systems after migration.



The old app.js must not remain responsible for rendering the new UI.



==================================================

4\. FIRST AUDIT THE EXISTING FRONTEND

==================================================



Inspect:



frontend/index.html

frontend/app.js

frontend/styles.css

frontend/display.html

frontend/display.js

frontend/display.css

frontend/sw.js



Identify:



authentication implementation

API client calls

existing endpoints

token/session handling

organization setup logic

WorkItem creation

Pipeline behavior

existing forms

notifications

display mode

existing useful logic that can be reused



Create:



docs/frontend/VANILLA\_TO\_REACT\_MIGRATION.md



Map:



OLD FEATURE

→

NEW REACT MODULE



Do NOT stop after documentation.



Proceed with migration.



==================================================

5\. NEW FRONTEND STRUCTURE

==================================================



Create a maintainable feature-oriented architecture.



Adapt if necessary, but target approximately:



frontend/

&#x20;   src/

&#x20;       app/

&#x20;           router.tsx

&#x20;           providers.tsx



&#x20;       layouts/

&#x20;           AuthLayout.tsx

&#x20;           AppLayout.tsx

&#x20;           DisplayLayout.tsx



&#x20;       features/

&#x20;           auth/

&#x20;           onboarding/

&#x20;           dashboard/

&#x20;           work/

&#x20;           pipeline/

&#x20;           inbox/

&#x20;           approvals/

&#x20;           people/

&#x20;           departments/

&#x20;           notifications/

&#x20;           search/

&#x20;           conciencia/

&#x20;           display/



&#x20;       components/

&#x20;           ui/

&#x20;           navigation/

&#x20;           work-items/



&#x20;       lib/

&#x20;           api/

&#x20;           auth/

&#x20;           permissions/

&#x20;           query-client/



&#x20;       hooks/



&#x20;       types/



&#x20;       styles/



&#x20;       main.tsx



Do not create unnecessary abstraction layers.



==================================================

6\. ROUTING MUST BE EXPLICIT

==================================================



Implement actual routes.



PUBLIC:



/login



/join



/setup



AUTHENTICATED:



/app



/app/my-work



/app/pipeline



/app/inbox



/app/work



/app/work/:workItemId



/app/approvals



/app/people



/app/people/:memberId



/app/departments



/app/departments/:departmentId



/app/search



/app/conciencia



/app/summary



DISPLAY:



/display/operations



ADMIN:



/app/admin/\*



according to permissions.



==================================================

7\. AUTH ROUTE GUARDS

==================================================



Implement:



<PublicRoute />

<ProtectedRoute />

<PermissionRoute />



Unauthenticated users must NEVER render AppLayout.



Pseudo behavior:



if authentication loading:

&#x20;   render session loading state



if unauthenticated:

&#x20;   redirect to /login



if authenticated:

&#x20;   render AppLayout



When a token/session expires:



clear auth session



invalidate authenticated queries



redirect to /login



show:



"Tu sesión expiró. Iniciá sesión nuevamente."



NEVER leave AppLayout visible behind login.



==================================================

8\. ORGANIZATION ONBOARDING MODEL

==================================================



Change the current UX model.



There are three distinct concepts:



ORGANIZATION SETUP



MEMBER JOIN



LOGIN



They MUST NOT be the same screen.



\------------------------------------------

/setup

\------------------------------------------



Used by the technical administrator / organization owner.



Fields may include:



Organization name

Organization code/slug

Initial administrator

Bootstrap credentials



This route should only be available when initialization is allowed.



\------------------------------------------

/join

\------------------------------------------



Used by employees joining an existing organization.



Example:



Código de empresa

Correo

Contraseña or activation credential



The user must NOT enter the database Organization UUID.



Use a human-friendly:



organizationCode



and optionally:



inviteCode



or existing invitation.



Knowing the organization code alone MUST NOT grant membership.



Validate:



organization

invitation / authorized email / join token

membership



\------------------------------------------

/login

\------------------------------------------



Normal everyday login.



ONLY:



Correo

Contraseña



\[Ingresar]



Optional:



Recordar sesión



¿Olvidaste tu contraseña?



No Organization ID.



No bootstrap.



No administrator setup.



==================================================

9\. LIN GROUP INITIAL CONFIGURATION

==================================================



Support an organization like:



Name:

Lin Group



Code:

LINTEAM



Internal organization UUID:

server-managed



Employees may initially join through:



organization code + authorized invitation



After membership exists, normal login requires only:



email

password



The application determines the user's organizations from membership.



If a user ever belongs to multiple organizations, show an organization

selector AFTER authentication.



Do not make ordinary users memorize technical IDs.



==================================================

10\. APP LAYOUT

==================================================



Build a polished operational shell.



Desktop:



Sidebar

Topbar

Main



Sidebar approximately 240px.



Topbar approximately 60px.



Main content fills remaining space.



The entire application must NOT appear as one long vertical document.



The document body must not contain multiple route pages stacked together.



==================================================

11\. SIDEBAR

==================================================



LINTEAM



PRINCIPAL

Inicio

Mi trabajo

Inbox



TRABAJO

Pipeline

Trabajo

Proyectos

Aprobaciones



ORGANIZACIÓN

Personas

Áreas



INTELIGENCIA

Resumen

Ask Conciencia



ADMIN

only when permitted.



Use React Router navigation.



Active states must derive from the current route.



==================================================

12\. TOPBAR

==================================================



Include:



Search / Command button



\+ Crear



Notifications



Current user avatar/name



User menu



Logout



Every button must work.



Do not render placeholder controls that cannot be closed or activated.



==================================================

13\. FIX MODAL / DRAWER ARCHITECTURE

==================================================



The current Create Ticket interaction can become impossible to close.



This must never happen in the React implementation.



Use an accessible Dialog/Sheet primitive.



Create:



<CreateWorkItemDialog />



or mobile:



<CreateWorkItemSheet />



Controlled state:



const \[open, setOpen] = useState(false)



Opening:



setOpen(true)



Closing through X:



setOpen(false)



Closing through Cancel:



setOpen(false)



Closing through Escape:



supported on desktop



Closing through outside interaction:



use sensible Dialog behavior



Successful creation:



mutation succeeds

→ invalidate relevant WorkItem queries

→ close dialog

→ success feedback



Failed creation:



keep dialog open

show error

preserve entered form data



Closing without creating:



MUST work.



Test this explicitly.



==================================================

14\. GLOBAL CREATE UX

==================================================



Desktop:



\+ Crear



Mobile:



prominent center / primary action.



Open a simple creation experience.



First screen:



¿Qué necesitás?



Description input.



Then:



Type

Area

Assignee

Priority

Deadline



Advanced fields should be optional/collapsible.



Do not force employees to complete a complex enterprise form for simple

requests.



==================================================

15\. HOME DASHBOARD

==================================================



/app



Must contain useful operational information.



Example:



Buenos días, Juan



Esto requiere tu atención hoy.



Today

Urgent

Due soon

Overdue



Then:



My Work



Recent Activity



Approvals if relevant



Use designed empty states.



NEVER leave a giant blank content panel.



==================================================

16\. PIPELINE / KANBAN

==================================================



/app/pipeline



Implement as a genuine Kanban representation of WorkflowState.



React component model approximately:



<PipelineBoard>

&#x20;   <PipelineColumn>

&#x20;       <WorkItemCard />

&#x20;   </PipelineColumn>

</PipelineBoard>



Use dnd-kit.



Columns are generated dynamically from backend workflow states.



Example:



NEW

ASSIGNED

IN\_PROGRESS

REVIEW

COMPLETED



Dragging a WorkItem requests a backend transition.



Frontend state is NOT authoritative.



Backend validates:



permissions

allowed transitions

approvals

deliverables

workflow rules



If denied:



rollback UI

show readable message.



==================================================

17\. PIPELINE CARD

==================================================



Display:



LG-1042



Repair air conditioner



Construction \& Logistics



William



Priority



Due date



Use subtle badges.



Do not overload cards.



==================================================

18\. LIST + PIPELINE

==================================================



Work should support:



List

Pipeline



Do not force Kanban for every workflow.



Remember user preference where appropriate.



==================================================

19\. MOBILE UX

==================================================



Mobile architecture must differ from desktop.



Do NOT shrink sidebar.



Use bottom navigation approximately:



Inicio

Trabajo

Crear

Inbox

Más



Mobile primary work view:



status-grouped list



Cards approximately full width.



Provide:



Change status



instead of depending on drag.



Optional horizontal pipeline remains available.



==================================================

20\. TV DISPLAY

==================================================



Migrate the existing display implementation into React.



Route:



/display/operations



Use:



DisplayLayout



No sidebar.



No editing.



Large typography.



Visible from several meters.



Pipeline visualization.



Counters:



Open

In progress

Blocked

Overdue

Completed today



Respect confidentiality.



Do not expose:



HR private data

credit/customer private data

legal confidential titles

private comments

financial sensitive information



==================================================

21\. RESPONSIVE LAYOUT

==================================================



Test:



360px

390px

430px

768px

1024px

1366px

1440px

1920px



Avoid:



long stacked desktop layouts

page-level horizontal overflow

giant empty areas

tiny mobile controls



==================================================

22\. DESIGN SYSTEM

==================================================



Implement semantic tokens through Tailwind/theme variables.



Visual direction:



professional enterprise productivity



deep LinTeam green

neutral backgrounds

white surfaces

lime accent sparingly



Subtle borders.



Good typography.



Moderate radius.



Minimal shadows.



No giant green empty canvas.



No excessive cards.



No gradients unless extremely subtle and justified.



No glassmorphism.



==================================================

23\. UI PRIMITIVES

==================================================



Use reliable primitives for:



Button

Input

Textarea

Select

Dialog

Sheet

Dropdown

Tooltip

Popover

Tabs

Badge

Avatar

Toast

Command

Skeleton

Alert



Do NOT rebuild accessibility-sensitive components using manual DOM logic

unless necessary.



==================================================

24\. QUERY ARCHITECTURE

==================================================



Use TanStack Query for server state.



Example keys:



\['me']



\['organization']



\['work-items', filters]



\['work-item', id]



\['pipeline', workflow]



\['notifications']



\['departments']



\['people']



After WorkItem creation:



invalidate relevant queries.



After transition:



invalidate work item

pipeline

my work

dashboard



Do not manually synchronize copies of server state across unrelated DOM

elements.



==================================================

25\. API CLIENT

==================================================



Create a typed central API layer.



Example:



apiClient



authApi



workItemsApi



organizationsApi



peopleApi



workflowsApi



notificationsApi



Do not scatter fetch() calls across components.



Handle:



401

403

404

409

422

500



centrally where appropriate.



401:



session invalidation and redirect.



==================================================

26\. FORM VALIDATION

==================================================



Use:



React Hook Form

\+

Zod



Share validation concepts with backend schemas when practical.



Human-readable Spanish messages.



Example:



"La fecha límite no puede ser anterior a hoy."



Do not expose raw FastAPI validation structures to users.



==================================================

27\. LOADING / ERROR / EMPTY STATES

==================================================



Every asynchronous view requires:



loading

error

empty

success



No blank screens.



Examples:



Loading:

skeleton



Error:

"No pudimos cargar el Pipeline."

\[Reintentar]



Empty:

"No hay trabajos en esta etapa."



==================================================

28\. NOTIFICATIONS / FEEDBACK

==================================================



Use toasts for lightweight confirmation.



Examples:



"Solicitud creada"



"Estado actualizado"



"Asignado a William"



Do not use alert().



Do not use technical console output as user feedback.



==================================================

29\. ACCESSIBILITY

==================================================



Keyboard navigation.



Visible focus.



Semantic labels.



Dialog focus trapping.



Escape closes dismissible dialogs.



44px touch targets.



Do not rely only on color.



==================================================

30\. REMOVE OLD FRONTEND

==================================================



After feature parity is reached and React works:



remove or archive obsolete:



app.js

old rendering code

unused CSS

display.js

display.html



Do not keep the old frontend mounted alongside React.



Preserve:



manifest

service worker concepts

icons



only if migrated correctly.



==================================================

31\. MIGRATION SAFETY

==================================================



Perform migration incrementally.



Do not delete the working frontend before equivalent React functionality

exists.



Use Git checkpoints.



Recommended:



checkpoint 1

React bootstrapped



checkpoint 2

auth working



checkpoint 3

AppLayout



checkpoint 4

WorkItems



checkpoint 5

Pipeline



checkpoint 6

mobile



checkpoint 7

display



Then remove obsolete frontend.



==================================================

32\. TESTS

==================================================



Add frontend tests for critical UI behavior.



At minimum:



unauthenticated user sees only Login



authenticated user sees only AppLayout



expired session redirects to Login



Create WorkItem opens



X closes Create WorkItem



Cancel closes Create WorkItem



failed create does not close unexpectedly



successful create closes and refreshes work



Pipeline renders states



valid transition works



invalid transition rolls back



Logout works



==================================================

33\. E2E ACCEPTANCE

==================================================



Run the actual application.



Do not consider compilation sufficient.



Use available browser/E2E tooling if present.



Test this workflow:



LOGIN



→ Home



→ Create



→ close without creating



→ reopen



→ create WorkItem



→ see WorkItem



→ Pipeline



→ move WorkItem



→ open details



→ logout



Then:



JOIN employee



→ login



→ access only authorized Lin Group workspace



Then:



TV Display



→ verify large safe pipeline.



==================================================

34\. CRITICAL VISUAL ACCEPTANCE

==================================================



The migration is NOT complete if the rendered application still resembles

the current screenshot.



Specifically reject the result if:



Login and App appear on one long page.



Organization setup appears under login.



Sidebar is a plain HTML list.



Content is mostly empty white space.



Create modal cannot reliably close.



Pipeline is not visibly Kanban.



Mobile merely shrinks desktop.



The application feels like a static admin prototype.



==================================================

35\. FINAL PRODUCT EXPECTATION

==================================================



LINTEAM should feel like an actual organizational operating system.



An employee should immediately understand:



What do I need to do?



A department manager:



What is happening in my area?



José:



What is happening across Lin Group?



And the software team should be able to evolve the frontend without

turning one app.js file into the state manager, router, renderer, API client,

modal manager and workflow UI simultaneously.



FIRST inspect the repository and existing backend contracts.



THEN create the migration plan.



THEN execute the migration.



DO NOT stop at the plan.



RUN the application and visually verify the result before declaring the

migration complete.

