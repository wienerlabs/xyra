# Xyra signing and notarization

Because Xyra is self-built, it is ad-hoc signed by default. Consequences: antivirus (Bitdefender/Avast) may flag it as a virus, macOS may reset keychain and permissions on every build (GitHub sign-in is asked again), and Gatekeeper shows a warning.

Root fix: sign with an Apple Developer ID and notarize. Zed's `bundle-mac` script already does this; you only need to supply the credentials as environment variables.

## Prerequisites (one-time setup)

1. **Apple Developer Program membership** ($99/year): https://developer.apple.com/programs/
2. **Developer ID Application certificate**:
   - Create a "Developer ID Application" certificate via Xcode or developer.apple.com.
   - Export it from Keychain Access as a `.p12` (set a password).
   - Base64-encode it: `base64 -i certificate.p12 | pbcopy`
3. **App Store Connect API key** (for notarytool):
   - App Store Connect > Users and Access > Integrations > App Store Connect API > new key (`.p8`).
   - Note the Key ID, Issuer ID and Team ID.
   - Base64-encode it: `base64 -i AuthKey_XXXX.p8 | pbcopy`

## Usage

Set these environment variables before building (for example add them to `~/.zshrc`, or export them before the build):

```bash
export XYRA_TEAM_ID="ABCDE12345"                 # Apple Team ID
export MACOS_CERTIFICATE="<p12 base64>"          # Developer ID Application .p12
export MACOS_CERTIFICATE_PASSWORD="<p12 password>"
export APPLE_NOTARIZATION_KEY="<p8 base64>"      # App Store Connect API .p8
export APPLE_NOTARIZATION_KEY_ID="<key id>"
export APPLE_NOTARIZATION_ISSUER_ID="<issuer id>"
```

Then build as usual:

```bash
./build/build-xyra.sh
```

With these variables set, bundle-mac automatically deep-signs with the hardened runtime, submits to Apple with notarytool, and staples the ticket. The result: AV no longer flags it, no Gatekeeper warning, and keychain and permissions persist.

If the variables are not set, an ad-hoc signed build is produced (current behavior), and nothing breaks.
