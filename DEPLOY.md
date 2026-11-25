# Deploying InvoiceFlow on a VM

Everything below is what produced the running instance. Two paths: run the script,
or do it by hand. Both end at the same place — three containers behind nginx on port 80.

```
Internet :80 → nginx (nginx:alpine) ─┬─ /api/* → backend:8000  (FastAPI + LangGraph)
                                      └─ /      → frontend:3000 (Next.js standalone)
backend volume invoiceflow-data → /app/data/invoiceflow.db (SQLite)
```

---

## Path A — the script (recommended)

```bash
# on the VM
git clone https://github.com/DawnofGenX/invoiceflow.git ~/invoiceflow
cp ~/invoiceflow/.env.example ~/invoiceflow/.env
$EDITOR ~/invoiceflow/.env          # set OPENCODE_API_KEY=oc_sk_...
~/invoiceflow/scripts/vm_setup.sh
```

The script is idempotent: it installs Docker when missing, fast-forwards the repo,
builds and starts the stack, waits for `/api/health`, seeds demo data on a fresh
database, and prints the dashboard summary. Re-running it after a `git pull` is the
normal way to deploy a change.

Useful flags: `--reset` (wipe the database volume first), `--check` (report state,
change nothing).

**Save the API key first** — the stack refuses to start without it
(`docker-compose.yml` has `${OPENCODE_API_KEY:?set OPENCODE_API_KEY in .env}`).

---

## Path B — by hand

### 1. Docker

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER" && newgrp docker     # or log out and back in
docker run --rm hello-world                          # sanity check
```

### 2. Code and configuration

```bash
git clone https://github.com/DawnofGenX/invoiceflow.git ~/invoiceflow
cd ~/invoiceflow
cp .env.example .env
# OPENCODE_API_KEY is the only required value:
#   OPENCODE_API_KEY=oc_sk_...        (from the opencode-go collection)
# optional: OPENCODE_SESSION (any string, sent as x-opencode-session),
#           LLM_*_MODEL overrides, SECRET_KEY, CORS_ORIGINS
```

`.env` is gitignored. Never commit it.

### 3. Build and start

```bash
cd ~/invoiceflow
docker compose up -d --build
docker compose ps                     # backend, frontend, nginx → all Up
```

The first build takes a few minutes (Python deps + `tesseract-ocr`, then a Next.js
production build). Rebuilds hit the layer cache and take seconds.

If nginx answers 502 right after a container is recreated, it is serving a cached
upstream IP — `nginx.conf` uses Docker DNS re-resolution, so a
`docker compose restart nginx` is enough.

### 4. Open the port

The containers bind `0.0.0.0:80` on the VM. Whether the world can reach it is a
firewall question:

- **Azure** — Resource groups → `hermes-rg` → `hermes-vm` → Networking →
  Add inbound port rule → TCP, port `80`, Allow, priority `1000`, name `Allow-HTTP`.
- **AWS / GCP** — add an inbound rule for TCP 80 to the instance's security group.
- **ufw** — `sudo ufw allow 80/tcp` (OTOH: `sudo ufw status` to confirm the firewall
  isn't the blocker; on Azure the NSG sits *outside* the VM, so ufw being inactive
  proves nothing).

Check from another machine, not from the VM itself:

```bash
curl -s http://<vm-public-ip>/api/health      # {"status":"ok","service":"invoiceflow"}
```

### 5. Seed and verify

```bash
curl -s -X POST http://<vm-public-ip>/api/seed/
curl -s http://<vm-public-ip>/api/dashboard/

# from your laptop, with the repo checked out
python3 scripts/e2e_smoke.py --base-url http://<vm-public-ip> --verbose
```

`e2e_smoke.py` is the acceptance test, not a smoke test: it asserts the explainability
contract (every audit entry has non-empty reasoning, a confidence in [0,1] and a
`rule_fired` where a rule decided) across all five sample documents, plus batch upload,
the transparency summary, vendor history, list filters and the approval round-trip.
Expect `63/63 checks passed`.

### 6. Domain

- No DNS needed: `<anything>.<vm-public-ip>.nip.io` and `.sslip.io` resolve to the VM — but both
  still require the inbound port to be open in the cloud firewall.
- Real domain: create an `A` record pointing at the VM, then add a TLS terminator —
  easiest is Caddy or certbot in front, or nginx with `listen 443 ssl`.

### 7. If the port cannot be opened (the current production setup)

On this VM the Azure NSG exposes only TCP 22, and the tenant enforces security defaults
(`AADSTS530035`) so `az login --use-device-code` cannot be used to edit it from inside the guest.
A Tailscale Funnel gives a stable public HTTPS URL with no inbound port and no cloud credentials:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=hermes-vm        # prints a login.tailscale.com link — approve once
sudo tailscale funnel --bg 80                 # -> https://hermes-vm.<tailnet>.ts.net
sudo tailscale funnel status                  # confirm the mapping

# verify from OUTSIDE the tailnet (public DNS returns Funnel ingress IPs, not the node IP):
dig +short @1.1.1.1 hermes-vm.<tailnet>.ts.net
curl -s --resolve hermes-vm.<tailnet>.ts.net:443:<ingress-ip> https://hermes-vm.<tailnet>.ts.net/api/health
```

Live now: **https://hermes-vm.tailfd1655.ts.net** (Funnel persists across reconnects and reboots;
`sudo tailscale funnel reset` disables it).

Fallback that needs no Tailscale account — Cloudflare quick tunnel:

```bash
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
sudo systemd-run --unit=cf-quick-tunnel --collect \
  cloudflared tunnel --url http://127.0.0.1:80 --no-autoupdate
sudo journalctl -u cf-quick-tunnel | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```

The quick-tunnel hostname is random and dies with the tunnel process — fine for a demo, wrong
for a submission URL.

---

## Operating it

| Task | Command |
|---|---|
| Deploy a change | `cd ~/invoiceflow && git pull && docker compose up -d --build` |
| Logs | `docker compose logs -f backend` |
| Restart one service | `docker compose restart nginx` |
| Inspect the database | `docker compose exec backend sqlite3 /app/data/invoiceflow.db '.tables'` |
| Wipe and reseed | `docker compose down -v && docker compose up -d && curl -X POST localhost/api/seed/` |
| Disk usage | `docker system df` |

State lives in the `invoiceflow-data` volume, not in the containers, so
`docker compose up -d --build` (or a reboot) keeps invoices and audit history.
`restart: unless-stopped` plus `systemctl enable docker` means the stack comes back by
itself after the VM reboots — verify with `sudo reboot` then `curl localhost/api/health`.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `set OPENCODE_API_KEY in .env` on compose up | `.env` missing or the key is empty | fill it in; the key is required by design |
| 502 from nginx | cached upstream IP after a container recreate | `docker compose restart nginx` |
| `/api/health` ok locally, dead from outside | firewall/NSG, not the app | open TCP 80 at the provider |
| Pipeline returns `needs_review` on every upload | LLM unreachable or key rejected | `docker compose logs backend`; check `OPENCODE_API_KEY` and outbound HTTPS |
| Duplicate flags on every demo upload | the volume already holds those invoices | `docker compose down -v` and reseed before a demo |
| OCR returns empty text | scanned PDF with no text layer and tesseract path wrong | confirm `/usr/bin/tesseract` exists in the image |
