\# BusinessPilot AI — Enterprise AI Business Assistant



<p align="center">

&#x20; <strong>An AI-powered business assistant for querying business data through natural language.</strong>

</p>



<p align="center">

&#x20; <a href="https://businesspilotai.onrender.com"><strong>🚀 Live Application</strong></a>

&#x20; \&nbsp; | \&nbsp;

&#x20; <a href="https://github.com/MJcoder20/BusinessPilotAI">GitHub Repository</a>

</p>



\---



\## Overview



BusinessPilot AI is an AI-powered business assistant designed to help organizations interact with their business data using natural language.



Instead of manually navigating multiple business reports, users can ask questions and receive AI-generated insights based on available CRM and ERP data.



The application combines a conversational AI interface, business analytics tools, persistent conversations, and role-based authentication in a full-stack architecture.



\## Key Features



\- \*\*AI Business Assistant:\*\* Ask business-related questions using natural language.

\- \*\*Business Analytics:\*\* Retrieve dashboard insights, top customers, low-stock products, overdue invoices, and daily revenue.

\- \*\*Streaming Responses:\*\* Receive AI responses token by token.

\- \*\*Conversation Management:\*\* Create, retrieve, and manage persistent chat conversations.

\- \*\*Authentication:\*\* Secure registration, login, access tokens, and refresh-token rotation.

\- \*\*Role-Based Access Control:\*\* Admin, manager, and employee permissions.

\- \*\*Data Persistence:\*\* PostgreSQL database with SQLAlchemy and Alembic migrations.

\- \*\*Responsive Interface:\*\* React and TypeScript frontend.



\## Technology Stack



| Layer | Technologies |

|---|---|

| Frontend | React, TypeScript, Vite |

| Backend | Python, FastAPI |

| AI / Agents | LangChain, LangGraph |

| AI Models | Google Gemini, Ollama |

| Database | PostgreSQL, SQLAlchemy |

| Migrations | Alembic |

| Authentication | JWT, Argon2 |

| Deployment | Render, Neon |

| Infrastructure | Docker, Docker Compose |

| Testing | Pytest |



\## Architecture



```text

&#x20;               User

&#x20;                |

&#x20;                v

&#x20;      React + TypeScript UI

&#x20;                |

&#x20;                v

&#x20;         FastAPI Backend

&#x20;                |

&#x20;         Authentication

&#x20;                |

&#x20;                v

&#x20;         LangGraph Agent

&#x20;                |

&#x20;         Business AI Tools

&#x20;                |

&#x20;                v

&#x20;         PostgreSQL Database

&#x20;                |

&#x20;                v

&#x20;      Business Analytics Results

```



\## AI Business Tools



The assistant currently integrates tools for:



\- `get\_business\_dashboard`

\- `get\_top\_customers`

\- `get\_low\_stock\_products`

\- `get\_overdue\_invoices`

\- `get\_daily\_revenue`



These tools allow the AI agent to retrieve relevant business information from the database.



\## Application Screenshots



Screenshots of the application can be added here.



<!-- Add screenshots to a docs/screenshots directory and reference them here. -->



\## Live Deployment



\*\*Live Application:\*\* https://businesspilotai.onrender.com



The application is deployed using:



\- \*\*Render:\*\* Frontend and backend hosting.

\- \*\*Neon:\*\* Managed PostgreSQL database.



The deployed application uses a same-origin reverse proxy for frontend-to-backend API communication.



\*Note: The free hosting tier may introduce a delay when services wake up after inactivity.\*



\## Running Locally



\### Prerequisites



\- Python

\- Node.js and npm

\- PostgreSQL

\- Ollama (optional, for local AI model execution)



\### Backend



```bash

cd backend



python -m venv .venv

```



Activate the virtual environment, then install dependencies:



```bash

pip install -r requirements.txt

```



Configure the required environment variables in your local `.env` file, then run:



```bash

alembic upgrade head

uvicorn app.main:app --reload

```



\### Frontend



Open another terminal:



```bash

cd frontend



npm install

npm run dev

```



Configure `VITE\_API\_URL` to point to your local backend API.



\## Security



The application includes:



\- Password hashing with Argon2.

\- JWT-based authentication.

\- Refresh-token rotation and revocation.

\- Role-based authorization.

\- Conversation ownership and access isolation.

\- Environment-based configuration.



Use synthetic or non-sensitive business data when testing the public demo.



\## Project Status



The application is deployed and its current backend test suite and frontend production build have passed.



\## Author



\*\*Marah Hussam Abdullah HarounJouda\*\*



Computer Science Graduate | AI \& Software Engineering



\- GitHub: \[MJcoder20](https://github.com/MJcoder20)



\---



<p align="center">

&#x20; <strong>BusinessPilot AI — Turning Business Data into Conversational Insights.</strong>

</p>

