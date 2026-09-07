# Book to Voice Converter Using Text-to-Speech Technology

Flask web app for uploading PDF files, extracting text, and converting the PDF into an English MP3 voice file.

No login or user accounts are included.

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python backend/app.py
```

Open:

`http://127.0.0.1:5000`

## Deploy on Render

The project includes a ready-to-use `render.yaml` file. It uses Gunicorn, binds to Render's assigned `$PORT`, has a `/health` readiness check, and deploys automatically after future pushes to the `main` branch.

1. In Render, select **New > Blueprint**.
2. Connect the GitHub repository `Bhushand007/book2voice`.
3. Select the `main` branch and deploy the detected `render.yaml` file.
4. Wait until the Render deploy log reports the `/health` check is passing, then open the generated `onrender.com` URL.

The free Render plan uses temporary local storage. Uploaded PDFs, generated MP3 files, and the SQLite database are cleared when Render restarts or redeploys. The conversion workflow works normally while the service is running. Use a Render Postgres database and persistent disk on a paid plan if you need saved audio and history to survive restarts.

## Temporary 24 Hour Live Link

Run this while the laptop is awake and connected to the internet:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_live_24h.ps1
```

The script writes the public tunnel URL into `LIVE_URL.txt`. It checks both the local server and public `/health` address every minute, then recreates its own tunnel when that link has expired. Keep the laptop awake and connected to the internet.

## Voice Service Reliability

The application uses Microsoft Edge neural voices, so it requires an active server internet connection. Before conversion it checks voice-service DNS availability, retries temporary connection failures three times, and removes incomplete audio files automatically. If the voice service is temporarily unavailable, the uploaded PDF stays ready and the page tells the user to retry instead of reporting a generic conversion failure.

## Project Structure

```text
backend/
  app.py
  config.py
  extensions.py
  models.py
  routes/
  services/
frontend/
  templates/
  static/
uploads/
generated_audio/
logs/
requirements.txt
render.yaml
Procfile
```

## API

- `GET /`
- `GET /health`
- `POST /upload` - PDF only
- `POST /convert`
- `GET /audio-list`
- `DELETE /delete-audio/<id>`
- `GET /stats`
- `GET /audio/<filename>`
- `GET /download/<id>`
