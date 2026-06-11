# 1Password references — run: op run --env-file=.env.tpl -- python import_trails.py
# To find your vault name: op vault list
# NOTE: after supabase_lockdown.sql, import scripts need the service_role key
# (anon can no longer execute the import RPCs) — point this item at it.
SUPABASE_URL=op://Private/Supabase apex/username
SUPABASE_KEY=op://Private/Supabase apex/password
# Server-side Mapbox token for scripts (the web token is URL-restricted).
# Uncomment when the 1Password item exists (only compute_drive_times.py needs it):
# MAPBOX_SCRIPT_TOKEN=op://Private/apex_mapbox_script/credential
