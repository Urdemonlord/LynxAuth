use axum::extract::Multipart;
use reqwest::multipart::{Form, Part};

use crate::routes::auth::{RegisterResponse, VerifyResponse};

#[derive(Clone)]
pub struct ProxyService {
    client: reqwest::Client,
    base_url: String,
}

impl ProxyService {
    pub fn new(client: reqwest::Client, base_url: String) -> Self {
        Self { client, base_url }
    }

    pub async fn forward_register(
        &self,
        multipart: Multipart,
    ) -> Result<RegisterResponse, (axum::http::StatusCode, String)> {
        let form = multipart_to_form(multipart).await?;
        let response = self
            .client
            .post(format!("{}/infer/register", self.base_url))
            .multipart(form)
            .send()
            .await
            .map_err(internal_error)?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_else(|_| "worker error".to_string());
            return Err((status, body));
        }

        response.json::<RegisterResponse>().await.map_err(internal_error)
    }

    pub async fn forward_verify(
        &self,
        multipart: Multipart,
    ) -> Result<VerifyResponse, (axum::http::StatusCode, String)> {
        let form = multipart_to_form(multipart).await?;
        let response = self
            .client
            .post(format!("{}/infer/verify", self.base_url))
            .multipart(form)
            .send()
            .await
            .map_err(internal_error)?;

        if response.status() == axum::http::StatusCode::FORBIDDEN {
            let body = response.json::<VerifyResponse>().await.map_err(internal_error)?;
            return Ok(body);
        }

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_else(|_| "worker error".to_string());
            return Err((status, body));
        }

        response.json::<VerifyResponse>().await.map_err(internal_error)
    }
}

async fn multipart_to_form(mut multipart: Multipart) -> Result<Form, (axum::http::StatusCode, String)> {
    let mut form = Form::new();

    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|err| (axum::http::StatusCode::BAD_REQUEST, err.to_string()))?
    {
        let name = field.name().unwrap_or("field").to_string();
        let file_name = field.file_name().map(|value| value.to_string());
        let content_type = field.content_type().map(|value| value.to_string());
        let bytes = field
            .bytes()
            .await
            .map_err(|err| (axum::http::StatusCode::BAD_REQUEST, err.to_string()))?;

        if let Some(file_name) = file_name {
            let mut part = Part::bytes(bytes.to_vec()).file_name(file_name);
            if let Some(content_type) = content_type {
                part = part.mime_str(&content_type).map_err(|err| {
                    (axum::http::StatusCode::BAD_REQUEST, format!("invalid mime type: {err}"))
                })?;
            }
            form = form.part(name, part);
        } else {
            form = form.text(name, String::from_utf8_lossy(&bytes).to_string());
        }
    }

    Ok(form)
}

fn internal_error(err: impl std::fmt::Display) -> (axum::http::StatusCode, String) {
    (axum::http::StatusCode::BAD_GATEWAY, err.to_string())
}
