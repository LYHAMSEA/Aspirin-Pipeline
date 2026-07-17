# ChemOps: Docker Compose → Kubernetes migration guide

Follow these steps in order. Each step builds on the previous one.

---

## Step 0 — Prerequisites

You need a running Kubernetes cluster and `kubectl` configured to talk to it.

```bash
# Verify kubectl can reach your cluster
kubectl cluster-info

# Verify you have a default storage class (needed for PVCs)
kubectl get storageclass
```

If you don't have a cluster yet, the simplest paths are:
- **Local testing**: `minikube start` or `kind create cluster`
- **Cloud (cheap)**: DigitalOcean Kubernetes (DOKS) or Civo — both ~£10/month for a small cluster
- **Cloud (free tier)**: Google Kubernetes Engine (GKE) Autopilot has a free tier

---

## Step 1 — Create the namespace

```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl get namespaces
# You should see "chemops" in the list
```

Everything in this migration lives inside the `chemops` namespace — this keeps it isolated from other workloads on the cluster and makes cleanup trivial (`kubectl delete namespace chemops` removes everything).

---

## Step 2 — Create the application ConfigMap

This replaces the non-secret `CHEMOPS_*` values from your `.env`.

```bash
kubectl apply -f k8s/base/configmap-app.yaml
kubectl get configmap chemops-config -n chemops -o yaml
```

---

## Step 3 — Create the Secret (DO NOT use the template file directly)

Never commit real secrets to Git, even in a k8s manifest. Create the Secret directly with kubectl:

```bash
# Generate a real secret key first
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

kubectl create secret generic chemops-secrets \
  --namespace=chemops \
  --from-literal=CHEMOPS_SECRET_KEY="$SECRET_KEY" \
  --from-literal=DATABASE_URL="sqlite+aiosqlite:///./chemops.db" \
  --from-literal=GF_SECURITY_ADMIN_USER="admin" \
  --from-literal=GF_SECURITY_ADMIN_PASSWORD="your_strong_password_here" \
  --from-literal=ALERTMANAGER_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/your/webhook/url"

# Verify it was created (values are base64-encoded, not shown in plain text)
kubectl get secret chemops-secrets -n chemops
```

`k8s/base/secret-template.yaml` exists only as documentation of which keys are required — it is never applied with `kubectl apply -f`.

---

## Step 4 — Deploy the ChemOps API

```bash
kubectl apply -f k8s/base/api-deployment.yaml

# Watch the pods come up
kubectl get pods -n chemops -w
# Press Ctrl+C once both pods show "Running" and "2/2 Ready" (if using 2 replicas)

# Check logs
kubectl logs -n chemops -l app=chemops-api --tail=50
```

### Test it from inside the cluster

```bash
# Run a temporary pod to curl the service
kubectl run -n chemops curltest --rm -it --image=curlimages/curl --restart=Never -- \
  curl http://chemops-api:8000/healthz
```

---

## Step 5 — Deploy Prometheus

The Prometheus config (scrape targets + alert rules) is already converted into a ConfigMap using Kubernetes-native service DNS names.

```bash
kubectl apply -f k8s/configmaps/prometheus-config.yaml
kubectl apply -f k8s/base/prometheus.yaml

kubectl get pods -n chemops -l app=prometheus

# Port-forward to check it locally before setting up Ingress
kubectl port-forward -n chemops svc/prometheus 9090:9090
# Open http://localhost:9090 -> Status -> Targets
# "chemops-api" should show State = UP
```

---

## Step 6 — Generate the Grafana dashboard ConfigMap from your existing JSON

This is the one step that is NOT a plain `kubectl apply` — your dashboard JSON
file becomes a ConfigMap generated directly from the file on disk:

```bash
kubectl create configmap grafana-dashboard-chemops \
  --namespace=chemops \
  --from-file=monitoring/grafana/dashboards/chemops_main.json
```

This avoids embedding a large JSON blob inside a YAML file (error-prone with
quoting/escaping). If you update the dashboard later, delete and recreate:

