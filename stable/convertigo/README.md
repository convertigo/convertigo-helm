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
| image.repository                  | convertigo             | The Docker image repository (the Docker Official Image). Customize if you want to use another repository. |
| image.tag                         |                        | The Docker image tag. Customize if you want to use a specific version. Default is the Chart app version. |
| image.jxmx                        | 1024                   | The Java memory size in MB for a worker pod. 1024 MB is recommended. Increase this value to handle more users per worker, but it will use more memory resources from the cluster. |
| additionalJavaOpts                | []                     | Extra lines appended to `JAVA_OPTS`, allowing custom JVM flags or overrides for bundled properties. |
| extraVolumes                      | []                     | Extra volumes mounted on the Convertigo pod, for example Redis TLS secrets. |
| extraVolumeMounts                 | []                     | Extra volume mounts for the Convertigo container. |
| sessionStore.mode                 | auto                   | Session store mode: `auto` (redis if enabled, otherwise tomcat), `tomcat` (sticky sessions), or `redis` (stateless). |
| sessionStore.redis.*              |                        | Optional Redis client settings used when `sessionStore.mode=redis` and `redis.enabled=false`. |
| sessionStore.redis.ssl.*          |                        | Optional Redis TLS/mTLS client settings: truststore, keystore, verification mode, and protocols. |
| sharedWorkspaceSync.enabled       | false                  | Enable runtime synchronization between instances that share the same Convertigo workspace. Recommended for multi-replica `ReadWriteMany` deployments. |
| webStudio                         |                        | Convertigo 8.5.0+. Web Studio in the administration console (`web_studio`): `disabled` or `enabled`. Empty: the administrators decide in the configuration, disabled at first. A value: imposed, the configuration cannot change it. |
| serverBuild                       |                        | Convertigo 8.5.0+. What the server builds (`server_build`), each level including those before it: `none`, `sources` (Java sources of the projects), `studio` (builds started from the web Studio: nodejs, npm packages, applications), `all` (applications deployed without their build, built at startup). Empty: the administrators decide in the configuration, `none` at first. A value: imposed. |
| redis.enabled                     | false                  | Deploy the embedded Redis service used for stateless sessions. When false, the chart does not configure Redis in Convertigo. |
| redis.auth.enabled                | true                   | Enable Redis AUTH for the embedded Redis. |
| redis.auth.password               | ChangeMe!              | Redis AUTH password used by the embedded Redis and injected into Convertigo when Redis is enabled. |
| redis.tls.enabled                 | false                  | Enable TLS on the embedded Redis and configure Convertigo to connect with `rediss`. |
| redis.tls.authClients             | true                   | Require client certificates on the embedded Redis when TLS is enabled. Set false for server-side TLS only. |
| redis.tls.existingSecret          |                        | Secret mounted in both Redis and Convertigo pods for Redis TLS/mTLS certificates and Java stores. |
| redis.persistence.enabled         | false                  | Enable persistence for the embedded Redis data volume. |
| nocodestudio.enable               | true                   | Enable installation of Convertigo No Code Studio (C8oForms projects). |
| nocodestudio.version              | 2.1.14                 | The Convertigo No Code Studio version for Citizen Dev applications to be deployed |
| publicAddr                        | localhost              | Public hostname used by the ingress rules. |
| publicUrl                         |                        | Full public origin users will use in browsers, including protocol and optional port, without a trailing path. Defaults to `https://publicAddr`. |
| publicDomains                     |                        | Public CORS origins injected into Convertigo `PUBLIC_DOMAINS`. Defaults to `publicUrl`. Use `#` as separator for multiple origins. |
| ingress.enabled                   | true                   | Set to true if you want to deploy an ingress (recommended in most cases). |
| ingress.className                 | nginx                  | Default is Nginx ingress. Ensure that an Nginx controller is deployed in your cluster. |
| ingress.annotations               |                        | Nginx ingress annotations for handling sticky sessions. Convertigo workers need sticky sessions based on route cookies. Default `values.yaml` provides the correct setup. |
| resources                         | {}                     | Convertigo resources restriction. |
| workspace.persistentVolume.storageClass | ebs-sc           | StorageClass for Convertigo workspace PVC. |
| workspace.persistentVolume.size   | 5Gi                    | PVC size for Convertigo workspace. |
| workspace.accessModes             | ["ReadWriteOnce"]      | AccessModes for Convertigo workspace PVC. |
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
| couchdb.enabled                   | true                   | Set to false when using an external CouchDB instance; skips deploying the bundled database and related resources. |
| couchdb.urlOverride               |                        | Optional full CouchDB URL (including protocol and port) for Convertigo to use instead of the internal service. |
| couchdb.existingSecret            |                        | Name of an existing secret providing CouchDB credentials (same namespace by default). |
| couchdb.existingSecretNamespace   |                        | Namespace of the existing CouchDB credentials secret (defaults to the release namespace). |
| couchdb.existingSecretUsernameKey |                        | Key inside the existing secret for the CouchDB username. |
| couchdb.existingSecretPasswordKey |                        | Key inside the existing secret for the CouchDB password. |
| couchdb.existingSecretOptional    | false                  | Set to true to ignore missing/invalid existing secrets and fall back to inline values. |
| couchdb.image.repository          | couchdb                | CouchDB image repository. Customize if using another repository. |
| couchdb.image.tag                 | 3.5                    | CouchDB image tag. Customize if using a specific version. |
| couchdb.admin                     | admin                  | CouchDB admin username. Used for account configuration, offline features, and No Code studio projects. |
| couchdb.password                  | fullsyncpassword       | CouchDB admin password. |
| couchdb.persistentVolume.storageClass | ebs-sc             | CouchDB PVC storageClass. |
| couchdb.persistentVolume.size     | 5Gi                    | CouchDB PVC size. |
| couchdb.accessModes               | ["ReadWriteOnce"]      | CouchDB PVC accessModes. |
| couchdb.resources                 | {}                     | Resources restriction for couchdb. |
| baserow.enabled                   | true                   | Set to true to use the integrated Baserow No Code database for No Code Studio and Low Code applications. |
| baserow.image.repository          | baserow/baserow        | Baserow image repository. Customize if using another repository. |
| baserow.image.tag                 | 1.30.1                 | Baserow image tag. Customize if using a specific version. |
| baserow.baserow_db                | baserow                | PostgreSQL database name for Baserow. It will be created automatically. |
| baserow.baserow_user              | baserow                | PostgreSQL username for Baserow. |
| baserow.baserow_password          | N0Passworw0rd          | PostgreSQL password for Baserow. |
| baserow.baserow_public_url        |                        | Optional Baserow-specific external URL. Defaults to `publicUrl`. |
| baserow.persistentVolume.storageClass | ebs-sc             | Baserow PVC storageClass. |
| baserow.persistentVolume.size         | 5Gi                | Baserow PVC size. |
| baserow.accessModes                   | ["ReadWriteOnce"]  | Baserow PVC accessModes. |
| baserow.resources                     | {}                 | Resources restriction for baserow. |

