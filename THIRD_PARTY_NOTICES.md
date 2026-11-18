# Third-party notices

The installer contains the official CPython 3.13.5 Windows x64 installer and PyPI wheels listed in `requirements-windows-lock.txt`. Each component remains under its own license. License metadata is available in the installed distributions and the included `third_party_licenses` inventory. CPython is distributed under the Python Software Foundation License.

The Windows installer bundles the unmodified official **xTB 6.7.1pre Windows x86-64** executable, its parameter files, and its required `libiomp5md.dll` under `runtime/xtb`. xTB is licensed under LGPL-3.0-or-later; the installer includes the upstream `COPYING`, `COPYING.LESSER`, exact v6.7.1 corresponding-source archive, binary/source URLs, and SHA-256 manifest. xTB remains a separate executable and its scientific results are explicitly distinguished from the JPCB GPR models and ORCA DFT data.

Upstream xTB release: https://github.com/grimme-lab/xtb/releases/tag/v6.7.1

xTB source and license: https://github.com/grimme-lab/xtb/tree/v6.7.1

The official Windows xTB archive also contains Intel's OpenMP runtime `libiomp5md.dll`. Intel documents the OpenMP runtime as a redistributable runtime component and documents private deployment of required runtime libraries. The installer retains the official unmodified DLL, identifies its checksum, and does not use Intel names for endorsement. See https://www.intel.com/content/www/us/en/developer/tools/oneapi/runtime-versions-download.html and the Intel oneAPI compiler deployment documentation.
