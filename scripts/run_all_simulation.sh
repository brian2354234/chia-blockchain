. .venv/bin/activate
. scripts/common.sh

# Starts a harvester, farmer, timelord, introducer, and 3 full nodes.
# Make sure to point the full node in config/config.yaml to the local introducer: 127.0.0.1:8444.

_run_bg_cmd python -m src.server.start_harvester
_run_bg_cmd python -m src.server.start_timelord
_run_bg_cmd python -m src.server.start_farmer
_run_bg_cmd python -m src.server.start_introducer
_run_bg_cmd python -m src.server.start_full_node "127.0.0.1" 8444 -id 1 -f -t -u 8222
_run_bg_cmd python -m src.server.start_full_node "127.0.0.1" 8002 -id 2 -u 8223
_run_bg_cmd python -m src.server.start_full_node "127.0.0.1" 8005 -id 3 -u 8224

wait