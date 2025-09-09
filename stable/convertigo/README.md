# Convertigo Low Code / No Code Platform

[Convertigo](https://www.convertigo.com) Open Source Low Code & No Code application platform for Enterprises

## Requirements

Kubernetes: `>=1.21.0-0`

## Install Chart for OCI repo

```console
helm repo add convertigo https://convertigo-helm-charts.s3.eu-west-3.amazonaws.com
helm install [RELEASE NAME] convertigo/convertigo --version x.y.z
```
## Applying custom values

You can download a sample values.yaml file [here](https://raw.githubusercontent.com/convertigo/convertigo-helm/refs/heads/master/stable/convertigo/values.yaml), 
then use the 

```console
helm install [RELEASE NAME] convertigo/convertigo --version x.y.z  -f values.yaml
```
 Command to install the chart with custom values .

## Values definitions

Find below the values.yaml customization options : 

| name                              | default                | usage |
|-----------------------------------|------------------------|-------|
| replicaCount                      | 1                      | Number of Convertigo workers to run. One worker will handle from 100 to 200 simultaneous users. |
| image.repository                  | convertigo             | The Docker image repository. Customize if you want to use another repository. |
| image.tag                         |                        | The Docker image tag. Customize if you want to use a specific version. Default is `latest`. |
| image.jmx                         | 1024                   | The Java memory size in MB for a worker pod. 1024 MB is recommended. Increase this value to handle more users per worker, but it will use more memory resources from the cluster. |
| nocodestudio.version              | 2.1.1                  | The Convertigo No Code Studio version for Citizen Dev applications to be deployed |
| publicAddr                        | localhost              | This must match the exact public address users will use in their browsers, corresponding to your ingress DNS name. Default is `https://my-public-addr/convertigo`. |
| ingress.enabled                   | true                   | Set to true if you want to deploy an ingress (recommended in most cases). |
| ingress.className                 | nginx                  | Default is Nginx ingress. Ensure that an Nginx controller is deployed in your cluster. |
| ingress.annotations               |                        | Nginx ingress annotations for handling sticky sessions. Convertigo workers need sticky sessions based on route cookies. Default `values.yaml` provides the correct setup. |
| resources                         | {}                     | Convertigo resources restriction. |
| workspace.persistentVolume.storageClass | ebs-sc           | StorageClass for Convertigo workspace PVC. |
| workspace.persistentVolume.size   | 5Gi                    | PVC size for Convertigo workspace. |
| workspace.persistentVolume.accessModes | ["ReadWriteOnce"] | AccessModes for Convertigo workspace PVC. |
| timescaledb.enabled               | true                   | Required for usage and license billing. Set to false only if using an external TimescaleDB. |
| timescaledb.image.repository      | timescale/timescaledb  | TimescaleDB image repository. Customize if using another repository. |
| timescaledb.image.tag             | latest-pg16            | TimescaleDB image tag. Customize if using a specific version. |
| timescaledb.user                  | postgres               | Database username Convertigo will use to connect to TimescaleDB. Customize as needed. |
| timescaledb.password              | ChangeMe!              | Database password Convertigo will use to connect to TimescaleDB. Customize as needed. |
| timescaledb.billing_database      | c8oAnalytics           | Database name for storing usage analytics data. |
| timescaledb.billing_user          | c8oAnalytics           | Username for accessing the billing database. |
| timescaledb.billing_password      | c8oAnalytics           | Password for accessing the billing database. |
| timescaledb.persistentVolume.storageClass | ebs-sc         | TimescaleDB PVC storageClass. |
| timescaledb.persistentVolume.size         | 5Gi            | TimescaleDB PVC size. |
| timescaledb.accessModes                   | ["ReadWriteOnce"] | TimescaleDB PVC accessModes. |
| timescaledb.resources                           | {}       | Resources restriction for timescaledb. |
| couchdb.image.repository          | couchdb                | TimescaleDB image repository. Customize if using another repository. |
| couchdb.image.tag                 | 3.4.2                  | TimescaleDB image tag. Customize if using a specific version. |
| couchdb.admin                     | admin                  | CouchDB admin username. Used for account configuration, offline features, and No Code studio projects. |
| couchdb.password                  | fullsyncpassword       | CouchDB admin password. |
| couchdb.persistentVolume.storageClass | ebs-sc             | CouchDB PVC storageClass. |
| couchdb.persistentVolume.size         | 5Gi                | CouchDB PVC size. |
| couchdb.accessModes  | ["ReadWriteOnce"]  | CouchDB PVC accessModes. |
| couchdb.resources                     | {}                 | Resources restriction for couchdb. |
| baserow.enabled                   | true                   | Set to true to use the integrated Baserow No Code database for No Code Studio and Low Code applications. |
| baserow.image.repository          | baserow/baserow        | TimescaleDB image repository. Customize if using another repository. |
| baserow.image.tag                 | 1.30.1                 | TimescaleDB image tag. Customize if using a specific version. |
| baserow.baserow_db                | baserow                | PostgreSQL database name for Baserow. It will be created automatically. |
| baserow.baserow_user              | baserow                | PostgreSQL username for Baserow. |
| baserow.baserow_password          | N0Passworw0rd          | PostgreSQL password for Baserow. |
| baserow.persistentVolume.storageClass | ebs-sc             | Baserow PVC storageClass. |
| baserow.persistentVolume.size         | 5Gi                | Baserow PVC size. |
| baserow.accessModes                   | ["ReadWriteOnce"]  | Baserow PVC accessModes. |
| baserow.resources                     | {}                 | Resources restriction for baserow. |

Notes on probes:
- Readiness can use an exec probe to verify the supervision endpoint contains "convertigo.started=OK":
  Example exec: ["sh","-c","curl -fsS http://127.0.0.1:28080/convertigo/services/engine.Supervision | grep -q 'convertigo.started=OK'"]
- If exec is not provided or not supported by the image, the chart falls back to httpGet (ensure port name/number matches container ports).
- Exec probes require shell + curl + grep in the image; otherwise prefer httpGet.

## Needed annotations for nginx

As Convertigo workers require "sticky" sessions we need some specific nginx annotations. Some other needed configuration is also defined here. If you use another ingress controller be sure to configure the equivalent settings.

```code
  annotations: 
    kubernetes.io/ingress.class: nginx
    kubernetes.io/tls-acme: "true"
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/affinity-mode: "persistent"
    nginx.ingress.kubernetes.io/session-cookie-name: "route"
    nginx.ingress.kubernetes.io/session-cookie-hash: sha1
    nginx.ingress.kubernetes.io/session-cookie-secure: "false"
    nginx.ingress.kubernetes.io/session-cookie-path: "/convertigo"
    nginx.ingress.kubernetes.io/session-cookie-httponly: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: 500m
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
```

## Amazon EKS Storage class

On Amazon EKS you can define the gp3 storage class this way for Containers needing EBS volumes.

```code
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
parameters:
  type: gp3
provisioner: ebs.csi.eks.amazonaws.com
reclaimPolicy: Delete
volumeBindingMode: Immediate
```

And configure 
```
baserow.persitentVolume.storageClass: gp3
couchdb.persitentVolume.storageClass: gp3
timescaledb.persitentVolume.storageClass: gp3
```
in values.yaml

## Using Multiple replicas of Convertigo on EKS

Convertigo can be scaled up using multiple replicas. To do this they will have to share the same workspace. This can be achived using an ReadManyWriteMany EFS storage class. You will need to define an **ef-sc** storage class this way

```
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: efs-sc
parameters:
  basePath: /dynamic_provisioning
  directoryPerms: '700'
  ensureUniqueDirectory: 'true'
  fileSystemId: <EFS file system ID>
  gidRangeEnd: '2000'
  gidRangeStart: '1000'
  provisioningMode: efs-ap
  reuseAccessPoint: 'false'
  subPathPattern: ${.PVC.namespace}/${.PVC.name}
provisioner: efs.csi.aws.com
reclaimPolicy: Delete
volumeBindingMode: Immediate
``` 
Where *EFS file system ID* is the  the fs ID of the EFS you have created.

Then configure Convertigo's workspace volume claim this way 
```
workspace.persitentVolume.storageClass: efs-sc
```

## Install AWS Nginx ingress controller with internet facing Load Balancer

If it is not already done, When running on AWS you must create the Ingress controller **BEFORE** installing Convertigo HELM chart because you will need to configure in the values.yaml the DNS public address AWS Load Balancer created for you.

Be sure all your subnets are tagged properly, if not the controller will not be able to create the internet facing load balancer. for each of you subnets do

```
 aws ec2 create-tags --resources <subnet-id> --tags Key=kubernetes.io/role/elb,Value=1
```

Then install the controller

```
 helm install  -n ingress-nginx ingress-nginx --create-namespace ingress-nginx/ingress-nginx  \
    --set controller.service.type=LoadBalancer \
    --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-scheme"="internet-facing" 
```

## Using let's encrypt on AWS.

Start by installing let's encrypt certificate issuer 

```
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
    --namespace cert-manager --create-namespace \
    --set installCRDs=true
```

Then create a Cluster Issuer 

```
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    email: your-email@example.com  # Change this
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

The Chart ingress will automatically use let's encrypt to setup the SSL certificate. Be sure to use a custom domain name such as *publicAddr* in your values.yaml *my-app.mydomain.com* as let's encrypt will not honor default *k8s-ingressn-ingress-XXXXX* AWS load balancer domain names.
