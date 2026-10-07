# Development and deployment of knife-server and spoon. `just` lists the recipes.

project := env("PROJECT", "knife-c51d5")

# Must match the "region" of the /api/** rewrite in firebase.json.

region := env("REGION", "europe-west1")
service := "knife-server"
repository := "knife"
service_account := service + "@" + project + ".iam.gserviceaccount.com"
registry := region + "-docker.pkg.dev"

# Images are tagged with the commit, marked -dirty when the tree has changes.

tag := env("TAG", `git describe --always --dirty`)
image := registry / project / repository / service + ":" + tag

# Addresses `just emulators` listens on.

emulator_env := "FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099"

[private]
default:
    @just --list --unsorted

# --- Development -----------------------------------------------------------

# Format, lint and run the tests that need no emulator
check:
    cargo clippy --workspace --all-targets -- -D warnings
    cargo clippy -p spoon --target wasm32-unknown-unknown -- -D warnings
    cargo test --workspace

# Run every test that needs the Firebase emulators
emulator-test:
    firebase emulators:exec --only auth,firestore "cargo emulator-test"

# Start the Auth and Firestore emulators, with their UI
emulators:
    firebase emulators:start --only auth,firestore

# Run the server against `just emulators`, on port 8000
serve:
    {{ emulator_env }} RUST_LOG=info cargo run -p {{ service }}

# Serve spoon with hot reload on port 8081, against `just serve` and the emulators
spoon:
    FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 dx serve -p spoon --port 8081

# Sign in as admin@email.com to manage members, editor@email.com to change
# recipes, or user@email.com to only read; the password is `password`. `data`,
# a chopstick export, is imported with chopstick if it exists. Everything is
# lost on exit.
#
# Run emulators, server and spoon (on http://localhost:8081) with sample data
local data="data.json":
    firebase emulators:exec --project {{ project }} --only auth,firestore \
        "just _local {{ quote(absolute_path(data)) }}"

[private]
_local data:
    #!/usr/bin/env bash
    set -euo pipefail
    password=password
    auth=http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts

    # member EMAIL NAME EDITOR ADMIN: an account and its member document.
    member() {
        echo "== Creating $1, $([[ $3 == true ]] && echo an editor || echo a reader)$([[ $4 == true ]] && echo " and admin") of the recipe book"
        local body="{\"email\":\"$1\",\"password\":\"$password\",\"returnSecureToken\":true}"
        local uid
        uid=$(curl -fsS "$auth:signUp?key=local" -H 'Content-Type: application/json' -d "$body" |
            sed -E 's/.*"localId": *"([^"]+)".*/\1/')
        curl -fsS -o /dev/null -X PATCH -H 'Authorization: Bearer owner' \
            -H 'Content-Type: application/json' \
            -d "{\"fields\":{\"display_name\":{\"stringValue\":\"$2\"},\"editor\":{\"booleanValue\":$3},\"admin\":{\"booleanValue\":$4}}}" \
            "http://127.0.0.1:8080/v1/projects/{{ project }}/databases/(default)/documents/members/$uid"
    }
    member admin@email.com Admin false true
    member editor@email.com Editor true false
    member user@email.com User false false

    {{ emulator_env }} RUST_LOG=info GOOGLE_CLOUD_PROJECT={{ project }} cargo run -p {{ service }} &
    server=$!
    trap 'kill $server' EXIT

    if [[ -f {{ quote(data) }} ]]; then
        echo "== Waiting for the server"
        until curl -fsS -o /dev/null http://127.0.0.1:8000/api/health; do sleep 1; done

        echo "== Importing {{ data }} with chopstick"
        # Keep chopstick's credentials away from the real ones.
        export XDG_CONFIG_HOME=$(mktemp -d) {{ emulator_env }}
        trap 'kill $server; rm -rf "$XDG_CONFIG_HOME"' EXIT
        KNIFE_PASSWORD=$password cargo run -q -p chopstick -- login \
            --email editor@email.com --api-key local --url http://127.0.0.1:8000
        cargo run -q -p chopstick -- import {{ quote(data) }}
    else
        echo "== No {{ data }}: starting with an empty recipe book"
    fi

    just spoon

