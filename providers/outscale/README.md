# Convertigo on OKS with a shared NFS workspace

This guide installs Convertigo on OUTSCALE OKS with a shared workspace backed by NFS. Shared Workspace is
Needed if you want more than 1 Convertigo replica running.
It assumes you have a working OKS cluster and `kubectl` access.

## 0) Prerequisites

- `kubectl` configured to reach the OKS cluster
- `helm` installed
- A namespace for Convertigo (example: `convertigo`)
- A namespace for NFS (example: `nfs`)

```bash
kubectl create namespace convertigo
kubectl create namespace nfs
```

## 1) Install the NFS server (userspace NFS‑Ganesha) for Multi Pod replica shared Worskpace

Apply the NFS deployment (RBAC + Service + Deployment) from `nfs-deployment.yaml`:

```bash
kubectl apply -f nfs-deployment.yaml
```

Verify the NFS pod is running:

```bash
kubectl -n nfs get pods -o wide
```

## 2) Create the NFS‑backed PV/PVC for Convertigo

Create a static PV + PVC pointing at the NFS service IP and `/export` path:

```bash
cat <<'YAML' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolume
metadata:
  name: nfs-pv
spec:
  accessModes:
  - ReadWriteMany
  capacity:
    storage: 5Gi
  mountOptions:
  - vers=4
  nfs:
    path: /export
    server: 10.92.20.183
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  volumeMode: Filesystem
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: convertigo-c8o-workspace
  namespace: convertigo
  annotations:
    helm.sh/resource-policy: keep
    meta.helm.sh/release-name: convertigo
    meta.helm.sh/release-namespace: convertigo
  labels:
    app.kubernetes.io/managed-by: Helm
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: 5Gi
  storageClassName: ""
  volumeMode: Filesystem
  volumeName: nfs-pv
YAML
```

Notes:
- The `server` IP is the NFS service ClusterIP from `nfs-deployment.yaml`.
- If you change the NFS service IP or name, update `server` accordingly.

## 3) Install Convertigo with Helm

Add the Convertigo Helm repo and install:

```bash
helm repo add convertigo https://convertigo-helm-charts.s3.eu-west-3.amazonaws.com
helm repo update

helm upgrade --install convertigo convertigo/convertigo \
  -n convertigo \
  --create-namespace \
  -f values.yaml
```

## 4) Verify

```bash
kubectl -n convertigo get deployments
kubectl -n convertigo get pods -o wide
```

All deployments should show `READY 1/1`.

## Troubleshooting

- Convertigo init fails with `Read-only file system`:
  - Ensure PV uses `path: /export` and NFS export is RW.
- Convertigo pods stuck in `Init:0/1`:
  - Check NFS server pod logs: `kubectl -n nfs logs deploy/nfs-server`.
- NFS mount issues:
  - Confirm NFS service IP: `kubectl -n nfs get svc nfs-server -o jsonpath='{.spec.clusterIP}'`.
  - Ensure PV `server` matches the service IP.
