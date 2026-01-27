# Convertigo on Exoscale SKS with a shared NFS workspace

This guide installs Convertigo on Exoscale SKS with a shared workspace backed by NFS. A shared workspace is
needed if you want more than 1 Convertigo replica running.
It assumes you have a working SKS cluster and `kubectl` access.

## 0) Prerequisites

- `kubectl` configured to reach the SKS cluster
- `helm` installed
- A namespace for Convertigo (example: `convertigo`)
- A namespace for NFS (example: `nfs`)

```bash
kubectl create namespace convertigo
kubectl create namespace nfs
```

## 1) Install the NFS server (userspace NFS‑Ganesha) for multi‑pod shared workspace

Apply the NFS deployment (RBAC + Service + Deployment) from `nfs-deployment.yaml`:

```bash
kubectl apply -f nfs-deployment.yaml
```

Verify the NFS pod is running:

```bash
kubectl -n nfs get pods -o wide
```

## 2) Dynamic NFS provisioning for Convertigo workspace

The NFS provisioner in `nfs-deployment.yaml` creates a StorageClass named `convertigo-nfs`.
The chart will create the workspace PVC automatically using this class.

Notes:
- In `values.yaml`, keep `workspace.persistentVolume.storageClass` set to `convertigo-nfs`.

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

## 4) Storage classes for Exoscale SKS

Update `values.yaml` to match your SKS storage classes:

- `timescaledb.persistentVolume.storageClass`
- `baserow.persistentVolume.storageClass`
- `couchdb.persistentVolume.storageClass`

The example uses `standard`, which is the default Exoscale CSI class in many SKS clusters. Adjust as needed.

## 5) Verify

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
