#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::fs::File;
use std::path::PathBuf;
use tauri::State;
use tokio::sync::Mutex;
use std::sync::Arc;
use serde::{Deserialize, Serialize};
use anyhow::Result;

// API URL
const API_URL: &str = "http://localhost:8000";

// Application state
struct AppState {
    api_client: reqwest::Client,
    processing_jobs: Arc<Mutex<Vec<String>>>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ApiResponse {
    job_id: String,
    status: String,
    progress: f32,
    message: Option<String>,
    result_url: Option<String>,
}

// Tauri commands
#[tauri::command]
async fn upload_file(
    _app: tauri::AppHandle,
    state: State<'_, AppState>,
    path: String,
) -> Result<String, String> {
    println!("Uploading file from path: {}", path); // Debug log
    
    // Create a multipart form
    let file_path = PathBuf::from(&path);
    let file_name = file_path.file_name()
        .ok_or_else(|| "Invalid file path".to_string())?
        .to_string_lossy()
        .to_string();
    
    // Read file content into bytes
    let file_content = tokio::fs::read(&path)
        .await
        .map_err(|e| format!("Failed to read file: {}", e))?;
    
    println!("File size: {} bytes", file_content.len()); // Debug log
    
    // Create part from bytes
    let file_part = reqwest::multipart::Part::bytes(file_content)
        .file_name(file_name);
    
    let form = reqwest::multipart::Form::new()
        .part("file", file_part);
    
    // Send request to backend API
    let response = state.api_client.post(&format!("{}/process/file", API_URL))
        .multipart(form)
        .send()
        .await
        .map_err(|e| format!("Failed to send request: {}", e))?;
    
    // Parse response
    let api_response: ApiResponse = response.json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;
    
    println!("Got job ID: {}", api_response.job_id); // Debug log
    
    // Store job ID in app state
    state.processing_jobs.lock().await.push(api_response.job_id.clone());
    
    // Return job ID
    Ok(api_response.job_id)
}

#[tauri::command]
async fn process_url(
    _app: tauri::AppHandle,
    state: State<'_, AppState>,
    url: String,
) -> Result<String, String> {
    // Create request body
    let body = serde_json::json!({
        "url": url,
        "options": {}
    });
    
    // Send request to backend API
    let response = state.api_client.post(&format!("{}/process/url", API_URL))
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Failed to send request: {}", e))?;
    
    // Parse response
    let api_response: ApiResponse = response.json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;
    
    // Store job ID in app state
    state.processing_jobs.lock().await.push(api_response.job_id.clone());
    
    // Return job ID
    Ok(api_response.job_id)
}

#[tauri::command]
async fn get_job_status(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<serde_json::Value, String> {
    // Send request to backend API
    let response = state.api_client.get(&format!("{}/status/{}", API_URL, job_id))
        .send()
        .await
        .map_err(|e| format!("Failed to send request: {}", e))?;
    
    // Parse response
    let api_response: serde_json::Value = response.json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;
    
    // Return status
    Ok(api_response)
}

#[tauri::command]
async fn download_result(
    _app: tauri::AppHandle,
    state: State<'_, AppState>,
    job_id: String,
    format: String,
    save_path: String,
) -> Result<String, String> {
    // Send request to backend API
    let response = state.api_client.get(&format!("{}/download/{}/{}", API_URL, job_id, format))
        .send()
        .await
        .map_err(|e| format!("Failed to send request: {}", e))?;
    
    // Check if request was successful
    if !response.status().is_success() {
        return Err(format!("Failed to download result: {}", response.status()));
    }
    
    // Get response bytes
    let bytes = response.bytes()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))?;
    
    // Write to file
    let path = PathBuf::from(&save_path);
    tokio::fs::write(&path, &bytes)
        .await
        .map_err(|e| format!("Failed to write file: {}", e))?;
    
    // Return success
    Ok(save_path)
}

#[tauri::command]
async fn read_file(path: String) -> Result<String, String> {
    // Read file content
    let content = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| format!("Failed to read file: {}", e))?;
    
    Ok(content)
}

#[tauri::command]
async fn cancel_job(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<bool, String> {
    // Send request to backend API
    let response = state.api_client.delete(&format!("{}/job/{}", API_URL, job_id))
        .send()
        .await
        .map_err(|e| format!("Failed to send request: {}", e))?;
    
    // Check if request was successful
    if !response.status().is_success() {
        return Err(format!("Failed to cancel job: {}", response.status()));
    }
    
    // Remove job ID from app state
    let mut jobs = state.processing_jobs.lock().await;
    if let Some(index) = jobs.iter().position(|id| id == &job_id) {
        jobs.remove(index);
    }
    
    // Return success
    Ok(true)
}

fn main() {
    // Initialize application state
    let app_state = AppState {
        api_client: reqwest::Client::new(),
        processing_jobs: Arc::new(Mutex::new(Vec::new())),
    };
    
    // Build Tauri application
    tauri::Builder::default()
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            upload_file,
            process_url,
            get_job_status,
            download_result,
            read_file,
            cancel_job,
        ])
        .run(tauri::generate_context!())
        .expect("Error while running Tauri application");
}