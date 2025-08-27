# Getting Your Clerk Token - Step by Step Guide

## 🔍 Your Clerk Configuration

Based on the API response, your Clerk app (`poetic-primate-48.clerk.accounts.dev`) is configured to only support:
- ✅ Google OAuth (`oauth_google`)
- ✅ Ticket-based authentication (`ticket`)
- ❌ Email/Password authentication (not enabled)

## 🎯 Recommended Method: Browser Console

This is the easiest and most reliable method:

### Step 1: Sign in via Google OAuth
1. Open your browser
2. Go to: `https://poetic-primate-48.clerk.accounts.dev`
3. Click "Sign in with Google"
4. Complete the Google OAuth flow

### Step 2: Get the Token
1. Once signed in, open Developer Tools (Press F12)
2. Go to the **Console** tab
3. Paste this command and press Enter:
   ```javascript
   window.Clerk.session.getToken().then(token => console.log('TOKEN:', token))
   ```
4. Copy the token (the long string after "TOKEN:")

### Step 3: Test Your API
```bash
python test_current_api.py http://localhost:8000/api/v1 YOUR_TOKEN_HERE
```

## 🚀 Quick Start Scripts

### Option A: Use the OAuth Helper
```bash
python get_clerk_token_oauth.py
```
Choose option 2 (Manual browser method)

### Option B: Use the Simple Helper
```bash
python get_token_simple.py
```
Choose option 1 (Browser Console Method)

## 📋 Complete Example

1. **Open browser and sign in:**
   - Go to: https://poetic-primate-48.clerk.accounts.dev
   - Sign in with Google

2. **Get token in console:**
   ```javascript
   window.Clerk.session.getToken().then(token => console.log('TOKEN:', token))
   ```

3. **Copy the token** (looks like: `eyJhbGciOiJSUzI1NiIsImtpZCI6Imluc18...`)

4. **Test your API:**
   ```bash
   python test_current_api.py http://localhost:8000/api/v1 eyJhbGciOiJSUzI1NiIsImtpZCI6Imluc18...
   ```

## 🔧 Why Email/Password Didn't Work

The API response showed:
```json
{
  "status": "needs_identifier",
  "supported_first_factors": [
    {"strategy": "ticket"},
    {"strategy": "oauth_google"}
  ]
}
```

This means your Clerk app is configured to only allow:
- Google OAuth sign-in
- Ticket-based authentication (for programmatic access)

Email/password authentication is not enabled in your Clerk dashboard.

## 🎯 Next Steps

Once you have your token:

1. **Test basic connectivity:**
   ```bash
   python test_current_api.py http://localhost:8000/api/v1 YOUR_TOKEN
   ```

2. **Test video generation:**
   ```bash
   python test_video_generation.py --base-url http://localhost:8000/api/v1 --token YOUR_TOKEN --quick
   ```

3. **Run comprehensive tests:**
   ```bash
   python test_video_generation.py --base-url http://localhost:8000/api/v1 --token YOUR_TOKEN
   ```

## 💡 Pro Tips

- **Tokens expire**: You may need to get a fresh token periodically
- **Save your token**: The scripts will save it to `auth_token.txt` for reuse
- **Use the browser method**: It's the most reliable approach
- **Check token format**: Valid tokens start with `eyJ`

## 🆘 Troubleshooting

**If the browser console method doesn't work:**
1. Make sure you're signed in to your app
2. Check that `window.Clerk` exists by typing it in console
3. Try refreshing the page after signing in
4. Make sure you're on the correct domain

**If you get "Clerk not found" errors:**
1. Make sure you're on a page where Clerk is loaded
2. Try going to the main app page after signing in
3. Check the Network tab for any Clerk-related requests