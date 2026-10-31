# Docmill

Docmill turns short labels into downloadable SVG diagram reports. The HTTP
process accepts requests; a separate worker renders them asynchronously.

## Run it on your laptop

You need Python 3.12+, PostgreSQL, Redis, and Graphviz. `nix-shell` supplies
them from pinned Nixpkgs, including the Python libraries. Start PostgreSQL and
Redis locally, create a database owned by your development user, then:

```sh
nix-shell
mkdir -p .local/reports
printf '%s\n' 'development-only-token' > .local/api-token
export DATABASE_URL="postgresql:///docmill?host=/run/postgresql"
export REDIS_URL="redis://127.0.0.1:6379/0"
export DOCMILL_STORAGE="$PWD/.local/reports"
export DOCMILL_TOKEN_FILE="$PWD/.local/api-token"
python -m docmill migrate
python -m docmill api
```

Run `python -m docmill worker` in another terminal with the same environment.
Graphviz's `dot` executable must be on the worker's PATH.

```sh
curl -H 'Authorization: Bearer development-only-token' \
  -H 'Content-Type: application/json' \
  -d '{"label":"A useful report"}' http://127.0.0.1:8080/jobs
# Poll /jobs/<id>, then download /reports/<id>.svg with the same authorization.
```

`GET /health` returns ready once the database schema, cache, credential file,
and report directory are available. It does not check whether the worker is
running. The API defaults to loopback; DOCMILL_BIND and DOCMILL_PORT configure
its listener.

## State and operations

PostgreSQL is the source of truth for accepted jobs. Redis is a wake-up queue;
queued work can be recovered even if that cache is emptied. Rendered files
live under DOCMILL_STORAGE and must remain alongside their database records.
Neither working directories nor temporary filesystem locations are a backup.

Run `migrate` before starting the application against a new database. It is
safe to rerun. The worker retries dependency failures and unfinished jobs. The
API exits if its credential file is absent at startup; a supervisor must let
it recover when credentials are provisioned later. The application reads the
credential file rather than needing a token embedded in a configuration.

For deployment, use packaged Python dependencies instead of running pip during
service startup. Neither application role needs root. Don't expose PostgreSQL
or Redis to other machines just to connect local application processes.
