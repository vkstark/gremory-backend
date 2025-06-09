# Gremory Backend (`gremory-be`)

**Backend for [Gremory](https://github.com/vkstark/gremory-app)** – your private AI assistant. Fully customizable, self-hostable, and model-agnostic.

Gremory enables you to chat using your own models, APIs, and infrastructure. Unlike hosted LLMs, your data stays where **you** choose – in your cloud, database, or offline.

<br>

## 🔗 Related Projects

* 🔵 **Frontend (Flutter):** [`vkstark/gremory-app`](https://github.com/vkstark/gremory-app)
* 🌐 Works across Android, iOS, macOS, Web

<br>

## ⚙️ Tech Stack

| Layer                   | Tech                                                       |
| ----------------------- | ---------------------------------------------------------- |
| **Database**            | PostgreSQL (hosted on AWS)                                 |
| **Backend**             | Python + FastAPI                                           |
| **Model Orchestration** | LangChain (used for LLM abstraction & chaining)            |
| **Frontend**            | Flutter (cross-platform)                                   |
| **Deployment**          | Docker                                                     |
| **Infra Notes**         | AWS Amplify tested, but currently self-managed due to cost |

> The system is containerized and easily portable to any cloud or local stack.

<br>

## 🧠 Features

* 🔌 **Bring your own models** – OpenAI, local, or custom inference engines
* 🧾 **Chat + User History APIs**
* 🚀 **Deploy anywhere** with Docker or cloud platforms
* 🧪 **Pytest-based testing**
* 🧰 Modular structure inspired by best open-source LLM backends

<br>

## ⚡️ Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
cp .env.example .env
```

Edit it with your values (OpenAI key, DB credentials, etc.)

### 3. Run Server

```bash
uvicorn main:app --reload
```

Swagger UI: `http://localhost:8000/docs`

<br>

## 🧩 Add Your Own Model

To integrate a custom model:

1. **Edit `_get_or_create_model` in** `services/chat_service.py`
2. Register the model in `self.model_mapping`
3. Add the model to the `SupportedModels` Enum in `app/api/chat.py`
4. Add any required config/keys to `.env`

> This lets you plug in local LLMs, third-party APIs, or anything else.

<br>

## 🌐 API Overview

### 🔹 Chat & Models

* `GET /api/v1/models`
* `POST /api/v1/chat`

### 🔸 Conversations & History

* Full CRUD + messaging on user history and conversations

### 👤 Users

* User management and test seeding

<br>

## 🧪 Testing

```bash
pytest
```

Covers chat, history, and bug regressions.

<br>

## 🚀 Deployment

* ✅ Dockerized and ready for Render, Railway, Fly.io, AWS, etc.
* 🌍 Easily runs on VPS or on-premises
* 🛠 Auto-configured via `.env`


<br>

## 🙌 Contribute

Pull requests welcome!
Ideas, tools, or your own model integrations? Start a discussion or fork and build.


<br>

## 🛠 To-Do / Roadmap

* 🔄 **Personalization** using user-specific data
* 📄 **RAG (Retrieval-Augmented Generation)** with document uploads
* 🔧 **Tool calling / actions** like calculators, web search, etc.
* 🤖 **Multi-agent system** with routing and dynamic task delegation
