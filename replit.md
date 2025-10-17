# Telegram File Sharing Bot

## Overview

This is a Telegram bot application built with Python that provides file sharing capabilities through web links. The bot allows users to upload files to Telegram and automatically generates downloadable links, streaming links for videos, and provides a web interface for file access. It uses the Telethon library for Telegram API integration and Quart as the web framework to serve files via HTTP.

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

**Postback GET URL Format & Ads API Key Management (October 2025)**
- Added flexible callback system for /api/postback endpoint with GET and POST support
- New Admin Panel Settings for Ads API:
  - Ads API Token field with masked display and toggle visibility
  - Callback Mode selection (GET URL Parameters or POST JSON)
  - Token stored in database Settings table with environment variable fallback
- Extended `/api/postback` endpoint:
  - Accepts optional `callback_url` parameter for automatic link delivery
  - Accepts optional `callback_method` parameter to override default callback mode
  - Supports GET callbacks: Sends android_id, stream_link, download_link as URL parameters
  - Supports POST callbacks: Sends same data as JSON payload (default)
  - Returns callback delivery status in response
- Database changes:
  - Added `ads_api_token` field to Settings model
  - Added `callback_mode` field to Settings model (GET/POST)
  - Added `callback_method` field to LinkTransaction model for tracking
- Updated ad_api.py authentication to read token from database first, then fallback to AD_API_TOKEN environment variable
- Enhanced send_links_to_api function to support both HTTP methods with proper error handling
- Updated API documentation with new callback parameters and admin configuration details
- Migrations safely handle existing databases with IF NOT EXISTS guards

**Publisher Template Refactoring - Reusable Sidebar (October 2025)**
- Implemented Jinja2 template inheritance pattern for publisher section
- Created `publisher_base.html` base template containing:
  - Complete sidebar with all 5 menu items (Dashboard, Upload Video, Your Videos, API Management, Withdraw)
  - Mobile responsive header with hamburger menu
  - Sidebar toggle functionality and overlay for mobile
  - Reusable layout blocks for title, content, and scripts
- Refactored all 5 publisher templates to extend base template:
  - `publisher_dashboard.html` - Dashboard view
  - `publisher_upload.html` - Video upload interface
  - `publisher_videos.html` - Video management list
  - `api_management.html` - API key management
  - `publisher_withdraw.html` - Withdrawal requests
- Updated `publisher.py` backend to pass `active_page` variable for proper sidebar menu highlighting
- Eliminated code duplication - sidebar defined once, appears on all publisher pages automatically
- Maintained cyan/turquoise color scheme and responsive design across all pages

**Admin Withdrawal Management System (October 2025)**
- Added comprehensive admin panel for managing publisher withdrawal requests
- New `/admin/withdrawals` page with:
  - Dashboard showing total pending, approved, and rejected withdrawal counts
  - Status filtering (All, Pending, Approved, Rejected)
  - Detailed withdrawal request table with publisher info, bank details, and amounts
  - Approve/reject actions with admin notes
  - Automatic balance validation before approval
  - Auto-rejection when insufficient balance with detailed explanatory notes
- Backend routes:
  - `/admin/withdrawals` - View and filter all withdrawal requests
  - `/admin/withdrawal/approve/<id>` - Approve withdrawal with balance validation
  - `/admin/withdrawal/reject/<id>` - Reject withdrawal with admin notes
- Security features:
  - Validates publisher balance before approving withdrawals (prevents negative balances)
  - Auto-rejects insufficient balance requests with detailed error messages
  - Transaction-safe approval/rejection with rollback on errors
- Updated all admin panel sidebars to include Withdrawals navigation menu item
- Consistent cyan/turquoise theme matching other admin pages

**Publisher Withdrawal System (October 2025)**
- Added complete withdrawal feature for publishers to request payouts
- Database models: Added `balance` field to Publisher, created `BankAccount` and `WithdrawalRequest` tables
- Publisher dashboard now displays current available balance
- New `/publisher/withdraw` page with:
  - Balance display cards showing total balance
  - Bank account management form (account holder, bank name, account number, routing/SWIFT code, country)
  - Withdrawal request form with amount validation
  - Withdrawal history table showing all requests with status
