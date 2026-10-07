#!/bin/sh
# Ticket-impact homework: configure both gateways after `docker compose up -d openclaw openclaw-cto phoenix`.
# Needs in .local/openclaw.env: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, GITHUB_MCP_TOKEN, A2A_CTO_URL, A2A_CTO_TOKEN.
# Safe to re-run.
set -eu
cd "$(dirname "$0")/.."
MODEL="${HOMEWORK_MODEL:-anthropic/claude-sonnet-5-5}"

oc() { service=$1; shift; docker compose exec -T "$service" openclaw "$@" 2>&1 | grep -v -i experimentalwarning | tail -1; }

for service in openclaw openclaw-cto; do
  echo "== $service"
  oc "$service" config set models.providers.anthropic.apiKey --ref-provider default --ref-source env --ref-id ANTHROPIC_API_KEY
  oc "$service" config set agents.defaults.model "{\"primary\":\"$MODEL\"}" --strict-json
done

echo "== openclaw (gateway A: main + generalist)"
oc openclaw config patch --file /project/config/homework-main.patch.json5
oc openclaw channels add --channel telegram --agent main --use-env
oc openclaw config set channels.telegram.dmPolicy pairing
oc openclaw config set channels.telegram.groupPolicy disabled
# main may run only the A2A helper, not python3 in general.
oc openclaw approvals allowlist add --agent main /project/scripts/a2a_ask.py

echo "== openclaw-cto (gateway B: cto over A2A)"
oc openclaw-cto config patch --file /project/config/homework-cto.patch.json5
# Read-only inspection binaries; target/ is a read-only mount.
for bin in /usr/bin/git /usr/bin/grep /usr/bin/find /usr/bin/head /usr/bin/ls /usr/bin/cat /usr/bin/wc; do
  oc openclaw-cto approvals allowlist add --agent cto "$bin"
done

docker compose restart openclaw openclaw-cto
echo "Done. Smoke test: docker compose exec openclaw /project/scripts/a2a_ask.py cto 'Reply with your agent id.'"
