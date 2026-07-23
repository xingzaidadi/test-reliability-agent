#!/usr/bin/env python3
"""
MulticaWriteback — 结果回写节点
读取 multica_comment_payload.json,把测试结果 POST 回 Multica issue。

诚实设计(不伪造):
- 无平台凭证(MULTICA_API_URL/MULTICA_TOKEN 未配)→ dry-run:打印将发送的完整请求,不发。
- 有凭证 → 真实 POST,返回真实响应。
- 回写结果写入 multica_writeback_result.json,状态如实(sent/dry_run/failed)。

用法:
  python multica_writeback.py --issue ISSUE-001              # 无凭证→dry-run
  MULTICA_API_URL=... MULTICA_TOKEN=... python multica_writeback.py --issue ISSUE-001  # 真发
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def writeback(issue_id: str, run_dir: Path) -> dict:
    payload_path = run_dir / "multica_comment_payload.json"
    if not payload_path.exists():
        raise RuntimeError(f"回写内容不存在: {payload_path}(请先跑 report)")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    api_url = os.environ.get("MULTICA_API_URL", "").rstrip("/")
    token   = os.environ.get("MULTICA_TOKEN", "")

    # 组装真实请求(无论发不发,都构造出来,证明请求是完整的)
    endpoint = f"{api_url}/issues/{issue_id}/comments" if api_url else "<MULTICA_API_URL未配置>"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}" if token else "<MULTICA_TOKEN未配置>",
    }
    body = {
        "issue_id": payload.get("multica_issue_id"),
        "status":   payload.get("status"),
        "comment":  payload.get("comment"),
        "artifact_links": payload.get("artifact_links", []),
    }

    result = {
        "issue_id": issue_id,
        "attempted_at": datetime.now().isoformat(),
        "endpoint": endpoint,
        "request_body": body,
    }

    # 无凭证 → dry-run,诚实不发
    if not api_url or not token:
        result["status"] = "dry_run"
        result["reason"] = "MULTICA_API_URL / MULTICA_TOKEN 未配置,未发送真实请求(dry-run)"
        print("[multica-writeback] DRY-RUN(未配置平台凭证,不发送真实请求)")
        print(f"[multica-writeback]   将POST到: {endpoint}")
        print(f"[multica-writeback]   状态: {body['status']} | issue: {body['issue_id']}")
        print("[multica-writeback]   配置 MULTICA_API_URL + MULTICA_TOKEN 后可真实发送")
    else:
        # 有凭证 → 真发
        try:
            req = urllib.request.Request(
                endpoint, data=json.dumps(body).encode("utf-8"),
                headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                result["status"] = "sent"
                result["http_status"] = resp.status
                result["response"] = resp.read().decode("utf-8", errors="replace")[:500]
                print(f"[multica-writeback] 已发送,HTTP {resp.status}")
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"[multica-writeback] 发送失败: {e}")

    out_path = run_dir / "multica_writeback_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[multica-writeback] 回写结果: {out_path}")
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="multica_writeback")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--run-dir", default=None, dest="run_dir")
    args = ap.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else Path("outputs/runs") / args.issue
    result = writeback(args.issue, run_dir)
    # dry_run 和 sent 都算成功退出(dry_run不是错误,是诚实的未配置状态)
    sys.exit(0 if result["status"] in ("sent", "dry_run") else 1)
