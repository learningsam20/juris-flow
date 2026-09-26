# Kubernetes Manifests (JurisFlow)

Production-oriented manifests for the async components: **API** (FastAPI +
LangGraph), **agent runtime**, and **telemetry**.

## Layout

```
k8s/
├── namespace.yaml            # jurisflow namespace
├── configmap.yaml            # non-secret JAIL_* env
├── secrets.yaml              # Secret example (JAIL_SECRET_KEY) — replace
├── pvc.yaml                  # 10Gi data volume for SQLite
├── api-deployment.yaml       # API Deployment (2 replicas) + Service
├── agent-deployment.yaml     # Agent runtime Deployment + Service
├── telemetry-deployment.yaml # Telemetry Deployment + Service
├── hpa.yaml                  # CPU/memory autoscaling for the API
├── ingress.yaml              # TLS ingress via nginx + cert-manager
└── kustomization.yaml        # applied via kubectl -k
```

## Apply

```bash
# 1. replace jurisflow.example.com in ingress.yaml
# 2. create the real secret (never commit values):
kubectl create secret generic jurisflow-secrets \
  --namespace jurisflow \
  --from-literal=JAIL_SECRET_KEY="$(openssl rand -hex 32)"
# 3. deploy:
kubectl apply -k k8s/
```

## Notes / caveats (scaffolding, not battle-tested)

- `image:` tags are placeholders (`jurisflow/api:latest`) — replace with your
  registry, and pin a real tag in production.
- SQLite single-PVC is fine for one replica of the API; the API Deployment runs
  2 replicas but the HPA scales only on the shared volume — use PostgreSQL +
  Qdrant servers before multi-replica scale-out.
- OTel endpoint (`JAIL_OTEL_EXPORTER_OTLP_ENDPOINT`) is intentionally empty in
  the ConfigMap — point it at your collector (or the `otel-collector` compose
  service) once deployed.
- No `PodDisruptionBudget`, network policies, or pod security admission are
  defined yet — add them with your cluster's hardening baseline.

## Relate

- `docker-compose.yml` + `otel-collector-config.yml` for the local stack.
- `docs/architecture.md` for the deployment topology.