```bash
kubectl delete configmap grafana-dashboard-chemops -n chemops
kubectl create configmap grafana-dashboard-chemops -n chemops \
  --from-file=monitoring/grafana/dashboards/chemops_main.json
kubectl rollout restart deployment/grafana -n chemops
```

---

## Step 7 — Deploy Grafana

```bash
kubectl apply -f k8s/configmaps/grafana-provisioning.yaml
kubectl apply -f k8s/base/grafana.yaml

kubectl get pods -n chemops -l app=grafana

# Port-forward to check it
kubectl port-forward -n chemops svc/grafana 3000:3000
# Open http://localhost:3000
# Login with the GF_SECURITY_ADMIN_USER/PASSWORD you set in step 3
# Dashboards -> ChemOps folder -> "ChemOps - Lab Orchestration"
```

---

## Step 8 — Trigger protocol runs and verify the full stack

```bash
# Port-forward the API
kubectl port-forward -n chemops svc/chemops-api 8000:8000

# In another terminal — trigger 10 runs
for i in $(seq 1 10); do
  curl -s -X POST http://localhost:8000/runs \
    -H "Content-Type: application/json" \
    -d '{"protocol":"aspirin_synthesis"}' > /dev/null
  echo "Triggered run $i"
  sleep 3
done
```

Watch the Grafana dashboard (port-forwarded at localhost:3000) — temperature
gauges, yield trends, and step duration heatmaps should populate exactly as
they did under Docker Compose.

---

## Step 9 — Expose everything externally with Ingress (optional but recommended)

```bash
# One-time: install an ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/cloud/deploy.yaml

# One-time: install cert-manager for automatic HTTPS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# Edit k8s/base/ingress.yaml — replace chemops.example.com with your real domain
kubectl apply -f k8s/base/ingress.yaml

# Point your domain's DNS A record to the Ingress controller's external IP:
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

---

## Step 10 — Enable autoscaling (optional)

```bash
kubectl apply -f k8s/base/hpa.yaml
kubectl get hpa -n chemops
# As CPU usage on chemops-api pods rises above 70%, k8s adds pods automatically
```

---

## Step 11 — Wire up CI/CD for automatic deploys

1. Generate a kubeconfig with deploy-only permissions (or use your existing one for now)
2. Base64 encode it: `cat ~/.kube/config | base64 -w 0`
3. Add it as a GitHub Secret named `KUBE_CONFIG`
4. Paste the contents of `k8s/ci_deploy_block.yml` into `.github/workflows/ci.yml`
   after your existing `build` job

Every push to `main` will now: lint → test → build & push image → deploy to
Kubernetes → wait for rollout → verify pods are running.

---

## Step 12 — Apply everything at once going forward

Once the Secret (step 3) and dashboard ConfigMap (step 6) exist, every future
change to the rest of the stack is a single command:

```bash
kubectl apply -k k8s/base
```

This is what the CI deploy job runs automatically.

---

## Mapping cheat sheet — Compose to Kubernetes

| Docker Compose concept | Kubernetes equivalent | File |
|---|---|---|
| `services:` | `Deployment` + `Service` | `*.yaml` per component |
| `.env` (non-secret values) | `ConfigMap` | `configmap-app.yaml` |
| `.env` (secrets) | `Secret` | created via `kubectl create secret` |
| `volumes:` (named volumes) | `PersistentVolumeClaim` | inside `prometheus.yaml`, `grafana.yaml` |
| bind-mounted config files | `ConfigMap` mounted as volume | `configmaps/*.yaml` |
| `depends_on: condition: service_healthy` | `readinessProbe` | every Deployment |
| `restart: unless-stopped` | default Pod restart policy | automatic |
| `ports:` host mapping | `Service` (ClusterIP) + `Ingress` | `ingress.yaml` |
| `docker compose up -d` | `kubectl apply -k k8s/base` | — |
| `docker compose logs -f` | `kubectl logs -f -n chemops -l app=chemops-api` | — |
| `docker compose exec` | `kubectl exec -it -n chemops <pod>` | — |
| (nothing — Compose can't scale) | `HorizontalPodAutoscaler` | `hpa.yaml` |
