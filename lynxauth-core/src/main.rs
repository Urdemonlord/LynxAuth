mod config;
mod db;
mod middleware;
mod routes;
mod services;

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{Router, routing::get};
use config::AppConfig;
use db::connect_db;
use middleware::{api_key::admin_api_key_middleware, rate_limit::rate_limit_middleware};
use reqwest::Client;
use services::audit_log::AuditLogService;
use tower::ServiceBuilder;
use tower_http::trace::TraceLayer;
use tracing::info;

#[derive(Clone)]
pub struct AppState {
    pub config: AppConfig,
    pub http_client: Client,
    pub db_pool: sqlx::PgPool,
    pub audit_log_service: AuditLogService,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenvy::dotenv().ok();
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let config = AppConfig::from_env()?;
    let db_pool = connect_db(&config.database_url).await?;
    let audit_log_service = AuditLogService::new(db_pool.clone());

    let state = Arc::new(AppState {
        config: config.clone(),
        http_client: Client::new(),
        db_pool,
        audit_log_service,
    });

    let app = Router::new()
        .route("/healthz", get(routes::healthz))
        .nest("/api/v1", routes::api_router(state.clone()))
        .layer(
            ServiceBuilder::new()
                .layer(TraceLayer::new_for_http())
                .layer(axum::middleware::from_fn_with_state(state.clone(), rate_limit_middleware))
                .layer(axum::middleware::from_fn_with_state(state.clone(), admin_api_key_middleware)),
        )
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], config.app_port));
    info!(%addr, "lynxauth-core listening");

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
