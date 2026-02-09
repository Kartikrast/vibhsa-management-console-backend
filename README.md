```
backend/
│
├── app/
│   │
│   ├── main.py                 # FastAPI app entry point
│   │
│   ├── core/                   # Cross-cutting concerns (foundation)
│   │   ├── __init__.py
│   │   ├── config.py            # Env & settings (pydantic)
│   │   ├── database.py          # SQLAlchemy engine & session
│   │   ├── security.py          # JWT, hashing, auth helpers
│   │   └── logging.py           # App-wide logging config
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py              # Declarative Base
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── product.py
│   │   ├── listing.py
│   │   ├── inventory.py
│   │   ├── order.py
│   │   └── marketplace.py
│   │
│   ├── schemas/                # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── inventory.py
│   │   ├── order.py
│   │   └── analytics.py
│   │
│   ├── repositories/           # DB access layer (CRUD logic)
│   │   ├── __init__.py
│   │   ├── user_repo.py
│   │   ├── product_repo.py
│   │   ├── inventory_repo.py
│   │   └── order_repo.py
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── inventory_service.py
│   │   ├── order_service.py
│   │   └── analytics_service.py
│   │
│   ├── routes/                 # API routes (FastAPI routers)
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── products.py
│   │   ├── inventory.py
│   │   ├── orders.py
│   │   ├── analytics.py
│   │   └── health.py
│   │
│   ├── marketplaces/           # External marketplace integrations
│   │   ├── __init__.py
│   │   └── walmart/
│   │       ├── __init__.py
│   │       ├── client.py        # HTTP client & auth
│   │       ├── products.py      # Walmart product APIs
│   │       ├── inventory.py     # Walmart inventory APIs
│   │       ├── orders.py        # Walmart order APIs
│   │       └── mappers.py       # Walmart ↔ internal model mapping
│   │
│   ├── workers/                # Background jobs / sync tasks
│   │   ├── __init__.py
│   │   ├── inventory_sync.py
│   │   ├── order_sync.py
│   │   └── product_sync.py
│   │
│   └── utils/                  # Helpers & shared utilities
│       ├── __init__.py
│       ├── pagination.py
│       ├── datetime.py
│       └── enums.py
│
├── alembic/                    # DB migrations
│   ├── versions/
│   └── env.py
│
├── alembic.ini
│
├── .env
├── pyproject.toml
└── README.md
```