use chrono::{DateTime, Utc};
use serde::Serialize;
use sqlx::FromRow;

#[derive(Clone)]
pub struct AuditLogService {
    pool: sqlx::PgPool,
}

#[derive(Debug, Serialize, FromRow)]
pub struct AuditLogRecord {
    pub id: i64,
    pub timestamp: DateTime<Utc>,
    pub user_id: Option<String>,
    pub authenticated: bool,
    pub deepfake_detected: bool,
    pub confidence: Option<f64>,
    pub latency_ms: i64,
    pub source_ip: Option<String>,
    pub notes: Option<String>,
}

impl AuditLogService {
    pub fn new(pool: sqlx::PgPool) -> Self {
        Self { pool }
    }

    pub async fn record(
        &self,
        user_id: Option<String>,
        authenticated: bool,
        deepfake_detected: bool,
        confidence: Option<f64>,
        latency_ms: i64,
    ) -> Result<(), sqlx::Error> {
        sqlx::query(
            r#"
            INSERT INTO audit_logs (user_id, authenticated, deepfake_detected, confidence, latency_ms)
            VALUES ($1, $2, $3, $4, $5)
            "#,
        )
        .bind(user_id)
        .bind(authenticated)
        .bind(deepfake_detected)
        .bind(confidence)
        .bind(latency_ms)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    pub async fn list_recent(&self) -> Result<Vec<AuditLogRecord>, sqlx::Error> {
        let rows = sqlx::query_as::<_, AuditLogRecord>(
            r#"
            SELECT id, timestamp, user_id, authenticated, deepfake_detected, confidence, latency_ms, source_ip, notes
            FROM audit_logs
            ORDER BY timestamp DESC
            LIMIT 100
            "#,
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows)
    }
}
