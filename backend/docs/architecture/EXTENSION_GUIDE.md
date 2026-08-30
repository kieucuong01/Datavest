# Backend extension guide

## Add a read-only market provider

1. Implement the public data-source contract.
2. Keep provider configuration server-side.
3. Do not load user account secrets or expose private client methods.
4. Add deterministic provider and provenance tests.
5. Register the market only after import and contract tests pass.

## Add a research workflow

1. Put HTTP validation in a route and domain behavior in a service.
2. Preserve tenant ownership and point-in-time data boundaries.
3. Use Celery only for finite retryable work.
4. Add focused tests for authorization, idempotency, and persistence.
5. Expose the workflow to Agent/MCP only when it fits R/W/B/N.

## Add an MCP tool

Add the decorated function, update `MCP_TOOL_NAMES`, and keep the REST route as source of truth. The declaration/decorator parity test must remain green.
