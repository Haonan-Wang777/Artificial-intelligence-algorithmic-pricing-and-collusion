"""Attempt the unmodified author-supplied Windows executable on a small input.

The executable is read from the provided archive or licensed vendor copy and
identified by SHA256. Intel runtime libraries may be needed.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package",default="data/source/provided_replication_package.zip")
    parser.add_argument("--output",default="results/original_smoke")
    parser.add_argument("--sessions",type=int,default=2)
    parser.add_argument("--cores",type=int,default=1)
    parser.add_argument("--runtime-path",default=None,help="Directory with installed Intel runtime DLLs")
    parser.add_argument("--timeout",type=int,default=120)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    output=root/args.output;output.mkdir(parents=True,exist_ok=True)
    if (root/args.package).exists():
        with zipfile.ZipFile(root/args.package) as archive:
            blob=archive.read("AER_fcode/baseline/baseline.exe")
            text=archive.read("AER_paper_Rscripts/table_I/A_InputParameters.txt").decode()
    else:
        vendor=root/"vendor/calvano_original"
        blob=(vendor/"AER_fcode/baseline/baseline.exe").read_bytes()
        text=(vendor/"AER_paper_Rscripts/table_I/A_InputParameters.txt").read_bytes().decode()
    text=text.replace("\r\r\n","\n").replace("\r\n","\n")
    rows=[line.strip() for line in text.splitlines() if line.strip()]
    rows[3]=str(args.cores)
    rows[5]=str(args.sessions)
    rows[9]="400"  # 400*25,000 = 10M periods, paper stability window unchanged
    rows[23]="1"  # impulse response
    rows[29]="1"  # equilibrium check
    rows[31]="1"  # Q gap
    rows[35]="0"  # avoid very large detailed output
    (output/"A_InputParameters.txt").write_text("\n".join(rows)+"\n",encoding="ascii")
    executable=output/"baseline.exe";executable.write_bytes(blob)
    record=dict(executable_sha256=hashlib.sha256(blob).hexdigest(),
                input_sha256=hashlib.sha256((output/"A_InputParameters.txt").read_bytes()).hexdigest(),
                sessions=args.sessions,cores=args.cores,platform=platform.platform(),modified_executable=False,
                runtime_path=args.runtime_path)
    if platform.system() != "Windows":
        record.update(status="unavailable",reason="Author binary targets Windows")
    else:
        ctypes.windll.kernel32.SetErrorMode(0x1|0x2|0x8000)
        start=time.perf_counter()
        try:
            environment=os.environ.copy()
            if args.runtime_path:
                environment["PATH"]=args.runtime_path+os.pathsep+environment.get("PATH", "")
                record["runtime_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(args.runtime_path).glob("libiomp5md.dll")}
            result=subprocess.run([str(executable)],cwd=output,capture_output=True,timeout=args.timeout,env=environment)
            (output/"stdout.log").write_bytes(result.stdout)
            (output/"stderr.log").write_bytes(result.stderr)
            record.update(status="success" if result.returncode==0 else "failed",returncode=result.returncode,
                          returncode_hex=f"0x{result.returncode & 0xffffffff:08x}")
        except (OSError,subprocess.TimeoutExpired) as error:
            record.update(status="failed",reason=str(error))
        record["elapsed_seconds"]=time.perf_counter()-start
    record["outputs_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file() and p.suffix in (".txt",".log")}
    (output/"execution.json").write_text(json.dumps(record,indent=2),encoding="utf-8")
    print(json.dumps(record,indent=2))
    if record["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