## External CouchDB example

To reuse an existing CouchDB cluster, disable the bundled component and point the chart to your endpoint:

```bash
helm upgrade --install convertigo ./stable/convertigo \
  --set couchdb.enabled=false \
  --set couchdb.urlOverride=https://my-couchdb:6984 \
  --set couchdb.existingSecret=my-couch-secrets \
  --set couchdb.existingSecretUsernameKey=username \
  --set couchdb.existingSecretPasswordKey=password
```

If the secret might be missing, add `--set couchdb.existingSecretOptional=true` to fall back to inline credentials.

## External Redis for session store

If you want to use an external Redis, set `sessionStore.mode=redis`, `redis.enabled=false`, and configure `sessionStore.redis.*`.

For Redis TLS/mTLS, mount the client truststore/keystore with `extraVolumes` and `extraVolumeMounts`, then point `sessionStore.redis.ssl.*` to the mounted files. Example:

```yaml
sessionStore:
  mode: redis
  redis:
    host: redis-mtls.default.svc.cluster.local
    port: 6379
    password: ChangeMe!
    ssl:
      enabled: true
      truststore: /etc/convertigo/redis/truststore.p12
      truststorePassword: changeit
      keystore: /etc/convertigo/redis/client.p12
      keystorePassword: changeit
      keystoreType: PKCS12
      verificationMode: CA_ONLY
extraVolumes:
  - name: redis-client-tls
    secret:
      secretName: redis-client-tls
extraVolumeMounts:
  - name: redis-client-tls
    mountPath: /etc/convertigo/redis
    readOnly: true
```

## Embedded Redis TLS/mTLS

The embedded Redis remains plaintext by default. To enable TLS/mTLS for the embedded Redis, keep `redis.enabled=true` and set `redis.tls.enabled=true`.

