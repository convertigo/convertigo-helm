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

|name       | default                     | usage
|-----------|-----------------------------|--------
| replicaCount | 1                         | Number of Convertigo workers to run. One worker will handle from 100 to 200 simultaneous users. |
| image.repository | convertigo                         | the dockerhub Image repository. Customize if you want to address an other repo |
| image.tag |                          | the image tag, Customize if you want to address a specific version. Default is latest|
| image.jmx | 512                         | The Java memory size in Mb of a worker POD. 512Mb is minimum, 1024Mb is recommended. You can make this larger to handler more users on a given worker. The more the value is increased the more worker pods will use memory resources from the cluster|
| publicAddr | "my-public-addr"                    | This must be configured to the exact public address users will have in their browser and must match the DNS server name your ingress will define. The default setting will allow users to connect this url: `https://my-public-addr/convertigo` |
| ingress.enabled | true                    | set to true if you want to deploy an ingress (Most of the cases)
|ingress.className | "nginx"   |   by default we deploy an Nginx ingress. Be sure Nginx controller has been deployed to your cluster|
| ingress.annotations| nginx Ingress annotation for handling sticky sessions | Convertigo workers need sticky sessions based on route cookie. To enable that see below the needed configuration. The default values.yaml already provides the correct configuration.|
|timescaledb.enabled | true         | Mandatory component for usage and licence billing. Set to false only if you want to use a timescaledb running outside of the cluster |
|timescaledb.user | postgress   | The database user name Convertigo will use to connect to the timescaledb database.  Customize to your needs |
|timecaledb.password | ChangeMe! | The database password Convertigo will use to connect to the timescaledb database.  Customize to your needs |
|timecaledb.billing_database| c8oAnalytics | The database holding usage analytics data|
|timecaledb.billing_user| c8oAnalytics | This database access username|
|timecaledb.billing_password| c8oAnalytics |This database access password |
|timecaledb.persistentVolume | hostpath of 5Gb | The timescale database persistent volume claim. Customize here to use Volume claims for your cluster provider. See below some sample volume claims |
|workspace.persistentVolume | hostpath of 5Gb | The Convertigo  workspace persistent volume claim. This is where deployed Low Code projects configuration will be persisted. In a multiple worker cluster this must be shared among all Convertigo  worker pods. This is why you should use a read-many/write-many capable storageClass here. Customize here to use Volume claims for your cluster provider. See below some sample volume claims |
|couchdb.admin | admin    | the CouchDB NoSQL database admin user. This database is used by Convertigo to store account configuration, perform all offline features and hold all the No Code studio projects and definitions. |
|couchdb.password | fullsyncpassord    | the CouchDB NoSQL database admin password. |
|couchdb.persistentVolume | hostpath of 5Gb | The CouchDB NoSQL database persistent volume claim. Customize here to use Volume claims for your cluster provider. See below some sample volume claims |
|baserow.enabled| true |  Set to true if you want to use the integrated Baserow No Code database for No Code Studio. It will provide data sources and Actions to the No Code applications. This database can also be used in Low Code applications for storing and handling data. | 
|baserow.baserow_db | baserow | The Postgres SQL database base name Baesrow will use and create automaticallly
|baserow.baserow_user| baserow | The Postgres SQL database access user name |
|baserow.baserow_password|N0Passworw0rd | The Postgres SQL database access password | 
|baserow.persistentVolume| hostpath of 5Gb | The baserow No Code  database persistent volume claim. Customize here to use Volume claims for your cluster provider. See below some sample volume claims |

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
