# SDK & Ingestion Findings

Setup, authentication, and document ingestion behavior confirmed hands-on against the live HydraDB Python SDK.

---

| Finding | Expected | Found | Severity |
|---|---|---|---|
| Missing `sub_tenant_id` silently returns empty results | An omitted optional parameter defaults sensibly (e.g. to the ingested sub-tenant) | Two separate methods (`context.status()`, `query()`) silently return "not found" / empty results with no `sub_tenant_id` passed, even though the real, indexed data exists - it defaults to "search an empty scope," not "use the default." | Significant |
| Supplying an explicit id for the first time creates a duplicate | Upsert-by-filename should still apply once an explicit id is added | Re-ingesting 13 already-ingested documents with an `id` field added for the first time created 13 new records instead of updating the originals - a real trap for anyone incrementally adopting the documented metadata shape. | Significant |
| Re-ingesting a just-deleted id silently fails to appear | Re-ingesting under a known, valid id either succeeds visibly or errors clearly | Returns `success: true` with the correct id, but never appears in the dashboard, even after several minutes - a different, silent failure mode from E6001. Workaround: never reuse a just-deleted document's filename/id. | Significant |
| Deprecation notice references nonexistent fields | A deprecation notice names the fields to migrate to | `client.databases.create()` succeeds but returns a deprecation notice pointing callers to `database_metadata`/`database_metadata_schema` - neither field exists in the method's actual signature. Complying with it today would raise a `TypeError`. | Moderate |
| `document_metadata` payload shape is unforgiving | A single-document call accepts a plain object, and a malformed shape errors clearly | Requires array-wrapping even for one document (`[{...}]`, not `{...}`) - the field is actually named `file_metadata` server-side, only discoverable via the raw error text. Beyond that, a structurally-wrong-but-valid-JSON shape (missing the required `id`/`metadata` wrapper) is silently accepted with `success: true`, leaving every chunk's metadata permanently empty with no warning. | Moderate |
| E6001 storage errors are transient, not permanent | Docs describe `errored` as a terminal, real failure state | Documents intermittently surfaced `E6001` for several minutes before resolving on their own via automatic retries, with no schema or payload change needed. Worth budgeting patience for, not treating as a hard failure. | Moderate |
| Ingest ids are deterministic | No explicit id parameter suggests no built-in upsert key | A removed-then-re-ingested document under the same filename gets back the exact same id - ids are derived from filename + tenant/sub-tenant, not randomly assigned. | Informational |

---
