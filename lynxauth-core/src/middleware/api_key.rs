use std::sync::Arc;

use axum::{
    body::Body,
    extract::{Request, State},
    http::StatusCode,
    middleware::Next,
    response::Response,
};

use crate::AppState;

pub async fn admin_api_key_middleware(
    State(state): State<Arc<AppState>>,
    request: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let path = request.uri().path().to_string();

    // Skip enforcement in dev/demo mode (empty key or default dev value)
    let dev_mode = state.config.admin_api_key.is_empty()
        || state.config.admin_api_key == "change-me";
    if dev_mode {
        return Ok(next.run(request).await);
    }

    if path.starts_with("/api/v1/admin") {
        let provided = request
            .headers()
            .get("x-api-key")
            .and_then(|value| value.to_str().ok());

        if provided != Some(state.config.admin_api_key.as_str()) {
            return Err(StatusCode::UNAUTHORIZED);
        }
    }

    Ok(next.run(request).await)
}
