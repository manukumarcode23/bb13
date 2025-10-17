# API Endpoints Documentation

## Admin Configuration

### Ads API Settings
The Ads API token and callback mode can be configured through the Admin Panel at `/admin/settings`:

- **Ads API Token**: Set the authentication token for ad network API endpoints. The system reads from database first, then falls back to `AD_API_TOKEN` environment variable if not set in admin panel.
- **Callback Mode**: Configure the default HTTP method for postback callbacks:
  - **POST (JSON)**: Sends link data as JSON payload (default)
  - **GET (URL Parameters)**: Sends link data as URL query parameters

These settings can be overridden per request using the `callback_method` parameter in the `/api/postback` endpoint.

---

## Advertisement API Endpoints

### 1. GET `/api/banner_ads`
**Intent:** Retrieve banner ad network information based on daily limits and priority

**Parameters:**
- `token` (query, required) - API authentication token (configured in Admin Panel or AD_API_TOKEN env var)
- `android_id` (query, required) - Android device identifier

**Response:**
```json
{
  "status": "success",
  "type": "banner",
  "network": "network_name",
  "banner_id": "banner_identifier",
  "priority": 1
}
```

**Function:** Finds available ad network for banner ads based on daily limits, increments play count, and returns network details.

---

### 2. GET `/api/interstitial_ads`
**Intent:** Retrieve interstitial ad network information based on daily limits and priority

**Parameters:**
- `token` (query, required) - API authentication token (AD_API_TOKEN)
- `android_id` (query, required) - Android device identifier

**Response:**
```json
{
  "status": "success",
  "type": "interstitial",
  "network": "network_name",
  "interstitial_id": "interstitial_identifier",
  "priority": 1
}
```

**Function:** Finds available ad network for interstitial ads based on daily limits, increments play count, and returns network details.

---

### 3. GET `/api/rewarded_ads`
**Intent:** Retrieve rewarded ad network information based on daily limits and priority

**Parameters:**
- `token` (query, required) - API authentication token (AD_API_TOKEN)
- `android_id` (query, required) - Android device identifier

**Response:**
```json
{
  "status": "success",
  "type": "rewarded",
  "network": "network_name",
  "rewarded_id": "rewarded_identifier",
  "priority": 1
}
```

**Function:** Finds available ad network for rewarded ads based on daily limits, increments play count, and returns network details.

---

## File Access API Endpoints

### 4. POST `/api/request`
**Intent:** Request access to a file and initiate link generation process

**Parameters (JSON Body):**
- `android_id` (string, required) - Android device identifier
- `hash_id` (string, required) - File access code/hash

**Response:**
```json
{
  "status": "pending",
  "message": "Please wait, links are being generated. Use the postback URL to generate the links."
}
```

**Function:** 
- Validates file existence and active status
- Links the file to the requesting Android device
- Returns pending status indicating links need to be generated via postback

---

### 5. GET/POST `/api/postback`
**Intent:** Generate temporary stream and download links after file access request

**Parameters (GET query or POST JSON):**
- `android_id` (string, required) - Android device identifier
- `hash_id` (string, required) - File access code/hash
- `callback_url` (string, optional) - URL to receive generated links
- `callback_method` (string, optional) - HTTP method for callback: 'GET' or 'POST' (defaults to admin-configured callback mode)

**Response:**
```json
{
  "status": "success",
  "message": "Links generated successfully. Use /api/links to retrieve them.",
  "callback_delivered": true
}
```

**Response with callback error:**
```json
{
  "status": "success",
  "message": "Links generated successfully. Use /api/links to retrieve them.",
  "callback_delivered": false,
  "callback_error": "error details"
}
```

**Function:**
- Validates file and Android ID match
- Generates temporary stream and download tokens
- Sets link expiry time based on video duration
- Creates link transaction record
- If `callback_url` is provided, sends links to the callback URL
- Callback method can be:
  - **GET (URL Parameters)**: Sends `android_id`, `stream_link`, and `download_link` as query parameters
  - **POST (JSON)**: Sends the same data as JSON payload
- Uses admin-configured callback mode by default, but can be overridden per request via `callback_method` parameter

---

### 6. POST `/api/links`
**Intent:** Retrieve generated stream and download links for a file

**Parameters (JSON Body):**
- `android_id` (string, required) - Android device identifier
- `hash_id` (string, required) - File access code/hash

**Response:**
```json
{
  "status": "success",
  "android_id": "device_id",
  "hash_id": "file_hash",
  "stream_link": "https://domain.com/stream/123?token=xxx",
  "download_link": "https://domain.com/dl/123?token=yyy",
  "expires_at": "2025-10-16T12:00:00Z"
}
```

**Function:**
- Validates file, Android ID match, and link existence
- Checks if links are expired
- Returns stream and download links with expiry information

---

## Tracking API Endpoints

### 7. GET `/api/tracking/postback`
**Intent:** Track video impressions for publisher analytics

**Parameters (Query):**
- `hash_id` (string, required) - File access code/hash
- `android_id` (string, required) - Android device identifier

**Response:**
```json
{
  "status": "success",
  "message": "Impression tracked successfully",
  "publisher_id": 123,
  "hash_id": "file_hash"
}
```

**Function:**
- Logs video impression with publisher ID, hash ID, Android ID, and user IP
- Used for publisher analytics and tracking
- Returns confirmation of tracked impression

