# Firebase Authentication Setup

This app now uses Firebase Authentication for secure user authentication. Passwords are **never** stored in Firestore - they are handled securely by Firebase Auth.

## Setup Instructions

### 1. Enable Firebase Authentication

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Navigate to **Authentication** > **Sign-in method**
4. Click on **Email/Password**
5. Enable the first toggle (Email/Password)
6. Click **Save**

### 2. Configure Firebase Config

1. In Firebase Console, go to **Project Settings** > **General**
2. Scroll down to **Your apps** section
3. If you don't have a web app, click **Add app** > **Web** (</> icon)
4. Copy your Firebase configuration object

### 3. Set Environment Variables

Create a `.env` file in `frontend/test/life-rpg/` with your Firebase config:

```env
VITE_FIREBASE_API_KEY=your-api-key-here
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=your-app-id
```

Or edit `src/config/firebase.js` directly with your config values.

### 4. Firestore Security Rules

Update your Firestore security rules to protect user data:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users collection - users can only read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Profiles collection - users can only read/write their own profile
    match /profiles/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

## How It Works

1. **Sign Up**: User creates account → Firebase Auth stores credentials → Firestore stores user profile (using Auth UID as document ID)
2. **Sign In**: User authenticates → Firebase Auth validates credentials → App loads user profile from Firestore using Auth UID
3. **Profile Data**: All profile data (character sheet, skill tree, etc.) is stored in Firestore using the Firebase Auth UID as the document ID

## Architecture

- **Firebase Authentication**: Stores email/password securely (you never see passwords)
- **Cloud Firestore**: Stores user profile data (username, character sheet, skill tree, etc.)
- **Document ID = Auth UID**: The Firestore document ID matches the Firebase Auth UID for easy lookup


