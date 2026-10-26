🛡️ NetShield Command

Military Communication & Network-Centric Warfare

📌 Project Description

NetShield Command is a web-based educational simulation designed to demonstrate secure communication and network resilience between multiple fictional units. It shows how messages can be routed through available network connections, even when a link fails.

The project combines authentication, role-based access control, Dijkstra's shortest-path algorithm, message-integrity mechanisms, network-failure simulation, and event logging in one application.

Note: This project is an educational simulation. It does not connect to real military or defence networks.

🎯 Objectives

- Demonstrate communication between multiple network stations.
- Implement user authentication and role-based permissions.
- Find the lowest-cost available route using Dijkstra's algorithm.
- Simulate network-link failures and alternative routing.
- Display message priorities and incoming-message alerts.
- Store communication records and export logs for review.

✨ Key Features

- Secure Login: User authentication and session management.
- Role-Based Access Control: Different permissions for different user roles.
- Smart Routing: Dijkstra's algorithm calculates routes using active network links.
- Failure Simulation: Disable a link and observe alternative routing.
- Message Integrity: SHA-256-based message-integrity mechanism.
- Command Dashboard: Displays network connections, messages, and communication status.
- Priority Alerts: Supports different message priority levels.
- Event Logging: Stores relevant messages and system events.
- Data Export: Supports CSV and JSON exports.

🧰 Technology Stack

Technology| Purpose
HTML| Webpage structure
CSS| Styling and layout
JavaScript| User interaction and animations
Python| Backend logic
Flask| Web framework and API endpoints
SQLite| Database
Werkzeug| Authentication-related utilities

🏗️ System Architecture

The application follows a three-layer architecture:

1. Presentation Layer: HTML, CSS, and JavaScript provide the user interface.
2. Application Layer: Python Flask handles authentication, permissions, routing, and message processing.
3. Data Layer: SQLite stores users, links, messages, and event records.

🔄 How It Works

1. The operator logs in.
2. The operator selects a destination, priority, and message.
3. The application checks the operator's permissions.
4. Dijkstra's algorithm calculates the lowest-cost route through active links.
5. The message-integrity mechanism processes the message.
6. The application records relevant data and displays the outcome.

If a link fails, the application recalculates the route. If no available route exists, it reports that the destination cannot be reached.

🖥️ Network Simulation

The project uses six fictional stations:

- Command Center (CC)
- Alpha
- Bravo
- Charlie
- Delta
- Echo

For example, if the Delta-to-Echo link fails, the application can select an alternative route through Command Center if that route remains available.

⚙️ Installation and Setup

Prerequisites

- Python 3.10 or newer
- A web browser
- The project source files

Steps

1. Clone the repository

git clone <YOUR_REPOSITORY_URL>
cd <YOUR_PROJECT_FOLDER>

2. Create a virtual environment (recommended)

python -m venv venv

Activate it on Windows:

venv\Scripts\activate

3. Install dependencies

If the project includes a "requirements.txt" file:

pip install -r requirements.txt

Otherwise, install the dependencies listed in your actual project configuration.

4. Start the application

Use the startup command specified by your project. For a Flask application whose entry point is "app.py", this may be:

python app.py

5. Open the application

Visit the local address displayed in the terminal, commonly:

http://127.0.0.1:5000

The exact command and address depend on the application's configuration.

🔐 Security Notes

- Passwords should be stored using a suitable password-hashing method, never as plaintext.
- SHA-256 alone does not provide sender authentication or constitute a digital signature.
- Production deployment requires proper key management, secure sessions, authorization checks, and additional security testing.
- Demo credentials should never be reused as production credentials.

🚀 Future Scope

- Stronger cryptographic authentication and key management.
- More realistic network-failure and connectivity simulations.
- Performance monitoring and automated testing.
- Additional simulated stations and network configurations.
- Improved anomaly detection and network-status analysis.

👥 Project Team

Project Name: NetShield Command
Domain: Cybersecurity, Computer Networks, and Network-Centric Warfare
Project Type: Educational Web Application Simulation

Add your team members' names and individual contributions here.

📚 Conclusion

NetShield Command demonstrates how authentication, access control, graph-based routing, message-integrity checks, and event logging can be combined in a network communication simulation. It provides a foundation for learning about secure communication and resilience when network connections fail.

---

Disclaimer: NetShield Command is developed for educational and demonstration purposes only. It is not a real military communication platform and is not connected to operational defence systems.
