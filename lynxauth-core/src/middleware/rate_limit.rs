use std::sync::Arc;

use axum::{
    body::Body,
    extract::{Request, State},
    middleware::Next,
    response::Response,
};

use crate::AppState;

pub async fn rate_limit_middleware(
    State(state): State<Arc<AppState>>,
    request: Request<Body>,
    next: Next,
) -> Response {
    let _rate_limit_hint = state.config.rate_limit_per_minute;
    next.run(request).await
}