- Backend routes:
  - `/publisher/save-bank-account` - Save/update bank account details
  - `/publisher/request-withdrawal` - Submit withdrawal requests
- Automatic earnings tracking: Publisher balance is credited when impressions are tracked via `/api/tracking/postback`
- Withdrawal workflow: Pending → Admin Review → Approved/Rejected
- Database migrations include explicit table creation for bank_accounts and withdrawal_requests with proper indexes

**Mobile App API Documentation (October 2025)**
- Created comprehensive API documentation for mobile app developers
- Added `APP_FLOW_SIMPLE.md` - ⭐ Simple step-by-step guide (no code, perfect for AI)
- Added `API_README.md` - Quick start guide for mobile developers
- Added `API_DOCUMENTATION.md` - Complete API reference with all endpoints
- Added `MOBILE_INTEGRATION_GUIDE.md` - Detailed integration guide (process only, no code)
- Added `API_FLOW.md` - Visual flow diagrams and sequence diagrams
- Added `README.md` - Project overview and documentation index
- Simple guide includes: Intent/Deep Link flow (14 steps) + Network Link flow (14 steps)
- Documentation covers complete user flow: Enter URL → Show ads → Stream/Download video
- Ad sequence clearly defined: Rewarded → Top Interstitial → Bottom Interstitial → Play button
- Perfect for AI-assisted application development

**Android App Integration (October 2025)**
- Added `/play/<hash_id>` landing page route for Android deep-link integration
- Implemented "Play in App" button with Android intent support
- Added Android app settings (package name, deep link scheme) to admin panel
- Updated bot and web upload responses to include play link
- Database migration for new Settings fields: `android_package_name`, `android_deep_link_scheme`
- Intent URL format: `intent://play?hash_id=HASH_ID#Intent;scheme=SCHEME;package=PACKAGE;end`

**API Parameter Update (October 2025)**
- Changed all API endpoints to use `android_id` instead of `username` parameter
- Updated `/api/request`, `/api/postback`, and `/api/links` endpoints
- Database models updated: `requested_by_username` → `requested_by_android_id`, `username` → `android_id` in LinkTransaction
- All error messages and documentation updated to reflect android_id usage

