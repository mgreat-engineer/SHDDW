# RCA — shddw.com SSL (ERR_SSL_VERSION_OR_CIPHER_MISMATCH)

## Problem statement
User reports the custom domain `shddw.com` shows Chrome `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`
("unsupported protocol"). App deployed at https://polar-mimic.emergent.host. Asked to verify
linkage, DNS, and SSL for both apex and `www`. No redeploy.

## Evidence gathered
- **describe_deployment_state**: deployment `polar-mimic` active; active run `57af2ec7…` status
  success; frontend_type cloudflare; both `shddw.com` and `www.shddw.com` show `verified:true`.
- **preview_health_check** (default URL): `https://polar-mimic.emergent.host/` → **200**,
  ~516ms, serves real app HTML. App is healthy.
- **list_domains**: both domains → `verified:true`, `provider:"cloudflare"`,
  **`ssl_status:"active"`**, `ssl_validation_method:"http"`, each with a live
  `cf_custom_hostname_id`. Apex (`shddw.com`) + subdomain (`www.shddw.com`) both present.
- **check_domain_status**: `shddw.com` → `linked:true`, `www.shddw.com` → `linked:true`
  (A records resolve to our target).

## Root cause
Everything on the Emergent/Cloudflare side is correct: the custom hostnames are verified, the
A records point at our target, and the SSL certificates are **issued and active** for both the
apex and `www`. Therefore the TLS handshake failure the browser reports is NOT a pending cert
and NOT a mislinked domain on our side.

`ERR_SSL_VERSION_OR_CIPHER_MISMATCH` with an active cert on our edge is an edge/client-side
conflict in front of our termination. Most likely one (or more) of:
1. **Stale cached DNS / connection** — SSL went active recently (deployment updated 2026-11-11);
   the user's browser/OS/resolver may still be hitting an old IP that does not terminate TLS for
   this hostname.
2. **A leftover AAAA (IPv6) record** pointing at an old/previous host. Browsers prefer IPv6;
   a stale AAAA that doesn't serve this cert produces exactly this error. Our A-record check
   does NOT inspect AAAA, so such a record would be invisible to `check_domain_status` yet still
   break the handshake.
3. **The zone proxied through the user's own Cloudflare account (orange cloud)** — TLS would then
   terminate at the user's Cloudflare edge, where no valid cert for shddw.com exists, instead of
   at our custom-hostname edge.

Note: our tooling cannot perform a live external TLS handshake, so items 1–3 are inferred from
the combination of (SSL active on our side) + (A records linked) + (browser cipher mismatch).
This was not reproduced from the client side.

## Fixes (all User-side; do NOT redeploy)
1. **Clear stale state first (test_and_verify):** flush local DNS cache and retry in an incognito
   window / on a different network (e.g. mobile data). If it loads there, it was purely cached
   state and will clear with propagation (allow up to a few hours, worst case 24h).
2. **Clean up DNS records (domain_related_issue):** at the registrar/DNS provider, keep ONLY the
   record(s) Emergent instructed in the Domains tab. Remove any leftover/duplicate A records and,
   importantly, any **AAAA (IPv6) record** pointing to an old host.
3. **Disable any Cloudflare proxy (domain_related_issue):** if shddw.com is managed in the user's
   own Cloudflare zone, set the record to **DNS-only (grey cloud)**, not proxied (orange cloud);
   if they insist on proxying, set that zone's SSL mode to Full (strict). Then wait for
   propagation.

The default URL https://polar-mimic.emergent.host keeps working throughout — the app is not down.
