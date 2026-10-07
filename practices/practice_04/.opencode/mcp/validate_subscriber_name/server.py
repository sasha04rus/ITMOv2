#!/usr/bin/env python3
#!/usr/bin/env python3
import sys
import json
import os

# Minimal MCP-compatible stdio server for opencode 1.18.x
# JSON per line framing (no Content-Length), per user spec.

def read_message():
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except Exception:
        return None

def write_message(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def validate_name(name: str):
    if name is None:
        return {"ok": False, "error": "name is required"}
    trimmed = name.strip()
    if trimmed == "":
        return {"ok": False, "error": "empty name is not allowed"}
    return {"ok": True, "name": trimmed}

def main():
    # Log first few messages for debugging compatibility
    try:
        evdir = os.path.join(os.path.dirname(__file__), "../../evidence")
        evdir = os.path.abspath(evdir)
        os.makedirs(evdir, exist_ok=True)
        log_path = os.path.join(evdir, "mcp_server_incoming.log")
    except Exception:
        log_path = None
    while True:
        msg = read_message()
        if msg is None:
            break
        try:
            if log_path:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except Exception:
            pass
        mid = msg.get("id")
        method = msg.get("method")
        params = (msg.get("params") or {})
        if method == "initialize":
            proto = params.get("protocolVersion") or "1.0"
            write_message({
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "protocolVersion": proto,
                    "serverInfo": {"name": "validate-subscriber-name", "version": "1.0.0"},
                    "capabilities": {"tools": {}}
                }
            })
            continue
        if method in ("tools/list", "tool/list"):
            write_message({
                "jsonrpc": "2.0",
                "id": mid,
                "result": {
                    "tools": [
                        {
                            "name": "validate_subscriber_name",
                            "description": "Validate and normalize subscriber name: trims spaces; rejects empty.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"name": {"type": ["string"]}},
                                "required": ["name"]
                            }
                        }
                    ]
                }
            })
            continue
        if method in ("tools/call", "tool/execute"):
            tool = params.get("name")
            args = params.get("arguments") or params.get("args") or {}
            if tool == "validate_subscriber_name":
                name = args.get("name")
                if not isinstance(name, str) and name is not None:
                    # Coerce non-string to string only for truthy informative error
                    res = {"ok": False, "error": "name must be a string"}
                else:
                    res = validate_name(name)
                # Wrap in MCP tool result with content/isError
                is_error = not res.get("ok", False)
                content_text = json.dumps(res, ensure_ascii=False)
                write_message({
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "content": [{"type": "text", "text": content_text}],
                        "isError": is_error
                    }
                })
            else:
                write_message({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown tool"}})
            continue
        write_message({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown method"}})

if __name__ == "__main__":
    main()
