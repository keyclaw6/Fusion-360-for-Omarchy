# Authentication

Authentication is not accepted until Fusion saves a new design to Autodesk cloud,
reopens it, and retains the account through a cold restart. A browser success page
or an Identity Manager log message alone is insufficient.

## Inspection on 26 September 2026

- No existing Fusion process was running at the start of inspection.
- The default host browser is Zen. Its normal desktop environment must be used
  for browser handoff; inherited Proton graphics and library variables previously
  prevented it from opening.
- The connected Chromium profile offers the user-requested Google account.
  Selecting it in a new disposable tab through Autodesk's ordinary Google sign-in
  flow redirected to the Autodesk profile site without a password or MFA prompt.
  The profile page rendered blank, so this establishes sign-in readiness only.
- The old Fusion180 installation records a completed sign-in on 10 September.
  Its cached Windows identity state has not been copied or reused elsewhere.
- The initial `adskidmgr` association pointed to the old Fusion180 handler. That
  handler chooses the newest installed runner, directly invokes Proton, and forces
  software graphics. It must not deliver a callback for the new installation.
- A separate old `fusion360-auth` helper invokes a launcher whose current code
  explicitly rejects authentication attachments. It is not a viable callback route.

## Required callback contract

The observed Autodesk callback uses the `adskidmgr` scheme, the `/login` path,
and `code` and `state` query fields. Values are credentials and must not appear in
logs, source, reports, command tracing, or public temporary files.

1. The desktop handler receives exactly one URI argument without `bash -c`,
   interpolation, or shell evaluation. It validates the scheme and callback shape.
2. It identifies the active installation's registered Identity Manager executable.
   It must not use the first executable found in a directory tree.
3. It invokes that executable with the URI as one argument through the same pinned
   GE-Proton/umu environment and prefix as the running Fusion session. A callback
   must never switch runtime or create another prefix.
4. Outgoing browser URLs use a host-side helper launched through the systemd user
   manager, allowing the host browser to inherit its normal desktop environment.
   Output is suppressed or redacted; the URL is never shell-evaluated.
5. Register only the required URI schemes with desktop utilities, record the prior
   associations, and restore them on removal if still owned by this package.
6. Keep TLS validation enabled. Do not transfer Windows credential caches or apply
   blanket browser sandbox workarounds.

## Fresh sign-in verified on 26 September 2026

The authentication agent operated the normal host Zen browser after an explicit
desktop-control handoff. The existing Google session for the account requested by
the user completed Autodesk sign-in without a password or MFA prompt. Activating
Open Product invoked the new URI handler and returned to the same running Fusion
installation. Identity Manager's pending window closed.

Identity Manager recorded `Completed login successfully` at 11:20:03 UTC and a
true logged-in response at 11:20:08 UTC. Fusion changed its title to Home. The
first captures still displayed a logo on black, so this establishes successful
sign-in and callback delivery, not correct workspace rendering or full acceptance.

No credential-cache transfer, callback extraction, account-security change, or
prefix modification was used to complete this flow. Keyboard navigation worked
while Fusion's floating windows visually covered the browser.

## Subsequent application checks

The fresh sign-in persisted across multiple cold Fusion/runtime starts. The
corrected renderer reached the signed-in design workspace. A new 64-plate test
design was saved through Fusion's ordinary Save dialog in a dedicated validation
folder. Fusion reported a complete cloud file at version 1, no unsaved changes,
and restored all 64 solid plates after the document was closed and reopened.
See `../validation/README.md` for the geometry and file-round-trip evidence.

The final production launcher still needs a cold-start/cloud-reopen review.
No sign-out, credential deletion or account-security change was needed.

## Installed bridge checks

The permanent WineBrowser helper was invoked through the live Fusion runtime's
`winebrowser.exe`. It opened Autodesk's official Fusion page in the host Zen
browser; the normal host desktop environment was preserved. The runtime must
load the host systemd libraries from both `/run/host/usr/lib` and its `systemd`
subdirectory. Its helper child drops `XDG_RUNTIME_DIR` while retaining the
session D-Bus address, allowing systemd's supported public-session-bus fallback.
No extra runtime mounts or desktop-wide environment changes were required.

The new `adskidmgr` and `fusion360` defaults are installed, their predecessors
recorded privately, and both effective defaults verified with `xdg-mime`.
Desktop entries invoke `/usr/bin/python3` with a quoted helper pathname to avoid
the installed xdg-utils parser's rejection of a quoted first executable token.
An isolated regression test includes a competing old callback handler and
verifies literal argument delivery through a helper path containing spaces.

These bridge checks establish browser launching and desktop registration;
the fresh callback and cloud checks above establish actual application sign-in.

## Initial sign-in display investigation

The fresh 2705.1.25 installation initialized Identity Manager successfully and
received `IsLoggedIn: false`. Fusion's server-time check and service-health
requests returned HTTP 200. There was no Identity Manager login request while
only the startup image was visible, placing that symptom before browser handoff.

Inspection of the installed `NuBase10.dll` identified the initial welcome screen
as `QTSignInDialog`, built with native Qt widgets, including a `signin_button`.
This is separate from Identity Manager's WebView2 stage. The main implementation
agent subsequently observed the welcome text and Sign In button after moving and
resizing the window and taking a fresh capture. Initial exposure/repainting needs
cold-launch verification; this observation does not establish authentication.
