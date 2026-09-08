<p align="center">
  <img src="https://raw.githubusercontent.com/MustardSeedNetworks/.github/main/profile/logo.svg" width="96" alt="Mustard Seed Networks">
</p>

<h1 align="center">Mustard Seed Networks</h1>

<p align="center"><strong>Visibility. Performance. Assurance.</strong></p>

<p align="center">
Software-first network visibility, performance testing, and simulation tools —
engineered for engineers who need deterministic, standards-aligned results.
</p>

## Products

| Product | What it does | Repo |
| --- | --- | --- |
| **Seed** | Portable network diagnostics: link, switch, DHCP, DNS, Wi-Fi troubleshooting, and security posture from any network jack. Safe to run on clinical and industrial networks. | [seed](https://github.com/MustardSeedNetworks/seed) |
| **Stem** | Standards-aligned performance testing: RFC 2544, ITU-T Y.1564, Y.1731, RFC 6349, MEF, and TSN. Reflector, generator, and certifier in one binary. | [stem](https://github.com/MustardSeedNetworks/stem) |
| **NIAC** | Network In A Can: a single-binary device simulator that speaks real protocols (ARP, DHCP, DNS, SNMP, LLDP, CDP, STP, and more) on real interfaces for testing, training, and lab work. | [niac-go](https://github.com/MustardSeedNetworks/niac-go) |
| **Trellis** | Wi-Fi site survey, heatmaps, and predictive planning. Pre-alpha. | [trellis](https://github.com/MustardSeedNetworks/trellis) |

Every product ships as one Go binary with an embedded web UI, runs on macOS,
Linux, and Windows, and validates licenses offline. Nothing phones home, so
air-gapped clinical, industrial, and government networks are first-class.

## Shared infrastructure

| Repo | Purpose |
| --- | --- |
| [foundation](https://github.com/MustardSeedNetworks/foundation) | Ed25519 license validation and per-session CSRF shared by the fleet |
| [.github](https://github.com/MustardSeedNetworks/.github) | Fleet-wide CI, Renovate policy, and reusable workflows |

## Licensing

Products are **source-available** under the Business Source License 1.1.
Free tiers are free to use; Pro tiers are licensed per year with keys that
validate locally. See each repo's `LICENSE` for the exact terms.

## Security

Report vulnerabilities privately through the affected repo's
[security advisories](https://github.com/MustardSeedNetworks/seed/security/advisories/new)
page or by email to `kris.armstrong@icloud.com`. See [SECURITY.md](https://github.com/MustardSeedNetworks/.github/blob/main/SECURITY.md).

<p align="center"><a href="https://mustardseednetworks.com">mustardseednetworks.com</a></p>
