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
2. Install and open Shadow Helper.
3. In Shadow, open the **Laptop** panel, press **Get connection code**, and paste the code into the helper. Then press **Link**.
4. Add the folders Shadow may use. Downloads are saved to the folder you mark.
5. Optional: close Chrome, then press **Copy my Chrome logins now**.

The builds are not code-signed yet, so the first launch shows a warning:
- Windows: More info → Run anyway
- Mac: right-click → Open

## Run from source (developers)
```
cd desktop && pip install -r requirements.txt
cp ../backend/shadow_browser.py shadow_helper/
python shadow_helper/main.py
```
