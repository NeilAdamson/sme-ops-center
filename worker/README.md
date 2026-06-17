# Worker Service

Background worker for SME Ops-Center asynchronous jobs.

## Current Responsibility

The worker currently handles Module A document indexing:

- Polls Redis list `doc_index_jobs`.
- Receives jobs queued by `POST /docs/move` or `POST /docs/index`.
- Imports the moved domain document into the matching Agent Search datastore.
- Polls the long-running Discovery Engine import operation.
- Updates `doc_asset.indexed_status` to `ready` or `failed`.

## Document Indexing Contract

Documents must be moved into a business-domain bucket before indexing:

```text
gs://<domain-bucket>/docs/<doc_id>/<filename>
```

The job payload includes:

```json
{
  "job_id": "uuid",
  "request_id": "uuid",
  "doc_id": 7,
  "domain": "compliance",
  "storage_uri": "gs://aiops-gc-poc-pilot-compliance-hz2xah/docs/7/example.pdf",
  "data_store_id": "aiops-gc-poc-pilot-compliance-store"
}
```

## Required Configuration

- `DATABASE_URL` — Postgres system-of-record connection.
- `REDIS_URL` — Redis queue URL, normally `redis://redis:6379/0`.
- `GOOGLE_APPLICATION_CREDENTIALS` — service account key path in local Docker.
- `GOOGLE_CLOUD_PROJECT` — GCP project ID.
- `GOOGLE_CLOUD_PROJECT_NUMBER` — numeric project number used in Agent Search resource paths.
- `DISCOVERY_ENGINE_LOCATION` — currently `global`.
- `DOC_DOMAIN_REGISTRY_PATH` — registry for domain buckets/data stores/search apps.

## Agent Search Path

Imports use the Discovery Engine parent resource:

```text
projects/<project-number>/locations/<location>/collections/default_collection/dataStores/<data_store_id>/branches/default_branch
```

The app service account needs `roles/discoveryengine.editor` to call `discoveryengine.documents.import`, and the Discovery Engine service agent needs read access to each domain bucket.