# Build spoon for Hosting, into target/spoon/public
spoon-build:
    #!/usr/bin/env bash
    set -euo pipefail
    # spoon reads this at build time and would sign in against the emulator.
    if [[ -n "${FIREBASE_AUTH_EMULATOR_HOST:-}" ]]; then
        echo "FIREBASE_AUTH_EMULATOR_HOST is set: unset it for a production build" >&2
        exit 1
    fi
    # dx copies everything in its output folder into the bundle, old builds
    # included: start from an empty one.
    target=$(cargo metadata --format-version 1 --no-deps |
        python3 -c 'import json, sys; print(json.load(sys.stdin)["target_directory"])')
    rm -rf target/spoon "$target/dx/spoon/release"
    dx bundle -p spoon --web --release --profile wasm-release --out-dir target/spoon

# --- Image -----------------------------------------------------------------

# Build the server image
image:
    docker build --platform linux/amd64 -f crates/knife-server/Dockerfile -t {{ image }} .

# Run the built image against `just emulators`, on port 8000
image-run: image
    docker run --rm --network host -e PORT=8000 -e RUST_LOG=info \
        -e FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 \
        -e FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
        {{ image }}

# Push the image to Artifact Registry
push: image
    gcloud auth configure-docker {{ registry }} --quiet
    docker push {{ image }}

# --- Deployment ------------------------------------------------------------

# One-time Google Cloud setup: APIs, image repository, service account
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    gcloud=(gcloud --project {{ project }} --quiet)

    # Newly enabled APIs and new service accounts take a while to be visible
    # everywhere: retry the steps that depend on them.
    retry() {
        for attempt in 1 2 3 4 5 6; do
            "$@" && return
            echo "-- not ready yet (attempt $attempt), retrying in 20s" >&2
            sleep 20
        done
        "$@"
    }

    echo "== Enabling APIs"
    "${gcloud[@]}" services enable run.googleapis.com artifactregistry.googleapis.com \
        firestore.googleapis.com

    echo "== Artifact Registry repository"
    "${gcloud[@]}" artifacts repositories describe {{ repository }} --location {{ region }} \
        >/dev/null 2>&1 ||
        retry "${gcloud[@]}" artifacts repositories create {{ repository }} \
            --location {{ region }} --repository-format docker

    echo "== Service account with Firestore access"
    "${gcloud[@]}" iam service-accounts describe {{ service_account }} >/dev/null 2>&1 ||
        "${gcloud[@]}" iam service-accounts create {{ service }} --display-name {{ service }}
    retry "${gcloud[@]}" projects add-iam-policy-binding {{ project }} \
        --member serviceAccount:{{ service_account }} --role roles/datastore.user \
        --condition None >/dev/null

# Unauthenticated invocations are allowed so Hosting can forward requests;
# knife-server checks Firebase ID tokens and membership itself.

# Deploy the pushed image to Cloud Run
deploy-server: push
    gcloud run deploy {{ service }} --project {{ project }} --region {{ region }} \
        --image {{ image }} --service-account {{ service_account }} \
        --allow-unauthenticated \
        --set-env-vars GOOGLE_CLOUD_PROJECT={{ project }},RUST_LOG=info \
        --memory 256Mi --max-instances 2 --quiet

# Deploy Hosting (spoon and the /api/** rewrite)
deploy-hosting: spoon-build
    firebase deploy --project {{ project }} --only hosting

# Deploy the Firestore security rules
deploy-rules:
    firebase deploy --project {{ project }} --only firestore:rules

# Check, then deploy the server, Hosting and rules
deploy: check deploy-server deploy-hosting deploy-rules health

# --- Production --------------------------------------------------------------

# Check the deployed API answers through Hosting
health:
    curl -fsS https://{{ project }}.web.app/api/health && echo

# Show recent server logs
logs limit="50":
    gcloud logging read \
        'resource.type="cloud_run_revision" AND resource.labels.service_name="{{ service }}"' \
        --project {{ project }} --limit {{ limit }} --freshness 1d \
        --format 'value(timestamp,severity,textPayload)'
