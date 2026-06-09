use anyhow::{Context, Result};

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub app_port: u16,
    pub database_url: String,
    pub inference_worker_url: String,
    pub admin_api_key: String,
    pub rate_limit_per_minute: u32,
    pub face_match_threshold: f32,
}

impl AppConfig {
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            app_port: std::env::var("APP_PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()
                .context("invalid APP_PORT")?,
            database_url: std::env::var("DATABASE_URL")
                .context("DATABASE_URL is required")?,
            inference_worker_url: std::env::var("INFERENCE_WORKER_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:8000".to_string()),
            admin_api_key: std::env::var("ADMIN_API_KEY")
                .unwrap_or_else(|_| "change-me".to_string()),
            rate_limit_per_minute: std::env::var("RATE_LIMIT_PER_MINUTE")
                .unwrap_or_else(|_| "10".to_string())
                .parse()
                .context("invalid RATE_LIMIT_PER_MINUTE")?,
            face_match_threshold: std::env::var("FACE_MATCH_THRESHOLD")
                .unwrap_or_else(|_| "0.6".to_string())
                .parse()
                .context("invalid FACE_MATCH_THRESHOLD")?,
        })
    }
}
