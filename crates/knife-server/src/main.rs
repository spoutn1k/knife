use firestore::FirestoreDb;
use knife_server::accounts::Accounts;
use knife_server::auth::Verifier;
use knife_server::members::Members;
use knife_server::store::Store;
use knife_server::{Auth, app};
use tokio::net::TcpListener;

const DEFAULT_PROJECT: &str = "knife-c51d5";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let project_id =
        std::env::var("GOOGLE_CLOUD_PROJECT").unwrap_or_else(|_| DEFAULT_PROJECT.into());

    // Same variable the Firebase SDKs use to detect the Auth emulator.
    let (verifier, accounts) = match std::env::var("FIREBASE_AUTH_EMULATOR_HOST") {
        Ok(host) => {
            tracing::warn!("FIREBASE_AUTH_EMULATOR_HOST is set: accepting unsigned tokens");
            (
                Verifier::emulator(&project_id),
                Accounts::emulator(&project_id, &host),
            )
        }
        Err(_) => (Verifier::google(&project_id), Accounts::google(&project_id)),
    };

    // Uses FIRESTORE_EMULATOR_HOST when set, Application Default Credentials
    // otherwise.
    let db = FirestoreDb::new(&project_id).await?;

    // Cloud Run passes the port to listen on in $PORT. The Firestore
    // emulator takes 8080, so default to 8000 locally.
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8000);
    let listener = TcpListener::bind(("0.0.0.0", port)).await?;

    let auth = Auth {
        verifier,
        members: Members::firestore(db.clone()),
        accounts,
    };

    tracing::info!("serving {project_id} on {}", listener.local_addr()?);
    axum::serve(listener, app(auth, Store::new(db)))
        .with_graceful_shutdown(async {
            tokio::signal::ctrl_c().await.ok();
        })
        .await?;
    Ok(())
}
