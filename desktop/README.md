# Shadow Helper (desktop app)

Lets your Shadow account run a hidden Google Chrome on your Windows or Mac laptop and use only the folders you pick. It does not use your mouse or keyboard.

## Get the installer
1. Push this project to GitHub with **Save to GitHub**.
2. The **Build Shadow Helper** workflow runs on its own (GitHub → Actions). You can also start it by hand with **Run workflow**.
3. Open GitHub → **Releases** and download one of these files:
   - Windows: `ShadowHelper-Setup-Windows.exe`
   - Mac (M1/M2/M3): `ShadowHelper-mac-apple-silicon.dmg`
   - Mac (Intel): `ShadowHelper-mac-intel.dmg`

## Set it up
1. Install Google Chrome if it isn't already on the computer.
2. Install and open Shadow. It opens in its own window straight away; its settings panel stays in the taskbar / Dock.
3. Sign in inside the Shadow window and press **Link computer**. (You can still paste a connection code from the **Laptop** panel instead.)
4. Add the folders Shadow may use. Downloads are saved to the folder you mark.
5. Optional: close Chrome, then press **Copy my Chrome logins now**.

The builds are not code-signed yet, so the first launch shows a warning:
- Windows: More info → Run anyway
- Mac: right-click → Open

## Automatic updates
Each build on GitHub gets a higher version number (`1.0.<build number>`) and becomes the **latest** Release, along with a `checksums.txt` file. Installed helpers check GitHub every 6 hours, or right away when you press **Check for updates**. A new version is downloaded and checked against `checksums.txt`. It installs once Shadow has had no task activity for 10 minutes, and then the helper restarts itself. This only works when the GitHub project is **public**.

## Turning on code signing later
The build signs the installers by itself as soon as these **GitHub → Settings → Secrets and variables → Actions** secrets exist. Until then it builds unsigned installers.

| Platform | Secret | What it is |
|---|---|---|
| Mac | `MACOS_CERT_P12` | Your "Developer ID Application" certificate exported as .p12, then base64-encoded (`base64 -i cert.p12`) |
| Mac | `MACOS_CERT_PASSWORD` | Password of that .p12 |
| Mac | `MACOS_SIGN_IDENTITY` | e.g. `Developer ID Application: Your Name (TEAMID)` |
| Mac | `APPLE_ID`, `APPLE_APP_PASSWORD`, `APPLE_TEAM_ID` | Apple ID email, an app-specific password from appleid.apple.com, and your Team ID (used for notarization) |
| Windows | `WIN_CERT_PFX` | Code signing certificate (.pfx), base64-encoded |
| Windows | `WIN_CERT_PASSWORD` | Password of that .pfx |

## Run from source (developers)
```
cd desktop && pip install -r requirements.txt
cp ../backend/shadow_browser.py shadow_helper/
python shadow_helper/main.py
```