---

## Web Routes (Non-API)

### File Streaming/Download Routes

#### GET `/stream/<file_id>`
**Intent:** Stream video files with token authentication

**Parameters:**
- `file_id` (path, required) - Telegram message ID
- `token` (query, required) - Temporary stream token

**Function:** Validates token and streams video content

---

#### GET `/dl/<file_id>`
**Intent:** Download files with token authentication and range request support

**Parameters:**
- `file_id` (path, required) - Telegram message ID
- `token` (query, required) - Temporary download token

**Function:** Validates token and serves file for download with range support

---

#### GET `/play/<hash_id>`
**Intent:** Landing page for video playback with deep linking support

**Parameters:**
- `hash_id` (path, required) - File access code

**Function:** Renders video player page with deep linking capabilities

---

### Upload Routes

#### GET `/upload`
**Intent:** Display file upload page

**Function:** Renders upload interface

---

#### POST `/upload`
**Intent:** Handle web-based file uploads

**Parameters (Multipart Form):**
- `video` (file, required) - Video file to upload

**Function:** Processes video upload, saves to Telegram, creates file record

---

## Authentication Routes

### POST `/register`
**Intent:** Register new publisher account

**Parameters (Form Data):**
- `email` (string, required) - Publisher email
- `password` (string, required) - Account password
- `confirm_password` (string, required) - Password confirmation
- `traffic_source` (string, required) - Traffic source description

**Function:** Creates new publisher account with validation

---

### POST `/login`
**Intent:** Authenticate publisher login

**Parameters (Form Data):**
- `email` (string, required) - Publisher email
- `password` (string, required) - Account password

**Function:** Validates credentials and creates session

---

### GET `/logout`
**Intent:** End publisher session

**Function:** Clears session and redirects to login

---

## Publisher Routes

### GET `/publisher/dashboard`
**Intent:** Display publisher dashboard with statistics

**Function:** Shows file count, impression count, and analytics

---

### POST `/publisher/generate-api-key`
**Intent:** Generate new API key for publisher

**Function:** Creates unique API key for external integrations

---

### POST `/publisher/upload-video`
**Intent:** Upload video through publisher dashboard

**Parameters (Multipart Form):**
- `video` (file, required) - Video file

**Function:** Processes publisher video upload via web interface

---

### POST `/publisher/delete-video/<file_id>`
**Intent:** Delete publisher's video

**Parameters:**
- `file_id` (path, required) - File ID to delete

**Function:** Removes video from system

---

## Admin Routes

### POST `/admin/register-publisher`
**Intent:** Admin creates new publisher account

**Parameters (Form Data):**
- `email` (string, required)
- `password` (string, required)
- `traffic_source` (string, required)
- `is_admin` (boolean, optional)

**Function:** Admin-level publisher creation

---

### POST `/admin/toggle-publisher/<publisher_id>`
**Intent:** Activate/deactivate publisher account

**Parameters:**
- `publisher_id` (path, required)

**Function:** Toggles publisher active status

---

### POST `/admin/ad-networks/add`
**Intent:** Add new ad network configuration

**Parameters (Form Data):**
- `network_name` (string, required)
- `banner_id`, `interstitial_id`, `rewarded_id` (optional)
- `banner_daily_limit`, `interstitial_daily_limit`, `rewarded_daily_limit` (integers)
- `priority` (integer)

**Function:** Creates new ad network with daily limits and priority

---

### POST `/admin/ad-networks/edit/<network_id>`
**Intent:** Update existing ad network

**Function:** Modifies ad network configuration

---

### POST `/admin/ad-networks/delete/<network_id>`
**Intent:** Remove ad network

**Function:** Deletes ad network from system

---

## Telegram Bot Commands

### `/start`
**Intent:** Welcome message and bot introduction

**Function:** Saves user to database and sends welcome message

---

### `/setapikey <api_key>`
**Intent:** Link publisher API key to Telegram account

**Parameters:**
- `api_key` (text, required) - Publisher API key

**Function:** Associates Telegram account with publisher account for bot uploads

---

### `/myaccount`
**Intent:** Display linked publisher account details

**Function:** Shows publisher email and account information

---

## File Upload Handler (Telegram)
**Intent:** Process file uploads sent to Telegram bot

**Function:** 
- Validates publisher authentication
- Saves file to Telegram
- Creates file record with access code
- Generates share link
- Provides revoke button

---

## Callback Handlers (Telegram)

### Callback Pattern: `rm_<message_id>_<secret_code>`
**Intent:** Revoke file access

**Function:** Deletes file and removes from database when revoke button clicked

---

## API Flow Summary

### Standard File Access Flow:
1. **POST `/api/request`** - Request file access (links android_id to file)
2. **GET/POST `/api/postback`** - Generate temporary links
3. **POST `/api/links`** - Retrieve the generated links
4. **GET `/stream/<file_id>` or `/dl/<file_id>`** - Access content with token
5. **GET `/api/tracking/postback`** - Track impression (optional)

### Ad Network Flow:
1. **GET `/api/banner_ads`**, `/api/interstitial_ads`, or `/api/rewarded_ads` - Get ad network based on limits and priority
2. System increments play count automatically
3. Returns next available network when daily limit reached
