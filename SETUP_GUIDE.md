# 🤖 Dainik Saar 100% Free & Fully Automated News Publisher

This automated system fetches new articles from **Tishha News** (`https://tishhanews.com/feed/`), uses **Google Gemini AI** (Free Tier) to rewrite the headline, content, and generate SEO keywords (0% plagiarism & zero copyright issues), and automatically posts them to **Dainik Saar** (`https://dainiksaar.blogspot.com/`).

---

## 💰 Total Cost: $0.00 / ₹0.00 Forever

| Tool | Purpose | Free Quota |
| :--- | :--- | :--- |
| **Google Gemini AI** | Rewrites news, creates headlines & tags | 1,500 requests / day (Free at Google AI Studio) |
| **HD Editorial Images** | Authentic news photo from source article + Unsplash HD (1200x675) | 100% Free & Unlimited (Zero credentials needed) |
| **Blogger Post-by-Email** | Official Blogger publishing & image upload | 100% Free native Blogger feature |
| **Gmail SMTP** | Sends formatted post + image to Blogger | 500 emails / day (Free) |
| **GitHub Actions** | Runs the entire pipeline 24/7 in the cloud | 2,000 free minutes / month (we use ~120 min) |

---

## 🔑 Step 1: Get Your 3 Free Keys (Takes 3 Minutes)

### 1. Google Gemini API Key (100% Free)
1. Visit **[Google AI Studio](https://aistudio.google.com/)**.
2. Sign in with your Google account.
3. Click **"Get API key"** → **"Create API key in new project"**.
4. Copy your key (`AIzaSy...`).

---

### 2. Blogger "Post Using Email" Secret Address
1. Go to **[Blogger Dashboard](https://www.blogger.com/)** → Select **Dainik Saar**.
2. Go to **Settings** (बाएं मेनू में सेटिंग्स पर जाएं).
3. Scroll down to the **"Email"** section (ईमेल सेक्शन में स्क्रॉल करें).
4. Find **"Post using email"** (ईमेल का उपयोग करके पोस्ट करें):
   * Select **"Publish email immediately"** (तुरंत ईमेल प्रकाशित करें).
   * Type a secret word (e.g. `secretnews123`).
   * Your secret email will look like: `yourname.secretnews123@blogger.com`.
   * Click **Save**.

---

### 3. Gmail App Password (To Send Articles to Blogger)
1. Go to your **[Google Account Security](https://myaccount.google.com/security)**.
2. Make sure **2-Step Verification** is turned ON.
3. Search for **"App passwords"** in the top search bar (or visit: `https://myaccount.google.com/apppasswords`).
4. Enter an app name: `Blogger Bot` and click **Create**.
5. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`).

---

## 🧪 Step 2: Test on Your PC Right Now

You can test it on your computer by setting the environment variables in PowerShell:

```powershell
$env:GEMINI_API_KEY="YOUR_GEMINI_KEY"
$env:BLOGGER_EMAIL="yourname.secretnews123@blogger.com"
$env:SENDER_EMAIL="yourgmail@gmail.com"
$env:SENDER_APP_PASSWORD="your 16 character app password"

python autopost.py
```

Check your blog at `https://dainiksaar.blogspot.com/` — the newly rewritten article will appear published instantly!

---

## ☁️ Step 3: Make it Run 24/7 in the Cloud (Zero Cost)

To make it run automatically every 2 hours **without keeping your laptop or computer on**:

1. Create a **Private Repository** on **[GitHub.com](https://github.com/)** (e.g. `dainik-saar-autopost`).
2. Upload all files from this folder (`autopost.py`, `posted_history.json`, and `.github/workflows/autopost.yml`).
3. In your GitHub repository:
   * Go to **Settings** → **Secrets and variables** → **Actions**.
   * Click **"New repository secret"** and add these 4 secrets:
     * `GEMINI_API_KEY`: Your Gemini API key.
     * `BLOGGER_EMAIL`: Your secret Blogger publishing email.
     * `SENDER_EMAIL`: Your personal Gmail address.
     * `SENDER_APP_PASSWORD`: Your 16-character Gmail App Password.
4. **Done!** GitHub Actions will now automatically wake up every 2 hours, check for new posts on `tishhanews.com`, rewrite them with Gemini AI, post them to Blogger, and go back to sleep.
