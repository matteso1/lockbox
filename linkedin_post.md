I was storing passwords in a text file. Decided that was probably bad. So I built an offline password manager instead of paying someone else to lose my credentials in their next breach.

LockBox. Single .exe, runs locally, no cloud, no accounts, no telemetry. Your vault is one AES-256-GCM encrypted file on disk. Argon2id key derivation at 64MB memory cost. Nothing touches the network. Ever.

Here's what it actually does for you:
- Generates cryptographically secure passwords so you stop reusing the same one everywhere (you know you do)
- Built-in TOTP two-factor auth -- you already have Duo Mobile or Google Authenticator on your phone, now actually use it
- 30-day quick unlock so you punch in a 6-digit code instead of your master password every time you open it
- One-click copy with auto-clear so your passwords aren't sitting in your clipboard forever
- Import your existing passwords from CSV so you can migrate in 30 seconds
- Passphrase generator for people who hate remembering random strings (look up xkcd 936)

The threat model is simple: no server means no server to breach. No API means no API to exploit. No account recovery means no account recovery to social engineer. The only attack surface is your own machine, and if someone owns your machine you've got bigger problems than your password manager.

Would I store nuclear launch codes in it? No. It's a Python app, not a hardened HSM. But it's a hell of a lot better than passwords.txt on my desktop, and I don't have to trust some company that'll get acquired next year and change their privacy policy at 2am on a Friday.

The known limitations are documented in the README because I'd rather tell you what it can't do than pretend it does everything. ~3000 lines of Python, MIT licensed, fully auditable. If you're at UW-Madison and you already suffer through Duo every day -- at least now you can get some value out of that app.

https://github.com/matteso1/lockbox
Download the .exe and try it: https://github.com/matteso1/lockbox/releases/latest

#cybersecurity #python #opensource #passwordmanager #infosec