The chart expects `redis.tls.existingSecret` to contain the Redis PEM files and the Convertigo Java stores. Default key names are:

- `ca.crt`
- `redis.crt`
- `redis.key`
- `truststore.p12`
- `client.p12`

For `verificationMode=STRICT`, the Redis server certificate must contain the rendered Redis service name in its Subject Alternative Name. The service name is stable across pod restarts and is rendered as `<fullname>-redis`, for example:

- `c8o-baseline-convertigo-redis`
- `c8o-baseline-convertigo-redis.c8o-redis-baseline`
- `c8o-baseline-convertigo-redis.c8o-redis-baseline.svc`
- `c8o-baseline-convertigo-redis.c8o-redis-baseline.svc.cluster.local`

Example:

```yaml
redis:
  enabled: true
  auth:
    password: ChangeMe!
  tls:
    enabled: true
    authClients: true
    existingSecret: redis-mtls-certs
    truststorePassword: changeit
    keystorePassword: changeit
    keystoreType: PKCS12
    verificationMode: CA_ONLY
```

When this mode is enabled, Redis listens only on `--tls-port`, and Convertigo automatically receives the matching `session.redis.ssl.*` JVM properties.

Redis TLS client options:

- `truststore` identifies the Redis server certificate. It should contain the Redis server certificate, its signing CA, or both.
- `keystore` identifies Convertigo to Redis when Redis requires client certificates.
- Redisson supports JKS, PKCS#12, and PEM stores.
- `verificationMode` defaults to Redisson `STRICT`: validate the certificate chain and hostname. `CA_ONLY` validates the certificate chain but ignores hostname verification. `NONE` disables certificate verification.
- `protocols` is optional. Leave it empty for JVM/Redisson defaults, or set protocol versions such as `TLSv1.3,TLSv1.2`.

## Logs, cache, and shared workspace

When multiple Convertigo replicas share the same workspace PVC, only projects, configuration, and runtime sync markers should live on that shared volume.

The chart keeps logs and file cache on pod-local storage by injecting:

- `-Dlog.directory=/tmp/convertigo-logs`
- `-Dconvertigo.engine.cache_manager.filecache.directory=/tmp/convertigo-cache`

This avoids log/cache collisions between replicas and avoids accumulating stale per-instance log or cache directories on the shared workspace volume.

