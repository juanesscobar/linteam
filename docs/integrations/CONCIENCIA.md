# Conciencia Connector Contract

Conciencia should integrate through the API only. It must not depend on database schemas.

Recommended operations:

- Get current work
- Get overdue work
- Get department status
- Search work items
- Get work item detail
- Create work item when authorized
- Comment on work items when authorized
- Propose or execute a transition when authorized
- List approvals
- Get organizational summary

Recommended auth model:

- Start with read-only scopes
- Add create/comment/transition scopes explicitly
- Use a dedicated service account for Conciencia

Reusable client:

- `app/integrations/conciencia_client.py`
- Configure with `LINTEAM_BASE_URL` and `LINTEAM_API_KEY`
- Methods:
  - `get_me()`
  - `list_departments()`
  - `list_work_items()`
  - `get_work_item()`
  - `get_overdue_work()`
  - `get_department_work()`

Example placeholder key:

```http
X-API-Key: lt_live_conciencia_example
```
