#!/bin/sh
# Ticket-impact homework.
#   scripts/homework_setup.sh env   before `docker compose up`: writes .local/cto.env and OPENCLAW_CTO_GATEWAY_TOKEN
#   scripts/homework_setup.sh       after `docker compose up -d openclaw openclaw-cto phoenix`
# Needs in .local/openclaw.env: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, GITHUB_MCP_TOKEN, A2A_CTO_URL, A2A_CTO_TOKEN.
# Safe to re-run.
set -eu
cd "$(dirname "$0")/.."
MODEL="${HOMEWORK_MODEL:-anthropic/claude-sonnet-5-5}"

# Gateway B gets only the two secrets it needs (see openclaw-cto in docker-compose.yml).
if [ "${1:-}" = env ]; then
  umask 077
  grep -E '^(ANTHROPIC_API_KEY|A2A_CTO_TOKEN)=' .local/openclaw.env > .local/cto.env
  [ -z "$(tail -c1 .local/openclaw.env)" ] || echo >> .local/openclaw.env  # keep the last key intact
  grep -q '^A2A_GENERALIST_TOKEN=' .local/openclaw.env || printf 'A2A_GENERALIST_URL=http://127.0.0.1:18789/a2a/v1\nA2A_GENERALIST_TOKEN=%s\n' "$(openssl rand -hex 32)" >> .local/openclaw.env
  grep -q '^OPENCLAW_CTO_GATEWAY_TOKEN=' .env || echo "OPENCLAW_CTO_GATEWAY_TOKEN='$(openssl rand -hex 32)'" >> .env
  echo "Wrote .local/cto.env ($(wc -l < .local/cto.env | tr -d ' ') keys) and the CTO dashboard token in .env."
  exit 0
fi

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
oc openclaw approvals allowlist add --agent main /project/scripts/a2a_ask.py  # both teammates

echo "== openclaw-cto (gateway B: cto over A2A)"
oc openclaw-cto config patch --file /project/config/homework-cto.patch.json5
# CTO may run only the confined inspector: raw git/find/cat could execute commands
# or read secrets outside the read-only target/ mount.
oc openclaw-cto approvals allowlist add --agent cto /project/scripts/cto_inspect.py

docker compose restart openclaw openclaw-cto
echo "Done. Smoke test: docker compose exec openclaw /project/scripts/a2a_ask.py cto 'Reply with your agent id.'"
