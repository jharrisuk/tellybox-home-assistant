# Tellybox for Home Assistant

A small, read-only Home Assistant custom integration for Tellybox. It polls one versioned statistics endpoint every 30 seconds and exposes aggregate stream, download, upload and server health values.

This is a custom repository. It is not an official Home Assistant integration and it is not in the default HACS catalogue. Add the repository URL manually as described below.

## Requirements

- Home Assistant 2026.10.0 or newer. The configuration flow uses `probatio`, the schema library used by Home Assistant config flows from 2026.10. Home Assistant 2026.9 and earlier used `voluptuous` and cannot load this flow.
- HACS, or the Marketplace built into Home Assistant 2026.11 and newer.
- A Tellybox server that provides `GET /api/integrations/home-assistant/stats` with schema version 1.
- A dedicated read-only Home Assistant token created in the existing Tellybox installation settings.
- Network access from Home Assistant to the Tellybox viewing address on port 8082.

## Create the Tellybox token

1. Open your existing Tellybox installation settings at `http://SERVER_IP:8990` and sign in as the installation administrator. Local viewing on port 8082 does not grant administrator access.
2. Find the **Home Assistant** section and choose **Create token**.
3. Copy the token immediately. It is shown only once. If you lose it, rotate the token in Tellybox and update the integration.

The token is read-only, revocable and separate from viewer cookies, app access tokens and the installation administrator password. There is no local-network bypass: a request without the bearer token receives `401`, even from the server itself.

## Install from this custom repository

The repository URL is:

```text
https://github.com/jharrisuk/tellybox-home-assistant
```

### Install through HACS

1. In Home Assistant, open **HACS > Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add the repository URL above with category **Integration**.
4. Search for **Tellybox** in HACS and choose **Download**.
5. Restart Home Assistant. A newly downloaded or updated custom integration is not loaded until Home Assistant restarts.
6. Open **Settings > Devices and services > Add integration**, search for **Tellybox**, then enter the details below.

### Install through the Marketplace (Home Assistant 2026.11 or newer)

1. Open **Settings > Marketplace**.
2. Select **Add from link** in the upper-right corner.
3. Enter the repository URL above and select **Add**. The Marketplace asks you to connect GitHub if needed.
4. Open the **Tellybox** repository and select **Install**.
5. Restart Home Assistant if the Marketplace asks for a restart.
6. Open **Settings > Devices and services > Add integration**, search for **Tellybox**, then enter the details below.

### Add the integration entry

Enter:

- **Server address:** `http://SERVER_IP:8082` (use `https://` if the address crosses an untrusted network)
- **Home Assistant token:** the token from the step above

The integration validates the address and token before creating the config entry. It uses the server's stable installation ID as the Home Assistant unique ID, so the same server is not added twice.

If the token is rotated or revoked, Home Assistant shows a reauthentication prompt. Enter the current token there. To change the server address or token later, use **Reconfigure** on the integration entry. Both flows keep the same installation identity and abort if the token belongs to a different Tellybox installation.

## Updates and releases

- HACS or the Marketplace offers an update when a new GitHub release is published. The repository version is `0.1.0`.
- Choose **Update**, then restart Home Assistant. Replacing files alone does not reload the Python integration. The Marketplace shows a repair when a restart is needed.
- HACS and the Marketplace use published GitHub releases. A tag without a published release is not enough.
- This repository is not in the default catalogue. Every user must add the custom repository URL above. It is not discovered, installed or updated automatically outside HACS or the Marketplace.

## What it reads

The integration only calls `GET /api/integrations/home-assistant/stats`. It never reads the normal viewer API and exposes only these aggregate values:

- Active, connected, local and remote stream counts.
- Active download count.
- Measured remote upload rate and the configured upload cap.
- Tellybox service uptime.
- Host CPU and memory percentages from the existing host-health collector.
- Available bytes for each host disk, keyed by a stable sanitised disk ID.
- An optional connectivity binary sensor.

It does not expose viewing titles, history, account details, IP addresses, file paths, provider URLs or any write action.

## Entities

Entity IDs depend on the config entry title, which includes the server address. Use the entity IDs shown in Home Assistant.

| Translation key | Typical entity | Meaning |
| --- | --- | --- |
| `active_streams` | `sensor...active_streams` | Playback sessions currently playing. |
| `connected_streams` | `sensor...connected_streams` | Sessions inside the server's recent window, including paused sessions. |
| `local_streams` | `sensor...local_streams` | Connected sessions using the direct local media route. |
| `remote_streams` | `sensor...remote_streams` | Connected sessions using the remote relay route. |
| `active_downloads` | `sensor...active_downloads` | Current downloads. |
| `measured_remote_upload` | `sensor...measured_remote_upload` | Measured remote upload in Mbit/s. |
| `configured_upload_limit` | `sensor...configured_upload_limit` | Configured upload cap in Mbit/s. `0` means unlimited. |
| `uptime` | `sensor...uptime` | Tellybox service uptime. |
| `cpu_usage` | `sensor...cpu_usage` | Host CPU percentage. |
| `memory_usage` | `sensor...memory_usage` | Host memory percentage. |
| Disk sensor | `sensor...available_space` | Free bytes for one disk. |
| `online` | `binary_sensor...online` | Whether the last statistics poll succeeded. |

A value is unavailable when the server reports it as missing or stale. The integration does not turn missing CPU, memory, uptime or disk readings into zero. A real zero, such as no active streams, remains `0`.

See `dashboard-example.yaml` for a simple entities card. Replace the example entity IDs with the ones Home Assistant created.

## Troubleshooting

- **`invalid_auth`:** the token was revoked, rotated or copied incorrectly. Create or rotate a token in Tellybox installation settings.
- **`cannot_connect`:** check the address, port 8082, Docker port publishing and Home Assistant network access.
- **`invalid_response`:** the server is older than the stats schema, or a proxy returned HTML. Check that the address points at Tellybox directly and that the endpoint path is correct.
- **CPU, memory or disk sensors unavailable:** the host-health collector has not written a fresh sample. Tellybox service uptime can remain available while host readings are missing.
- **Integration will not load:** confirm Home Assistant is 2026.10.0 or newer. Earlier releases do not provide the schema library used by this config flow.
- **Update downloaded but nothing changed:** restart Home Assistant after the HACS update.

## Remove

1. Remove the Tellybox integration entry in **Settings > Devices and services**.
2. Remove the repository in HACS.
3. Restart Home Assistant.

## Development checks

From the repository root:

```text
python -m pytest
```

The test suite covers URL and token validation, the statistics allowlist, failure mapping, config and reconfiguration flows, entity translation keys and packaging requirements. CI also runs the HACS validation action and hassfest.

The HACS validation workflow skips the `brands` and `license` checks. No brand asset is bundled, and the PolyForm Noncommercial licence is not OSI-approved, so the repository cannot be submitted to the default HACS catalogue. Custom repository installation does not require those checks.

## Licence

The integration, tests and documentation in this repository are source-available under the PolyForm Noncommercial License 1.0.0. See `LICENSE`, `NOTICE` and `LICENSE-SCOPE.md`. This is not an OSI-approved open-source licence. Commercial use requires separate permission from the rightsholders. Third-party components, including Home Assistant and HACS, remain under their own licences.

