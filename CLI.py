import subprocess, sys
from pathlib import Path

def run_chandra(input_path, out_dir, method="hf", page_range=None,
                include_images=True, include_headers_footers=False, max_tokens=None):
    cmd = ["chandra", str(input_path), str(out_dir)]
    if method:
        cmd += ["--method", method]
    if page_range:
        cmd += ["--page-range", page_range]
    if include_images is False:
        cmd.append("--no-images")
    if include_headers_footers:
        cmd.append("--include-headers-footers")
    if max_tokens:
        cmd += ["--max-output-tokens", str(max_tokens)]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    inp = Path("file.pdf") #input PATH
    out = Path("/Users/matvey/PycharmProjects/ocr_test/output") #output PATH
    out.mkdir(exist_ok=True, parents=True)
    run_chandra(inp, out, method="hf", page_range=None)