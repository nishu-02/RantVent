# RantVent — Audio-First Community Platform

> An open-source platform for sharing anonymous audio rants, thoughts, and comments within communities.

---

## Overview

| Aspect | Detail |
|--------|--------|
| **Type** | Audio-first social platform |
| **Core Features** | Posts, Comments, Communities, Anonymization |
| **Tech Stack** | FastAPI, SQLAlchemy, PostgreSQL, Redis, Gemini AI |

---

## ✅ Implemented Features

### Authentication & Users
- **Authentication** → `app/api/auth.py`
  - Sign up, login, refresh token, logout, change password
  - JWT-based with access & refresh tokens
  
- **User Profiles** → `app/api/users.py`
  - View/update profile, public profiles, search users
  - User statistics (posts, comments, join date)
  - Delete account

### Audio & Posts
- **Posts** → `app/api/posts.py`, `app/services/post_service.py`
  - Upload audio with anonymization presets (6 modes)
  - Background transcription & summarization (Gemini AI)
  - Feeds: general, community-specific, personalized
  - TLDR extraction and language detection

- **Comments** → `app/api/comments.py`, `app/services/comment_service.py`
  - Audio comments on posts with anonymization
  - Sentiment analysis (in-favor/against post)
  - Audio retrieval and replay

### Communities & Management
- **Communities** → `app/api/communities.py`
  - Create, join, leave, discover communities
  - Search and trending communities
  - Categories (organize communities)
  - Community activity feed and insights

- **Moderation** → `app/api/community_management.py`
  - Pin/unpin posts to community
  - Manage member roles (member → moderator → admin → owner)
  - Remove members, transfer ownership
  - Community avatars & banners

- **Statistics** → Per-community and per-user metrics

---

## 🟡 Partially Implemented / Needs Work

### AI & Audio Processing
| Feature | Status | Issue |
|---------|--------|-------|
| **Gemini AI** | 80% | Requires `GEMINI_API_KEY` env var; network-dependent |
| **Voice Anonymization** | 90% | Depends on native libs (`parselmouth`, `pydub`); needs system setup |

### Analytics & Insights
| Feature | Status | Issue |
|---------|--------|-------|
| **Community Analytics** | 60% | Returns placeholder data; needs complex aggregation queries |
| **Leaderboards** | 50% | Endpoints exist; scoring logic is simplified |
| **Hot/Top Sorting** | 60% | Basic implementation; ranking algorithm needs refinement |
| **Recommendations** | 40% | Placeholder suggestions; no ML ranking |

### Infrastructure
| Feature | Status | Issue |
|---------|--------|-------|
| **File Storage** | 70% | Upload hooks exist; verify `save_uploaded_file` for production |
| **Background Jobs** | 70% | Uses `asyncio.create_task()` — not durable; consider RQ/Celery/Redis Queue |

---

## 📊 Database Migrations

| Migration | Changes |
|-----------|---------|
| `736505bdf452_add_community_avatar_banner_and_category.py` | Added `avatar_url`, `banner_url`, `category_id` to communities; added `is_pinned`, `pinned_by`, `pinned_at` to posts |
| `50988ffb0347_add_community_tables.py` | Community, membership, and category tables |
| `f1589215da1e_comments.py` | Comments table with sentiment tracking |
| `b75a45911c77_add_community_management_features.py` | Management tables and roles |

---

## 📁 Project Structure

```
app/
├── api/                           # FastAPI route handlers
│   ├── auth.py                   # Authentication endpoints
│   ├── users.py                  # User profile & discovery
│   ├── posts.py                  # Post creation & listing
│   ├── comments.py               # Comment endpoints
│   ├── communities.py            # Community endpoints
│   └── community_management.py   # Moderation & roles
├── services/                      # Business logic
│   ├── user_service.py
│   ├── post_service.py
│   ├── comment_service.py
│   ├── community_service.py
│   ├── community_management_service.py
│   ├── gemini_service.py         # AI transcription & analysis
│   ├── voice_anonymizer.py       # Voice transformation
│   └── category_service.py
├── models/                        # SQLAlchemy ORM models
│   ├── user.py
│   ├── post.py
│   ├── comment.py
│   ├── community.py
│   └── community_membership.py
├── schemas/                       # Pydantic request/response schemas
├── core/                          # Config, database, tokens
├── dependencies/                  # Auth, Redis helpers
├── workers/                       # Background tasks (asyncio)
└── utils/                         # Storage, helpers
```

---

## 🚀 Next Steps (Priority Order)

### 1️⃣ Prepare AI & Audio Environment
- [ ] Set `GEMINI_API_KEY` in `.env`
- [ ] Install native audio libs: `parselmouth`, `pydub`, system audio utils
- **Files:** `app/services/gemini_service.py`, `app/services/voice_anonymizer.py`

### 2️⃣ Make Background Processing Durable
- [ ] Replace `asyncio.create_task()` with persistent worker queue (Redis/RQ/Celery)
- [ ] Add job persistence, retries, and failure handling
- **Files:** `app/workers/tasks.py`, `app/api/posts.py`, `app/api/comments.py`

### 3️⃣ Implement Real Analytics & Leaderboards
- [ ] Replace placeholder aggregation queries with production-ready logic
- [ ] Build scoring algorithms (upvotes, engagement, recency)
- [ ] Add caching layer for performance
- **Files:** `app/services/community_service.py`, `app/services/community_management_service.py`

---

## 💡 Quick Reference

| Layer | Files |
|-------|-------|
| **Routes** | `app/api/*.py` |
| **Business Logic** | `app/services/*.py` |
| **Data Models** | `app/models/*.py` |
| **Request/Response** | `app/schemas/*.py` |
| **Background Jobs** | `app/workers/tasks.py` |
| **DB Schema** | `alembic/versions/*.py` |
| **Config & Auth** | `app/core/`, `app/dependencies/` |
