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

pub async fn api_index() -> Json<serde_json::Value> {
    Json(json!({
        "service": "lynxauth-core",
        "version": "0.1.0",
        "endpoints": {
            "healthz": "/api/v1/healthz",
            "auth": {
                "register": "POST /api/v1/auth/register",
                "verify": "POST /api/v1/auth/verify"
            },
            "admin": {
                "logs": "POST /api/v1/admin/logs"
            }
        }
    }))
}

pub fn api_router(state: Arc<AppState>) -> Router<Arc<AppState>> {
    Router::new()
        .route("/", get(api_index))
        .nest("/auth", auth::router())
        .nest("/admin", admin::router())
        .with_state(state)
        .route("/healthz", get(healthz))
}
