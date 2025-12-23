# Firebase Credentials Setup Guide

To update Firebase from the backend (Python scripts), you need Firebase Admin SDK service account credentials.

## Quick Setup Steps

### 1. Get Service Account Credentials

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Click the **gear icon (⚙️)** in the top left
4. Select **Project settings**
5. Go to the **"Service accounts"** tab
6. Click **"Generate new private key"** button
7. Click **"Generate key"** in the confirmation dialog
8. A JSON file will download (e.g., `your-project-firebase-adminsdk-xxxxx.json`)
9. **IMPORTANT**: Save this file in a secure location (e.g., `D:\Lock In Labs\firebase-credentials.json`)

### 2. Set Environment Variable

#### Windows PowerShell:
```powershell
$env:FIREBASE_CREDENTIALS="D:\Lock In Labs\firebase-credentials.json"
```

To make it permanent for your current PowerShell session, add it to your PowerShell profile:
```powershell
notepad $PROFILE
# Add: $env:FIREBASE_CREDENTIALS="D:\Lock In Labs\firebase-credentials.json"
```

#### Windows Command Prompt (CMD):
```cmd
set FIREBASE_CREDENTIALS=D:\Lock In Labs\firebase-credentials.json
```

#### Linux/Mac:
```bash
export FIREBASE_CREDENTIALS="/path/to/firebase-credentials.json"
```

### 3. Verify Setup

Run the update script:
```bash
python scripts/update_firebase_skill_tree.py
```

You should see:
```
[OK] Using Firebase credentials from: ...
[OK] Successfully updated Firebase!
```

## Alternative: Use GOOGLE_APPLICATION_CREDENTIALS

You can also use the standard Google Cloud environment variable:
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="D:\Lock In Labs\firebase-credentials.json"
```

## Security Notes

⚠️ **Important**: 
- Never commit the service account JSON file to git
- Keep it secure and private
- The service account has admin access to your Firebase project
- Add `firebase-credentials.json` to your `.gitignore` file

## Troubleshooting

### Error: "Firebase credentials not found"
- Make sure the environment variable is set in the same terminal/command prompt where you're running the script
- Verify the path to the credentials file is correct

### Error: "Credentials file not found"
- Check that the file path is correct
- Make sure you're using forward slashes `/` or escaped backslashes `\\` in the path

### Error: "Permission denied" or authentication errors
- Make sure the service account has Firestore permissions
- Verify your Firebase project has Firestore enabled
- Check that the JSON file is valid (not corrupted)

