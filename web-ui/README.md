# Tube Explore UI

A colorful, modal-first single-page SvelteKit UI for the Tube Explore API.

## What is included

- Search, metadata inspection, and playlist inspection
- Video and playlist download flows
- Task list, task detail, task streaming, cancel, retry, delete, and results
- Downloaded files list and binary file download links
- Profile CRUD
- Conversion preset CRUD
- Outbox list, delete, and retry conversion
- Global settings
- Health and readiness views
- Responsive single-page layout with dialogs for advanced actions

## Setup

```bash
npm install
cp .env.example .env
npm run dev
```

By default the UI connects to:

```bash
http://localhost:8000
```

Change `PUBLIC_API_BASE_URL` in `.env` if your API runs elsewhere.

## API assumptions

This UI targets the updated Tube Explore OpenAPI spec and expects the backend to expose `/api/*` endpoints from the same spec.

## Design approach

The main screen is intentionally calm: primary input, recent activity, and four management cards. Dense controls are hidden in dialogs to avoid making the product feel like an admin dashboard.
