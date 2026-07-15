# File Inventory

All supplied game files have the host-interpreted timestamp
`1996-12-24 23:32:00 +0700`. The macOS `.DS_Store` file is host metadata and
is excluded. `file(1)` descriptions are heuristic; in particular, its
“Arhangel archive” label for `DDLE` is not treated as a format identification.

## Programs, data, and support files

| File | Bytes | SHA-256 | Current identification |
|---|---:|---|---|
| `CB.EXE` | 64,299 | `2b7726ae9cf56e0067533e4bd1c5c76685f1d9855a7d90835850388db7b07ee0` | EXEPACK-compressed DOS MZ program |
| `CB.ICO` | 766 | `81488f25bc2bfcdfbbb20091c2d9c3c48fb8be2ad5305dbc00c561f179a1780b` | 32×32, 16-color Windows icon |
| `CB.PIF` | 2,885 | `09818ec07f74adaf49ce5fb1ac31ea7be3fb5c157d04816217647db3d615013a` | Windows Program Information File |
| `DD1.DAT` | 1,866,068 | `a395fcf9f19d655a6440b5b8ab213983eb7d34a99810b763a9c95360f98f9562` | Main indexed resource container |
| `DDLA` | 10,065 | `b667b10536f2a7e9cb8b7d92afb8ef764fd2a4872703cb575129b05cf5616572` | Auxiliary game data; format pending |
| `DDLB` | 8,253 | `44a5ea34fed950e8265c1eb9eaa7e151941d98e934a39324d52de9d544dc364a` | Auxiliary game data; format pending |
| `DDLC` | 4,020 | `bc2ab554cf0dfdd999c7ac6e357551d693f900dc3f0bc67c8248dff99216e560` | Startup-loaded auxiliary data |
| `DDLD` | 14,973 | `bf4176fee554a9613a0423c5b5a2df07976ae1171950ba992296071da0220006` | Auxiliary game data; format pending |
| `DDLE` | 10,489 | `5a7de313baf42f50a47e06774aedc4e98969fc969673ea740b8cd27a77d3ea47` | Auxiliary game data; format pending |
| `DDLF` | 10,257 | `b4ab910df4ff59433ffcdca44f450cd91e50c10b540f0d810826e4e6e8610ffc` | Auxiliary game data; format pending |
| `DDLG` | 9,993 | `ab9e8ab9cb8c1bd8d1944dcc8383d045f9ddd7ee8670549d430a037c5299a4b6` | Auxiliary game data; format pending |
| `DDLR` | 696 | `067cfcfc63f07545e29d26a1d1773d2bd596d397663fd9716014ed4a48b28cc4` | Auxiliary game data; format pending |
| `MANUAL.TXT` | 36,384 | `5f2f583be150e5e6c73a5a760e1847b3986e8635e86175b4f82d8c9f70368a42` | Plain-text game manual |
| `SETSOUND.BAT` | 597 | `1d863472ef14a164966a93180bcb785ce32c0ce17a0321b6caf0892930fa18a1` | Sound configuration/install batch file |
| `SOUND.1` | 4,824 | `286ca4901bc2d3c18982b398ea5cef77920e4e542a834c6113902768c5d0e080` | DIGPAK Sound Blaster 16 COM driver |
| `SOUND.2` | 16,263 | `491896220f4d7284bcd213180bcb785ce32c0ce17a0321b6caf0892930fa18a1` | Miles Design Sound Blaster Pro FM driver |
| `SOUND.3` | 13,312 | `69796e9ceb0340bcb03799b49dfdbb4d604c3b22d8a2014e757faef07921427a` | MIDPAK COM package |
| `SOUND.4` | 3,622 | `3350419d0cec0c6c197d91e72340abb133f4de7cf00bff493c1f7ab9fb2ccef8` | MIDPAK timbre data |
| `SOUND.5` | 4 | `67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450` | Installation locks: `01 00 00 00` |

## Supplied saves

| File | Bytes | SHA-256 |
|---|---:|---|
| `DDGAMES.SV0` | 243 | `6f460832b488527a5cdc06d5860c10ff68509c9063ce0e88376757634f81ae43` |
| `DDGAMES.SV1` | 2,752 | `26a409ea52ec2f21363408d7ae8bf886bca70c318ec751b39b01e947776c9e54` |
| `DDGAMES.SV2` | 2,752 | `666cb666bec4290812cc8d2142755d58593e108f9d18daf47771f695de73237d` |
| `DDGAMES.SV3` | 2,752 | `33d2f0ea672255e30db017eb5b74f14a521bd0000eaf497d5c8179ba92a19cd8` |
| `DDGAMES.SV4` | 2,752 | `2102f392e43881001fc6b61097143ff09d9f869d1f7cdd7fc37b8102cdbe35d3` |
| `DDGAMES.SV5` | 2,752 | `238d409176200f50dd009cb739f7f6393491f3b0b92e7ee998a549ea4cea947d` |
| `DDGAMES.SV6` | 2,752 | `55c20b1824cbd7ea203dae82286a1999d1bd733b2e3f67a6a80fc44dcdd3cdee` |
| `DDGAMES.SV7` | 2,752 | `b339db79febc4e8fec6880325a0b3c5fc64abdd63ab813cde033071aa70aedde` |
| `DDGAMES.SV8` | 2,752 | `55c20b1824cbd7ea203dae82286a1999d1bd733b2e3f67a6a80fc44dcdd3cdee` |
| `DDGAMES.SV9` | 2,752 | `6139575d1cf94a76d64a730d7bf06dd9da7c2f1b5a66e5f386ef05afff04a0f3` |

`SV6` and `SV8` are byte-identical. `SV0` is the nine-record slot index;
`SV1` through `SV9` use the fixed state layout documented in the static
analysis chapter.