The chart also sets `LOG_STDOUT=true` and `LOG_FILE=true`: the engine logs reach the pod standard output, where the cluster log pipeline (Fluent Bit, Fluentd, Filebeat...) can collect them, and stay available in the **Logs** view of the administration console. The log line format, the multi-line rule (`^!` starts a record) and a Fluent Bit example are documented in the [Centralize the logs](https://doc.convertigo.com/documentation/latest/operating-guide/production-deployment-recommendations/#centralize-the-logs) section of the Operating Guide.

Notes on probes:
- Readiness can use an exec probe to verify the supervision endpoint contains "convertigo.started=OK":
  Example exec: ["sh","-c","curl -fsS http://127.0.0.1:28080/convertigo/admin/services/engine.Supervision | grep -q 'convertigo.started=OK'"]
- If exec is not provided or not supported by the image, the chart falls back to httpGet (ensure port name/number matches container ports).
- Exec probes require shell + curl + grep in the image; otherwise prefer httpGet.

## Needed annotations for nginx

As Convertigo workers require "sticky" sessions we need some specific nginx annotations. Some other needed configuration is also defined here. If you use another ingress controller be sure to configure the equivalent settings.
When the session mode resolves to `redis` (explicitly or via `auto`), sticky-session annotations are not needed and the chart removes them automatically.

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

## Production deployment

The Operating Guide's [Production deployment recommendations](https://doc.convertigo.com/documentation/latest/operating-guide/production-deployment-recommendations/) apply to this chart too. The examples below are optional settings to adapt to your network and ingress controller; they do not change the chart defaults.

### Public origin, HTTPS and error responses

Example override values for the Convertigo chart:

```yaml
publicAddr: convertigo.example.com
publicUrl: https://convertigo.example.com
publicDomains: "https://app.example.com#https://convertigo.example.com"
additionalJavaOpts:
  - "-Dconvertigo.engine.hiding_error_information=true"
  - "-Dconvertigo.engine.hide_product_version_in_api_specs=true"
ingress:
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
```

`publicAddr` is the hostname used by the ingress and its TLS certificate, whereas `publicUrl` is the full browser origin. `publicDomains` lists the allowed CORS origins and defaults to `publicUrl` when omitted. The image preserves a `cors.policy` already saved in the workspace; update that property in the admin console, or explicitly override it through `additionalJavaOpts` with `-Dconvertigo.engine.cors.policy=...` if necessary. CORS is not an access-control mechanism for non-browser clients.

The chart uses the TLS secret `convertigo-tls`. Provision a certificate for `publicAddr`, or configure your cert-manager issuer (the chart defaults to `letsencrypt-prod`). If TLS terminates at an upstream load balancer instead, adapt the ingress redirect and forwarded-header configuration to that topology to avoid redirect loops. See the ingress-nginx [HTTPS redirect annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/#server-side-https-enforcement-through-redirect).

The Java options suppress detailed errors in client responses while keeping them in the engine logs, and hide the product version in API specifications. To retain selected error details instead, leave `hiding_error_information=false` and configure the `show_error_*` properties described in the guide. This does not disable API discovery.

### HSTS belongs to the HTTPS frontend

Configure `Strict-Transport-Security` on the component terminating public HTTPS, not in Convertigo. For ingress-nginx, these are values for the **ingress-nginx controller chart**, not for the Convertigo chart:

```yaml
controller:
  config:
    hsts: "true"
    hsts-max-age: "31536000"
    hsts-include-subdomains: "false"
    hsts-preload: "false"
```

They apply controller-wide. Enable HSTS only after verifying that the sites are served over HTTPS permanently; enable `includeSubDomains` only if every affected subdomain also supports HTTPS. See the controller's [HSTS configuration](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/configmap/#hsts). For other ingress controllers or load balancers, use their equivalent settings.

### Restrict administration and optional API discovery

When end users should not reach the admin console, limit these paths to an administrator network or VPN at the public reverse proxy or gateway, including the forms without a trailing slash:

- `/convertigo/admin` and all paths below it, including `/convertigo/admin/services/`;
- `/convertigo/login` and `/convertigo/logout`;
- optionally `/convertigo/api` and all paths below it when public API discovery is not wanted.

The chart's ingress routes the entire `/convertigo/` prefix. It does not provide a value for per-path administration restrictions. For a public application, use a path-aware access policy at your frontend, or disable the chart ingress with `ingress.enabled=false` and manage the public and private routes separately. A private admin route alone does not protect these paths if a public catch-all still forwards them to Convertigo. Keep the server service private so clients cannot bypass the frontend policy, and change the default admin credentials.

If the **whole deployment** is private, ingress-nginx can restrict its ingress to selected source ranges through Convertigo override values:

```yaml
ingress:
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "192.0.2.0/24,2001:db8::/32"
```

Replace these documentation ranges with your actual administrator/VPN ranges. This annotation restricts all paths on that ingress, including applications and Baserow, not only the admin console. Check that the controller sees the real client IP through any upstream proxy. See the [source-range annotation](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/#whitelist-source-range).

Finally, use a project-root `.httpignore` (Convertigo 8.4.4+) to keep templates, configuration files and other non-public project resources off HTTP; it is independent from ingress access policies.

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
baserow.persistentVolume.storageClass: gp3
couchdb.persistentVolume.storageClass: gp3
timescaledb.persistentVolume.storageClass: gp3
```
in values.yaml

## Using Multiple replicas of Convertigo on EKS

Convertigo can be scaled up using multiple replicas. To do this they will have to share the same workspace. This can be achieved using an ReadManyWriteMany EFS storage class. You will need to define an **efs-sc** storage class this way

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
Where *EFS file system ID* is the fs ID of the EFS you have created.

Then configure Convertigo's workspace volume claim this way 
```
workspace.persistentVolume.storageClass: efs-sc
```

And enable shared-workspace runtime synchronization:

```
sharedWorkspaceSync:
  enabled: true
```

This setting is independent from `sessionStore.mode` and should be enabled for shared-workspace multi-replica deployments whether sessions are sticky Tomcat or Redis-backed.

## Install AWS Nginx ingress controller with internet facing Load Balancer

If it is not already done, when running on AWS you must create the Ingress controller **BEFORE** installing Convertigo HELM chart because you will need to configure in the values.yaml the DNS public address AWS Load Balancer created for you.

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

The Chart ingress will automatically use let's encrypt to setup the SSL certificate. Be sure to use a custom domain name such as *publicAddr* in your values.yaml *my-app.mydomain.com* as let's encrypt will not honor default *k8s-ingress-ingress-XXXXX* AWS load balancer domain names.
