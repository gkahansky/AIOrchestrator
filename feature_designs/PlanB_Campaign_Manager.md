# Technical Specification: "Campaign Manager" Module for Plan B

## 1. Overview
The "Campaign Manager" is a modular dashboard within the Plan B Admin ecosystem. It facilitates the creation, deployment, monitoring, and automated optimization of ad campaigns. It uses an **Adapter Pattern** to ensure scalability for future ad networks (LinkedIn, X, etc.) beyond the initial Google and Meta integrations.

## 2. Architecture: AdProvider Interface
All interaction with ad platforms must route through an `AdProvider` interface to ensure vendor-agnostic controller logic.

* **`CampaignController`**: Handles CRUD, state, and global metrics.
* **`AdProvider` (Interface)**: Defines standard methods: `createCampaign()`, `getStats()`, `toggleStatus()`, `getSupportedFormats()`.
* **Service Adapters**: `GoogleAdsAdapter`, `MetaAdsAdapter` implement the interface.

## 3. Database Schema (Updates)
Add the following to the existing schema:

### `Campaigns` Table
- `id`: Primary Key
- `name`: string
- `vendor`: string (google/meta)
- `external_id`: string (Vendor-specific ID)
- `status`: enum (active, paused, stopped)
- `daily_budget_limit`: decimal
- `total_budget_limit`: decimal
- `drive_folder_id`: string
- `created_at`: datetime

### `Metrics_History` Table
- `id`: Primary Key
- `campaign_id`: Foreign Key
- `spend`: decimal
- `clicks`: int
- `impressions`: int
- `timestamp`: datetime

## 4. Module Specifications

### 4.1 Creative Lab (Sub-Page)
1.  **Configuration**: UI fetches vendor-specific dimensions/shapes (e.g., 1:1, 9:16).
2.  **Generation**: User inputs prompt -> Gemini generates assets.
3.  **Storage**: 
    - Folder Name: `/PlanB/Campaigns/[Campaign_Name]_[Campaign_ID]/`
    - Logic: Save all assets to Drive; store URLs and File IDs in DB.
4.  **Approval**: Campaign is only created in the vendor API *after* the human approves the generated creative.

### 4.2 Dashboard & Monitoring
1.  **Dashboard View**:
    - Table displaying all active/paused campaigns.
    - Metrics: Current Spend, Impressions, Clicks, CPA.
2.  **Hard Stop/Alerting**:
    - **Logic**: Hourly background worker fetches spend from platform APIs.
    - **Visuals**: 
        - Row Highlight (Yellow): Spend >= 90% of budget.
        - Row Highlight (Red): Spend >= 100% of budget (Auto-Trigger Pause).
    - **Actions**: "Stop" button per row executes immediate API pause.

### 4.3 AI Insight Engine
- Triggered weekly or on-demand.
- Logic: Pulls metrics + Market Research context -> Gemini -> Returns structured optimization suggestions (e.g., "Pause Ad Set B", "Change Creative").

## 5. Human-Related Actions (Prerequisites)
These actions must be completed manually before the backend integration will function.

### 5.1 Google Cloud Platform (GCP)
1.  **OAuth Scopes Update**: Navigate to GCP Console > API & Services > OAuth Consent Screen.
2.  **Add Scopes**:
    - `https://www.googleapis.com/auth/adwords` (Google Ads)
    - `https://www.googleapis.com/auth/drive.file` (Google Drive)
3.  **Re-Authorization**: Trigger the OAuth consent flow in the Plan B Admin UI to generate a new token with these updated permissions. *Note: Existing tokens must be replaced; you cannot simply append scopes to a live token.*

### 5.2 Meta for Developers
1.  **App Registration**: Create an app in the Meta for Developers portal.
2.  **Permissions**: Request `ads_read` and `ads_management` permissions.
3.  **Tokens**: 
    - Generate a "System User Access Token" for long-lived access.
    - Ensure