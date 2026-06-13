use std::sync::Arc;
use std::time::Instant;

use axum::{
    Json, Router,
    extract::{Multipart, State},
    http::StatusCode,
    response::IntoResponse,
    routing::post,
};
use serde::{Deserialize, Serialize};

use crate::{AppState, services::proxy::ProxyService};

#[derive(Debug, Serialize, Deserialize)]
pub struct RegisterResponse {
    pub success: bool,
    pub user_id: String,
    pub message: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct VerifyResponse {
    pub authenticated: bool,
    pub user_id: Option<String>,
    pub confidence: Option<f32>,
    pub deepfake_detected: bool,
    #[serde(default)]
    pub synthetic_detected: bool,
    #[serde(default)]
    pub vit_prob: f64,
    #[serde(default)]
    pub synth_prob: f64,
    #[serde(default)]
    pub det_score: f64,
    pub latency_ms: u128,
}

pub fn router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/register", post(register_face))
        .route("/verify", post(verify_face))
}

pub async fn register_face(
    State(state): State<Arc<AppState>>,
    multipart: Multipart,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let proxy = ProxyService::new(state.http_client.clone(), state.config.inference_worker_url.clone());
    let response = proxy.forward_register(multipart).await?;
    Ok((StatusCode::OK, Json(response)))
}

pub async fn verify_face(
    State(state): State<Arc<AppState>>,
    multipart: Multipart,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let started = Instant::now();
    let proxy = ProxyService::new(state.http_client.clone(), state.config.inference_worker_url.clone());
    let response = proxy.forward_verify(multipart).await?;
    let latency_ms = started.elapsed().as_millis();

    state
        .audit_log_service
        .record(
            response.user_id.clone(),
            response.authenticated,
            response.deepfake_detected,
            response.confidence.map(|v| v as f64),
            latency_ms as i64,
        )
        .await
        .map_err(|err| (StatusCode::INTERNAL_SERVER_ERROR, err.to_string()))?;

    Ok((StatusCode::OK, Json(VerifyResponse { latency_ms, ..response })))
}
