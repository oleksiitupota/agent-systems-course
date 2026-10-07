# Known risks

Confirmed risks found by the ticket-impact skill, newest last.
Format: `- <date> <ticket>: <risk> (<file:line>)`.

- 2026-10-07 oleksiitupota/agent-systems-course#1: Retrying on timeout would double CTO work and stack to ~1200 s per peer call, because the client TIMEOUT_S and the gateway replyTimeoutMs are both 600 s (scripts/a2a_ask.py:17, config/homework-main.patch.json5:29)
- 2026-10-07 oleksiitupota/agent-systems-course#1: Rebuilding the request body on retry generates a new messageId and no idempotency key exists, so the peer may run the task twice (scripts/a2a_ask.py:34,37)
- 2026-10-07 oleksiitupota/agent-systems-course#1: HTTPError and URLError arrive as OSError, so the retry must distinguish 5xx from 4xx explicitly (scripts/a2a_ask.py:62)
- 2026-10-07 oleksiitupota/agent-systems-course#2: Gateway B takes a single token string, so rotation currently needs both gateways restarted (config/homework-cto.patch.json5:9, scripts/homework_setup.sh:44)
- 2026-10-07 oleksiitupota/agent-systems-course#2: homework_setup.sh copies only A2A_CTO_TOKEN into .local/cto.env, so a second token variable would not reach gateway B (scripts/homework_setup.sh:14)
- 2026-10-07 oleksiitupota/agent-systems-course#3: write overwrites by default and exec needs approval, so the no-overwrite rule must use read with optional:true (config/homework-main.patch.json5:23, scripts/homework_setup.sh:36)
- 2026-10-07 oleksiitupota/agent-systems-course#3: Ticket id owner/repo#N contains / and #, so using it as a filename can create subdirectories or path traversal (openclaw/workspace/skills/ticket-impact/SKILL.md:3)
