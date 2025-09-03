# cfb-discord-bot


## Postgres (Docker) Quickstart for `cfb26`

Use these instructions to manage the local Postgres database running inside Docker during development.

### Start the database
```
```bash
docker start cfb26-postgres
```

### Check status & logs
```
```bash
# See if it's running
docker ps --filter name=cfb26-postgres

# Follow logs (Ctrl+C to stop following)
docker logs -f cfb26-postgres
```

### Connect with `psql`
```
```bash
psql 'postgresql://cfbuser:yourpass@127.0.0.1:5432/cfb26'
```

### First‑time setup (create the container)
```
```bash
docker run -d \
  --name cfb26-postgres \
  -e POSTGRES_USER=cfbuser \
  -e POSTGRES_PASSWORD=yourpass \
  -e POSTGRES_DB=cfb26 \
  -v cfb26_data_v2:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:14
```

### Stop / restart
```
```bash
docker stop cfb26-postgres
docker restart cfb26-postgres
```

### Troubleshooting

**Port already in use (5432)**
```
```bash
brew services stop postgresql@14
```

**Check container exists**
```
```bash
docker ps -a --filter name=cfb26-postgres
```

**Exec into the container’s `psql`**
```
```bash
docker exec -it cfb26-postgres psql -U cfbuser -d cfb26
```

**Fresh reset (delete and recreate)**
```
```bash
docker stop cfb26-postgres
docker rm cfb26-postgres
docker volume rm cfb26_data_v2
```

### Connection details (for clients like DBeaver)

- **Host:** `127.0.0.1`
- **Port:** `5432`
- **Database:** `cfb26`
- **User:** `cfbuser`
- **Password:** `yourpass`
￼