{{/*
TLS Secret used by the Ingress and by the Gateway created by the chart.
*/}}
{{- define "convertigo.tlsSecretName" -}}
{{- $tls := default dict .Values.tls -}}
{{- default "convertigo-tls" $tls.secretName -}}
{{- end -}}

{{/*
"true" when these annotations name a cert-manager issuer, which then provides the TLS Secret.
*/}}
{{- define "convertigo.certManagerIssuer" -}}
{{- range $key, $value := (default dict .) -}}
  {{- if and $value (has $key (list "cert-manager.io/cluster-issuer" "cert-manager.io/issuer")) -}}true{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Host names of the Gateway API routes, as a JSON list: gateway.hostnames, else publicAddr, else none (any host)
when publicAddr is localhost or an IP address, which Gateway API host names cannot be.
*/}}
{{- define "convertigo.gatewayHostnames" -}}
{{- $gateway := default dict .Values.gateway -}}
{{- $hosts := default list $gateway.hostnames -}}
{{- $addr := toString (default "" .Values.publicAddr) -}}
{{- if and (not $hosts) $addr (ne $addr "localhost") (not (regexMatch "^[0-9.]+$|:" $addr)) -}}
  {{- $hosts = list $addr -}}
{{- end -}}
{{- toJson $hosts -}}
{{- end -}}

{{/*
"true" when the chart generates a self-signed certificate in the TLS Secret. tls.selfSigned:
auto (default) only for the Gateway created by the chart, true also for the Ingress, false never.
Never when a cert-manager issuer annotation provides the certificate.
*/}}
{{- define "convertigo.tlsSelfSigned" -}}
{{- $tls := default dict .Values.tls -}}
{{- $gateway := default dict .Values.gateway -}}
{{- $ingress := default dict .Values.ingress -}}
{{- $mode := "auto" -}}
{{- if and (hasKey $tls "selfSigned") (not (kindIs "invalid" $tls.selfSigned)) -}}
  {{- $mode = toString $tls.selfSigned -}}
{{- end -}}
{{- if not (has $mode (list "auto" "true" "false")) -}}
  {{- fail "tls.selfSigned must be auto, true or false" -}}
{{- end -}}
{{- if and $gateway.enabled $gateway.gatewayClassName (ne $mode "false") (not (include "convertigo.certManagerIssuer" $gateway.annotations)) -}}
true
{{- else if and $ingress.enabled (not $gateway.enabled) (eq $mode "true") (not (include "convertigo.certManagerIssuer" $ingress.annotations)) -}}
true
{{- end -}}
{{- end -}}
