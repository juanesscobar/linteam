# Webhooks

Outgoing webhooks are signed with HMAC and delivered asynchronously.

Headers:

- `X-LinTeam-Event`
- `X-LinTeam-Delivery`
- `X-LinTeam-Timestamp`
- `X-LinTeam-Signature`

Example event names:

- `work_item.created`
- `work_item.updated`
- `work_item.assigned`
- `work_item.transitioned`
- `work_item.completed`
- `work_item.overdue`
- `comment.created`
- `approval.requested`
- `approval.approved`
- `approval.rejected`
- `deliverable.submitted`

The payload is retried with backoff and delivery attempts are persisted.
