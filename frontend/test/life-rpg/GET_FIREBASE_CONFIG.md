# How to Get Your Firebase Config for Frontend

## Quick Steps

### 1. Go to Firebase Console
Visit: https://console.firebase.google.com/

### 2. Select Your Project
- If you already have a project, select it
- If not, create a new project

### 3. Get Your Web App Config
1. Click the **⚙️ Settings** icon (gear) in the top left
2. Select **Project settings**
3. Scroll down to **Your apps** section
4. Look for a **Web app** (</> icon)
   - If you don't have one, click **Add app** > **Web** (</> icon)
   - Give it a nickname (e.g., "Life RPG Frontend")
   - Click **Register app**

### 4. Copy the Config Values
You'll see a config object that looks like this:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "123456789012",
  appId: "1:123456789012:web:abcdef1234567890"
};
```

### 5. Add to Your .env File

Create or edit `.env` file in `frontend/test/life-rpg/` directory:

```env
# Existing variables (keep these)
GEMINI_API_KEY="your-gemini-key"
ELEVENLABS_API_KEY="your-elevenlabs-key"
FIREBASE_CREDENTIALS=""

# Add these NEW Firebase frontend config variables:
VITE_FIREBASE_API_KEY="AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
VITE_FIREBASE_AUTH_DOMAIN="your-project.firebaseapp.com"
VITE_FIREBASE_PROJECT_ID="your-project-id"
VITE_FIREBASE_STORAGE_BUCKET="your-project.appspot.com"
VITE_FIREBASE_MESSAGING_SENDER_ID="123456789012"
VITE_FIREBASE_APP_ID="1:123456789012:web:abcdef1234567890"
```

**Important:** 
- All frontend variables MUST start with `VITE_` for Vite to expose them
- Replace the values with your actual Firebase config values
- No quotes needed around the values (or use quotes, both work)

### 6. Restart Your Dev Server
After adding the variables, restart your Vite dev server:
```bash
# Stop the server (Ctrl+C) and restart:
npm run dev
```

## Difference Between Frontend and Backend Config

- **Frontend Config** (`VITE_FIREBASE_*`): Used by the browser/client-side code for Firebase Auth and Firestore
- **Backend Config** (`FIREBASE_CREDENTIALS`): Used by your Python backend for admin operations (already set up)

Both are needed but serve different purposes!

