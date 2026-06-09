use std::sync::Arc;

use axum::{Json, Router, extract::State, routing::get};
use serde::Serialize;

use crate::AppState;

#[derive(Debug, Serialize)]
pub struct AuditLogsResponse {
    pub logs: Vec<crate::services::audit_log::AuditLogRecord>,
}

pub fn router() -> Router<Arc<AppState>> {
    Router::new().route("/logs", get(list_logs))
}

pub async fn list_logs(
    State(state): State<Arc<AppState>>,
) -> Result<Json<AuditLogsResponse>, (axum::http::StatusCode, String)> {
    let logs = state
        .audit_log_service
        .list_recent()
        .await
        .map_err(|err| (axum::http::StatusCode::INTERNAL_SERVER_ERROR, err.to_string()))?;

    Ok(Json(AuditLogsResponse { logs }))
}
