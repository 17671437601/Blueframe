# BlueFrame Studio

BlueFrame Studio is a new, modular Windows desktop application for local-first video production. It is implemented independently beside the packaged legacy application; the legacy files are evidence only and are never modified by this repository.

## Foundation status

Implementation follows `../docs/superpowers/plans/2026-11-03-blueframe-foundation-implementation.md`.

The foundation includes the blue Vue workbench, a protected loopback FastAPI service, durable recoverable jobs, account/provider extension points, and a pywebview Native launcher. Media editing pipelines and the Volcengine production adapter are the next roadmap phases; the current shell does not yet render real video.

## Development

From PowerShell:

```powershell
.\scripts\verify.ps1
.\scripts\smoke.ps1
.\scripts\dev.ps1
```

`dev.ps1` builds the Vue application and opens the Native pywebview window. The per-launch API token is transferred through an in-memory bridge and is never stored in the URL or browser storage. Secrets, media outputs, databases, and local environment files must not be committed.

## Foundation acceptance

- Deep navy navigation, bright blue actions, pale workspace, white panels, and Chinese UI copy are implemented independently from the legacy layout.
- The desktop contract uses a 1366×768 initial window when space permits and a 1024×700 minimum; browser tests cover both sizes and offline recovery.
- The local API binds only to `127.0.0.1`, requires a random per-launch token, and shuts down with the window.
- Automated smoke checks cover migrations, health, protected API access, readonly account mode, job creation, lease expiry, and recovery.