**UI Theme Update (October 2025)**
- Updated all Admin panel pages to use cyan/turquoise color scheme (#00BCD4, #0891B2)
- Updated all Publisher panel pages to use matching cyan/turquoise theme
- Modernized admin_ads_settings.html and admin_ad_networks.html with Tailwind CSS
- All pages now feature consistent sidebar navigation with all menu items accessible
- Color changes: Changed from purple/blue gradients to cyan gradients
- Maintained responsive design and mobile compatibility across all pages

## System Architecture

### Core Components

**Telegram Bot Layer**
- Built using Telethon library for Telegram API integration
- Plugin-based architecture with modular command handling
- Session management with file-based storage
- Event-driven message processing with decorators for user verification

**Web Server Layer**
- Quart (async Flask-like) web framework for HTTP file serving
- Uvicorn ASGI server for production deployment
- RESTful endpoints for file download, streaming, and Telegram file access
- Range request support for efficient large file streaming
- HTML5 video player integration with Plyr.js

**Database Layer**
- PostgreSQL database (Neon-backed via Replit)
- SQLAlchemy ORM with async support (asyncpg driver)
- Automatic table creation on startup
- Session management with transaction support
- Database connection pooling with health checks

**Authentication & Security**
- Temporary token-based file access with automatic expiry
- Android ID validation for link generation
- User whitelist system with owner privileges
- Environment variable-based configuration management
- Private chat verification for sensitive operations
- Time-limited access tokens (video duration + 1 hour)
- Publisher API key authentication for secure video uploads
- API key validation via form data or X-API-Key header

**File Management**
- Automatic file forwarding to designated channel for storage
- File property detection (name, size, MIME type, video duration)
- Support for multiple media types (video, audio, documents, photos)
- Automatic hash ID generation (12 characters)
- Link revocation capabilities

**API System**
- RESTful API for requesting temporary links
- Two-step workflow: request → postback → temporary links
- Secure token generation with expiry enforcement
- Android ID-based access control

**Plugin System**
- Dynamic plugin loading from the plugins directory
- Separate modules for commands, file handling, callbacks, and deep links
- Decorator-based user verification and access control
- Modular static text management

### Data Flow

**Via Telegram Bot:**
1. User sends file to bot in private chat
2. Bot generates 12-character hash ID and forwards file to storage channel
3. Bot returns hash ID to user (no direct download/stream links)
4. User calls `/api/request` with android_id and hash ID → receives pending status
5. User calls `/api/postback` with android_id and hash ID → receives temporary streaming/download links
6. Temporary links are valid for video duration + 1 hour
7. Web server validates temporary tokens and expiry before serving files
8. Links expire automatically after the validity period

**Via Web Upload (New):**
1. User visits `/upload` page on the web interface
2. User selects and uploads a video file (up to 2 GB)
3. Server saves file temporarily, extracts metadata (duration using ffprobe)
4. Server uploads file to Telegram storage channel with generated hash ID
5. Server saves file metadata to database
6. User receives hash ID for later API use
7. User can then use existing API endpoints (`/api/postback`) to generate streaming/download links
8. Temporary file is deleted from server after successful upload

**Via Publisher System:**
1. Publisher logs in to their account at `/login`
2. Publisher generates an API key from the API management page (`/publisher/api-management`)
3. Publisher navigates to the dashboard to upload videos
4. Upload requires the API key (sent as form data or X-API-Key header)
5. Without a valid API key, uploads are rejected with 401/403 error
6. API key can be regenerated at any time (old key becomes invalid)
7. Dashboard shows navigation menu with "Upload" and "API" options
8. Upload form is disabled if no API key is configured

### Deployment Architecture

- **Deployment Type**: VM (Virtual Machine) for persistent bot connections
- **Run Command**: `python -m bot`
- Environment variable configuration for secrets and settings
- File-based logging with structured format
- Health check endpoint with redirect to bot's Telegram profile
- Database migrations handled automatically on startup
- Web server bound to 0.0.0.0:5000 for external access

## External Dependencies

### Core Libraries
- **Telethon**: Telegram client library for bot functionality
- **Quart**: Async web framework for HTTP file serving
- **Uvicorn**: ASGI server for production deployment
- **cryptg**: Cryptographic library for Telegram encryption

### Frontend Dependencies
- **Plyr.js**: HTML5 media player for video streaming interface
- **Font Awesome**: Icon library for UI elements

### Required Environment Variables
- `TELEGRAM_API_ID`: Telegram API credentials
- `TELEGRAM_API_HASH`: Telegram API credentials  
- `TELEGRAM_BOT_TOKEN`: Bot authentication token
- `TELEGRAM_BOT_USERNAME`: Bot username for link generation
- `TELEGRAM_CHANNEL_ID`: Storage channel for file uploads
- `OWNER_ID`: Bot owner's Telegram user ID
- `BASE_URL`: Public URL for file serving endpoints
- `DATABASE_URL`: PostgreSQL connection string (auto-provided by Replit)
- `ALLOWED_USER_IDS`: Whitelist of authorized users (optional)
- `SECRET_CODE_LENGTH`: Length of generated access codes (optional)
- `PORT`: Web server port (optional, defaults to 5000)
- `BIND_ADDRESS`: Server bind address (optional, defaults to 0.0.0.0)

### System Dependencies
- **ffmpeg**: Video processing for extracting metadata (duration) from uploaded videos

### External Services
- **Telegram Bot API**: Primary integration for bot functionality
- **Telegram MTProto API**: Direct client access for file operations
- **CDN Services**: For serving Plyr.js and Font Awesome assets