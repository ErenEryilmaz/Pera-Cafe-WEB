☕ PERA KAFE

Pera Kafe is an AI-powered virtual barista and web application designed to offer customers a fully personalized, interactive, and modern coffee ordering experience.

Initially designed as a prototype, the architecture has been upgraded to a professional cloud-ready structure, migrating to a high-performance FastAPI backend and a dedicated HTML/JavaScript frontend for maximum scalability and speed.


🌟 KEY FEATURES

🤖 AI Barista (Gemini AI): Powered by advanced natural language processing, the barista can chat with customers, recommend coffee blends, and seamlessly understand complex, custom orders.

🗣️ Voice Interaction (TTS Integration): Utilizing Text-to-Speech technology, the virtual barista communicates with you audibly, enhancing the real-world cafe feel.

👤 3D Avatar Interface: A stylized, dynamic 3D barista avatar greets customers, providing a rich, visually engaging user experience.

🔐 User Management & Database: Integrated with MySQL to provide a secure login system, order history tracking, and personalized menu management.

⚡ High-Performance Backend: An asynchronous, low-latency API architecture built entirely on FastAPI.


🏗️ SYSTEM ARHICTECTURE & TECH STACK

Pera Kafe is built using a modern client-server architecture.

Backend (Server-Side)
Framework: FastAPI (Python)

Artificial Intelligence: Google Gemini API (Prompt engineering and context management)

Speech Synthesis: GTTS libraries / External API integration

Database ORM/Driver: MySQL Connector 

Security: JWT-based authentication, password hashing (Bcrypt)

Frontend (Client-Side)
UI/UX: HTML5, CSS3 (Custom branding and responsive design)

Logic: Vanilla JavaScript (Asynchronous Fetch API for backend communication)

Database (MySQL)
Users: Stores user credentials and authentication data.

Orders: Tracks past user orders and shopping cart details.

Menu: A dynamically updatable catalog of items and prices.
