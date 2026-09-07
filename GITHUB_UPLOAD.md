# Uploading Signal Audio to GitHub

Suggested repository name: `signal-audio`.

1. Extract `signal-audio-0.3.0-source.zip`.
2. Create an empty GitHub repository. The source already includes a README,
   MIT license, and `.gitignore`, so do not generate duplicates.
3. Upload the **contents** of the extracted `signal-audio-0.3.0` folder to
   the repository root. Include the hidden `.github`, `.gitignore`, and
   `.gitattributes` entries. Use Git for an easier complete upload:

   ```powershell
   git init -b main
   git add .
   git commit -m "Initial Signal Audio release"
   git remote add origin YOUR_GITHUB_REPOSITORY_URL
   git push -u origin main
   ```

4. Confirm the Windows CI checks pass on GitHub.
5. Create a release tagged `v0.3.0` with notes from `CHANGELOG.md`.
6. Before public binary distribution, complete the dependency corresponding-source
   review described in `THIRD_PARTY_NOTICES.md`. The source project can be
   uploaded independently. Attach `signal-audio-0.3.0-windows-x64.zip` and `SHA256SUMS.txt` to the
   release. The executable ZIP belongs in release assets, not in Git history.
   You may also attach the source ZIP so both checksum entries are available.

No repository has been created or published by the local build process.
The source package uses an explicit file allowlist and excludes recordings,
transcripts, local settings, virtual environments, cached models, and secrets.
Do not upload your working folder wholesale. Windows binaries are unsigned;
there is no bundled signing certificate, updater, telemetry, or account login.
