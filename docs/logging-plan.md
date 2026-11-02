# Lightweight Query Logging Plan

## What We're Removing
- `supabase` package and all its dependencies
- All Supabase client code, table inserts, RPC calls
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` env vars

## New System: JSON File Logging

### What Gets Logged
Each chat request appends one JSON line to `logs/queries.jsonl`:

```json
{
  "timestamp": "2026-03-01T20:53:30Z",
  "session_id": "abc-123",
  "ip": "203.118.x.x",
  "query": "What is the RMA?",
  "response": "The Resource Management Act...",
  "sources_count": 5,
  "detected_act": "Resource Management Act 1991",
  "response_time_ms": 1234
}
```

### IP Address Notes
- Railway sits behind a proxy, so we get IP from `X-Forwarded-For` header
- Consider privacy: you could hash IPs or only store first 3 octets (e.g., `203.118.45.x`)
- NZ Privacy Act 2020 applies if you're storing identifiable info

### How You Access Logs

**Option A: Download endpoint (recommended)**
```
GET /admin/logs
X-Admin-Token: YOUR_SECRET
```
Returns the JSONL file. Open in any text editor, or import to Excel/Google Sheets.

**Option B: Simple stats endpoint**
```
GET /admin/stats
X-Admin-Token: YOUR_SECRET
```
Returns: total queries, queries today, top Acts asked about.

**Option C: SSH/Railway CLI**
```bash
railway run cat logs/queries.jsonl
```

### Implementation Changes

1. **Remove from requirements.txt:**
   - `supabase==2.11.0`

2. **Remove from main.py:**
   - Supabase imports and client init
   - `log_chat_message()`, `log_analytics()`, `update_topic_stats()` functions
   - All `supabase_client` references

3. **Add to main.py:**
   - Simple `log_query()` function (~15 lines)
   - `/admin/logs` endpoint (~10 lines)
   - `ADMIN_TOKEN` env var check

4. **Add to Railway:**
   - `ADMIN_TOKEN` env var (generate a random string)
   - Persistent volume mounted at `/app/logs`

### Storage Estimate
- ~500 bytes per query
- 1000 queries/day = 500KB/day = 15MB/month
- Railway free tier: plenty of space

### Migration Steps
1. Remove Supabase code
2. Add JSON logging
3. Push to Railway
4. Add ADMIN_TOKEN env var
5. Set up persistent volume in Railway (Settings > Volumes > Mount at /app/logs)
6. Done

## Decision Needed

**IP logging approach:**
- [ ] Full IP (most useful for abuse detection)
- [ ] Partial IP like `203.118.x.x` (privacy-friendly)
- [ ] Hashed IP (can detect same user, but not identify)
- [ ] No IP (maximum privacy)
