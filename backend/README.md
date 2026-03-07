# QnAI FastAPI Backend (Recall.ai Integration)

This backend provides real-time meeting transcription using Recall.ai's bot-as-a-service and broadcasts it via WebSockets.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **ngrok** (to expose your local server to Recall.ai)
- **Recall.ai Account** (and API Key)

---

### 2. Installation
Navigate into the backend folder and install the required dependencies:

```bash
cd backend
python -m pip install -r requirements.txt
```

---

### 3. Configuration (`.env`)
Create a `.env` file in the `backend` folder and fill in your credentials:

```bash
# Recall.ai Credentials
RECALL_API_KEY=your_recall_api_key_here
RECALL_REGION=us-west-2  # Look at your dashboard URL to confirm

# The public URL where Recall will send transcript data
# REPLACE this every time you restart ngrok!
RECALL_WEBHOOK_URL=https://your-ngrok-subdomain.ngrok-free.app/recall/webhook
```

---

### 4. Running the Project

#### A. Start your Backend
```bash
python main.py
```
*Your server will run on `http://localhost:8000`.*

#### B. Start ngrok
In a **new terminal window**, start ngrok to expose port 8000:
```bash
ngrok http 8000
```
*Copy the `Forwarding` URL (e.g., `https://1234.ngrok-free.app`) and update your `.env` file's `RECALL_WEBHOOK_URL`.*

#### C. Trigger the Bot to Join a Meeting
Open a **new terminal window** and run this command:
```bash
curl -X POST "http://localhost:8000/recall/join?meeting_url=YOUR_ZOOM_MEETING_URL"
```
*(Replace `YOUR_ZOOM_MEETING_URL` with your actual Zoom link.)*

---

### 5. Seeing the Output
- **Console:** You will see `[PARTIAL]` and `[FINAL]` transcripts logged directly in your terminal running `main.py`.
- **WebSocket:** Any frontend (or teammate) can connect to the live stream at:
  `ws://your-ngrok-subdomain.ngrok-free.app/ws/transcripts`

---

## 🛠 Troubleshooting
- **Bot not joining?** Check if the meeting has a **Waiting Room**. You must manually admit the bot.
- **Malformed URL?** Ensure your Zoom URL includes the password if required (e.g., `?pwd=xxx`).
- **Authentication failed?** Verify your `RECALL_REGION` in `.env` matches your Recall dashboard URL.
- **Empty Transcripts?** Ensure the meeting participants are speaking **English** (required for low-latency mode).
