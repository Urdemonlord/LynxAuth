pub mod admin;
pub mod auth;

use std::sync::Arc;

use axum::{Json, Router, routing::get};
use serde_json::json;

use crate::AppState;

pub async fn healthz() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "service": "lynxauth-core"
    }))
}

pub fn api_router(state: Arc<AppState>) -> Router<Arc<AppState>> {
    Router::new()
        .nest("/auth", auth::router())
        .nest("/admin", admin::router())
        .with_state(state)
        .route("/healthz", get(healthz))
}
