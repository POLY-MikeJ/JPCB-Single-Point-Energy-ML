"""Stage the verified official xTB 6.7.1pre Windows runtime for an installer."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, tempfile, zipfile
from pathlib import Path

EXPECTED_ARCHIVE_SHA256="043e578da4a7e114a4d584972959a875e3ffb9f2767a86723b95aa6719d28d9c"
UPSTREAM_URL="https://github.com/grimme-lab/xtb/releases/download/v6.7.1/xtb-6.7.1pre-windows-x86_64.zip"
SOURCE_URL="https://github.com/grimme-lab/xtb/tree/v6.7.1"

def sha256(path: Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()

def unique(root: Path,name: str)->Path:
    matches=list(root.rglob(name))
    if len(matches)!=1: raise RuntimeError(f"Expected exactly one {name}; found {len(matches)}")
    return matches[0]

def stage(binary_archive: Path,source_archive: Path,destination: Path)->dict:
    actual=sha256(binary_archive)
    if actual.lower()!=EXPECTED_ARCHIVE_SHA256: raise RuntimeError(f"Official xTB archive hash mismatch: {actual}")
    if destination.exists() and any(destination.iterdir()): raise RuntimeError(f"Destination must be new or empty: {destination}")
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="zhu-xtb-stage-") as temporary:
        extracted=Path(temporary)/"binary"; source=Path(temporary)/"source"
        with zipfile.ZipFile(binary_archive) as archive: archive.extractall(extracted)
        with zipfile.ZipFile(source_archive) as archive: archive.extractall(source)
        executable=unique(extracted,"xtb.exe"); runtime_root=executable.parent.parent
        shutil.copy2(executable,destination/"xtb.exe")
        dll=unique(extracted,"libiomp5md.dll"); shutil.copy2(dll,destination/dll.name)
        shutil.copytree(runtime_root/"share"/"xtb",destination/"share"/"xtb")
        license_dir=destination/"licenses"; license_dir.mkdir()
        shutil.copy2(unique(source,"COPYING"),license_dir/"xTB_GPL-3.0.txt")
        shutil.copy2(unique(source,"COPYING.LESSER"),license_dir/"xTB_LGPL-3.0.txt")
        shutil.copy2(source_archive,license_dir/"xtb-v6.7.1-corresponding-source.zip")
    completed=subprocess.run([str(destination/"xtb.exe"),"--version"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30,check=False)
    output=(completed.stdout+completed.stderr).strip()
    if completed.returncode or "xtb version 6.7.1pre" not in output.lower(): raise RuntimeError(f"Staged xTB did not execute correctly: {output}")
    manifest={"component":"xTB","version":"6.7.1pre","upstream_binary":UPSTREAM_URL,"corresponding_source":SOURCE_URL,"archive_sha256":actual,"executable_sha256":sha256(destination/"xtb.exe"),"libiomp5md_sha256":sha256(destination/"libiomp5md.dll"),"version_output":output,"files":[]}
    for path in sorted(p for p in destination.rglob("*") if p.is_file()): manifest["files"].append({"path":path.relative_to(destination).as_posix(),"bytes":path.stat().st_size,"sha256":sha256(path)})
    (destination/"xtb_runtime_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--binary-archive",type=Path,required=True); parser.add_argument("--source-archive",type=Path,required=True); parser.add_argument("--destination",type=Path,required=True)
    args=parser.parse_args(); print(json.dumps(stage(args.binary_archive.resolve(),args.source_archive.resolve(),args.destination.resolve()),indent=2))
