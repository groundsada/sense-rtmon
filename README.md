# sense-rtmon (Dynamic Dashboard)
This package will provide everything needed to run `cloud` and `site` stack.

## Cloud Stack (running on host)

### Configuration
- fill out `config.yml` under `config_cloud` to deploy `cloud stack`.
- `cloud` stack uses config_cloud config files to start docker stack. Dashboards use the config_flow config files.
- Example (config.yml)
- ```yml
  ###### CONFIG YAML ######
  hostIP: H.O.S.T.I.P.
  
  ssl_certificate_key: 'path/to/key'
  ssl_certificate: 'path/to/certificate'
  grafana_host: 'http://dev2.virnao.com:3000'
  pushgateway: 'http://dev2.virnao.com:9091'
  grafana_username: 'username'
  grafana_password: 'password'
  grafana_api_token: "API KEY"
  siterm_url_map:
    "urn:ogf:network:nrp-nautilus.io:2020": https://sense-prpdev-fe.sdn-lb.ultralight.org/T2_US_SDSC/sitefe/json/frontend
    "urn:ogf:network:ultralight.org:2013": https://sense-caltech-fe.sdn-lb.ultralight.org/T2_US_Caltech_Test/sitefe/json/frontend
    "urn:ogf:network:sc-test.cenic.net:2020": https://sense-ladowntown-fe.sdn-lb.ultralight.org/NRM_CENIC/sitefe/json/frontend
  ```
- It also needs auth files
    - /root/.sense-o-auth.yaml
    - /etc/letsencrypt/live/dev2.virnao.com/privkey.pem
    - /etc/letsencrypt/live/dev2.virnao.com/cert.pem

### Installation
- Run `./install.sh` and follow the steps to install necessary dependencies. 

### Topology diagrams

Every dashboard carries two topology panels at the top, selected by `topdiagrams`
in `rtmon.yaml` (`Mermaid`, `Archify`, or `Both` - the default):

- **Mermaid** renders inline through the `jdbranham-diagram-panel` plugin and
  draws the complete graph: a node per switch port, VLAN, address and BGP peer.
- **Archify** draws the same path at device level, with that detail moved into
  cards beside it, and is interactive - focus views per site, an animated trace
  along the path, and PNG export.

Whichever is selected, the Mermaid walk always runs: it is what builds the path
model both diagrams are drawn from.

#### Archify prerequisites

Archify renders to a self-contained HTML file rather than to panel JSON, because
its runtime shell alone is 760 KB before any diagram is drawn - so every
dashboard would carry most of a megabyte of identical payload into Grafana's
database. RTMon builds the typed IR and POSTs it to the
[rtmon-archify](https://github.com/groundsada/rtmon-archify) sidecar, which
validates, renders, attributes and serves one gzipped artifact per dashboard;
the dashboard's `text` panel embeds it in a sandboxed `<iframe>`.

The sidecar is a **separate container in the same pod as RTMon**. It keeps the
Archify runtime and its third-party notices out of this repository and this
container image, and it is what listens on the network port. RTMon is an HTTP
client for it, and listens on nothing itself. Three things have to be set up:

1. **Run the sidecar and share the token.** Deploy the sidecar image, and set
   `archify.sidecar_url` and `archify.token` in `rtmon.yaml` to where it lives
   and the shared secret. An unconfigured sidecar_url skips the panel with a
   warning; a wrong token makes every render fail with the same warning.

2. **Point the browser at it.** `archify.diagram_url_base` is whatever URL a
   browser reaches the sidecar on - the Service, Ingress and TLS in front of it
   are the deployment's, not RTMon's. While this is unset the panel is skipped
   and the dashboard says so.

3. **Allow the iframe.** Grafana must run with

   ```ini
   [panels]
   disable_sanitize_html = true
   ```

   or `GF_PANELS_DISABLE_SANITIZE_HTML=true`. Without it Grafana strips the
   iframe and the panel renders empty.

   **This setting is org-wide, not per-panel.** Turning it on re-enables raw
   HTML for every text panel in that Grafana, including ones RTMon did not
   create. If that is not acceptable for your deployment, set
   `topdiagrams: Mermaid` - the Mermaid panel needs no plugin beyond the diagram
   panel it already uses, and shows the full topology.

If the sidecar is unreachable the panel is skipped with a warning in the
dashboard's "Graph Generation Warnings" row; nothing else is affected, and the
Mermaid diagram is still complete.

### Running
- `Cloud` stack consists of Grafana, Prometheus, Pushgateway, and Script Exporter containers. 
- Run `./start.sh` to deploy `Cloud` stack.
- Run `./update.sh` to start generating dashboards.

### Cleaning
- `clean.sh` script to removes running containers.

## Site Stack (containerized)

### Configuration
- `site` stack doesn't use any configuration files.
- Configuration is done inside each exporter's `docker-compose.yml` file. Variables are passed in under `environment` session. 

### Installation
- Docker Images are pull from DockerHub.
- To build images run `docker build . -t <user_name>/rocky_<exporter_name>_exporter:latest` under the correct directory. 

### Running
**NOTE: PLEASE FILL IN CONFIG FILES FIRST BEFORE RUNNING**. 
- `site` stack consists of `Node`, `SNMP`, `ARP`, and `TCP` (in development) Exporter.
- Start Exporters: `docker compose up -d` under the exporter directory.
- Detailed instruction can be found under each exporter's directory.

### Stopping
- Stop docker containers either `docker rm <container_id>` or run `docker compose down -v` under exporters' directory.
- Delete pod on cluster: `kubectl delete -n <namespace> deployment <name_of_exporter>-exporter`
