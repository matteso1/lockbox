# LockBox Demo Script

Recording guide -- follow these steps in order. Keep it casual, talk through what you're doing.

---

## 1. LAUNCH (5 sec)

- Open LockBox.exe (or `python lockbox.py`)
- Let the spinning ASCII logo do its thing for a moment
- "This is LockBox -- fully offline password manager. No cloud, no accounts, no telemetry."

---

## 2. CREATE A VAULT (30 sec)

- The default vault path is already filled in (`~/.lockbox/vault.lockbox`)
- You're on the create screen -- point out the yellow warning box
- "Your master password is the only key. There's no recovery, no forgot password. The app actually warns you about this."
- Type a master password -- use something demo-friendly like `correct-horse-battery-staple`
- Point out the strength indicator updating live as you type -- "This uses Dropbox's zxcvbn library, same one the real world uses. It detects dictionary words, keyboard patterns, repeated characters -- not just length."
- Confirm the password
- Click **[CREATE NEW VAULT]**

---

## 3. FIRST LOOK -- EMPTY VAULT (10 sec)

- You're now in the main vault screen
- Point out the toolbar: FILE, ENTRY, TOOLS menus, the search bar, filter, GEN and LOCK buttons
- "Clean interface, everything is keyboard-friendly."

---

## 4. ADD ENTRIES (45 sec)

Add 3-4 entries to show it off. Use the ENTRY menu or right-click.

**Entry 1 -- GitHub:**
- ENTRY > Add Entry (or click the menu)
- Name: `GitHub`
- Username: `matteso1`
- Click **[GENERATE]** in the dialog to auto-generate a password
- URL: `https://github.com`
- Category: leave as General
- Save

**Entry 2 -- Gmail:**
- Name: `Gmail`
- Username: `yourname@gmail.com`
- Generate another password
- URL: `https://gmail.com`
- Category: Email
- Save

**Entry 3 -- Bank of America:**
- Name: `Bank of America`
- Username: `your_username`
- Generate password
- URL: `https://bankofamerica.com`
- Category: Finance
- Save

**Entry 4 -- AWS API Key:**
- Name: `AWS Production`
- Username: `AKIA...` (fake key ID)
- Password: paste in a fake secret key
- Category: API Keys
- Save

- "Four entries, four different categories -- notice the color coding."

---

## 5. SHOW CATEGORY COLORS (10 sec)

- Point out the different colors in the table for each category
- Click the **FILTER** button in the toolbar
- Filter to just "Finance" -- only Bank of America shows
- Filter back to "All"

---

## 6. SEARCH (10 sec)

- Click the search bar
- Type `git` -- GitHub entry filters in real time
- Clear the search
- Type `bank` -- Bank of America shows up
- Clear the search

---

## 7. COPY PASSWORD (15 sec)

- Right-click on GitHub entry
- Click "Copy Password"
- "Password copied. Notice the status bar -- it auto-clears the clipboard in 30 seconds. It also clears Windows clipboard history so it won't show up in Win+V."
- Wait a beat, then show the status bar updating when it clears

---

## 8. EDIT AN ENTRY (15 sec)

- Right-click GitHub > Edit
- Change the URL or add a note
- Save
- "Easy to update entries, and it saves to the encrypted vault immediately."

---

## 9. PASSWORD GENERATOR (20 sec)

- Go to TOOLS > Password Generator (or however it's accessed)
- Show the generator dialog
- Adjust the length slider -- make it 30 chars
- Toggle symbols off and on
- Click generate a few times -- "Cryptographically secure, uses Python's secrets module"
- Switch to passphrase mode
- Generate a passphrase -- "Diceware-style, four random words. Easy to remember, hard to crack -- that's the xkcd 936 idea."
- Copy one

---

## 10. IMPORT (15 sec)

- TOOLS > Import Passwords
- Show the import dialog
- "You can paste in CSV, pipe-delimited, key=value blocks -- it auto-detects the format."
- Paste in a quick example:
  ```
  Twitter | myuser | fakepass123 | https://twitter.com
  Reddit | reddituser | anotherpass | https://reddit.com
  ```
- Click Preview to show it parsed correctly
- Click Import
- "Boom, two more entries."

---

## 11. LOCK AND UNLOCK (15 sec)

- Click the **[LOCK]** button in the toolbar
- "Vault is locked. Everything is cleared from memory."
- You're back at the login screen
- Type your master password
- Click **[UNLOCK VAULT]**
- "Back in. All your entries are here."

---

## 12. SET UP 2FA (30 sec)

- Go to TOOLS > Setup 2FA
- A QR code appears on screen
- Open your authenticator app (Duo Mobile, Google Authenticator, whatever)
- Scan the QR code
- Type in the 6-digit code to verify
- "Now every login requires your master password AND a TOTP code. The TOTP secret is stored inside the encrypted vault, not in plaintext."
- Lock the vault
- Unlock again -- this time it asks for the 2FA code after the password
- Enter the code
- "Two-factor is live."

---

## 13. QUICK UNLOCK (10 sec)

- Lock the vault again
- This time notice the **[QUICK UNLOCK - 2FA ONLY]** button
- Click it -- only asks for the 2FA code, not the full password
- "30-day remember-me, protected by Windows DPAPI. Bound to your Windows user account."

---

## 14. CHANGE MASTER PASSWORD (15 sec)

- TOOLS > Change Master Password
- Enter current password
- Enter new password -- show the strength meter
- Confirm
- "Re-encrypts the entire vault with a new key. Argon2id, 64 megs of memory, 3 iterations."

---

## 15. CLOSE OUT (10 sec)

- "That's LockBox. AES-256-GCM, Argon2id, TOTP 2FA, fully offline. Single exe, no install. Free and open source."
- "Link in bio." (or wherever you're posting it)
- Close the app

---

## TIPS FOR RECORDING

- Keep the window at a comfortable size -- not maximized, not tiny
- Use a clean desktop or dark wallpaper so the Tokyo Night theme looks good
- If you stumble, just keep going -- it's a demo not a movie
- Talk about the security stuff casually, don't read it off like a spec sheet
- Total runtime target: 3-4 minutes
