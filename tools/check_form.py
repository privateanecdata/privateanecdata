#!/usr/bin/env python3
"""
Fail if the contribution form contains any control the schema does not enumerate, any free-text
control, or any control that could carry something other than a vocabulary id. Walks every screen
of the form against a running server (tools/check_origin.sh starts one) with a full set of answers,
so the screens that depend on earlier answers (effect details) are rendered too.

    python3 tools/check_form.py http://127.0.0.1:4399

Allowed: radio/checkbox controls named after schema fields (onset:<id> and dechallenge:<id> for
effect details), the routing fields (`at`, `go`, `s`), `no_effects`, and exactly one
text input — the visually hidden bot trap `website`, whose value is never stored.
"""
import base64
import json
import re
import sys
import urllib.parse
import urllib.request

FIELDS = {"compound", "route", "goal", "source_channel", "start_dose", "current_dose", "frequency",
          "duration", "purity_tested", "status", "stop_reason", "outcome", "adverse_effects",
          "age_band", "sex"}
CONTROL = {"at", "go", "s", "no_effects"}
HONEYPOT = "website"
CTRL = re.compile(r'<(input|select|textarea|button)\b([^>]*)>', re.I)
ATTR = re.compile(r'\s(name|type)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.I)

STATE = {"compound": "bpc-157", "route": "subcutaneous", "goal": "injury-healing", "source_channel": "overseas-vendor",
         "start_dose": "b1", "current_dose": "b1", "frequency": "daily", "duration": "1-3mo",
         "purity_tested": "no", "status": "stopped", "stop_reason": "cost",
         "outcome": "slight", "adverse_effects": ["headache", "injection-site"],
         "effect_detail": {"headache": {"onset": "first-2wk", "dechallenge": "resolved"}, "injection-site": {"onset": "first-days", "dechallenge": "resolved"}},
         "age_band": "35-44", "sex": "male"}


def post(origin, data):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(origin + "/contribute", data=body, headers={"Origin": origin, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode()


def controls(html):
    for m in CTRL.finditer(html):
        tag, attrs = m.group(1).lower(), m.group(2)
        a = {k.lower(): (v1 if v1 is not None else v2 if v2 is not None else v3) for k, v1, v2, v3 in ATTR.findall(attrs)}
        yield tag, a.get("name"), (a.get("type") or ("text" if tag == "textarea" else "")).lower()


def main():
    origin = sys.argv[1].rstrip("/")
    enc = base64.urlsafe_b64encode(json.dumps(STATE).encode()).decode().rstrip("=")
    # Render each screen by pressing Back from the screen after it, carrying the full state, so
    # every conditional control (effect details, stop reason) is on the page.
    nxt = {"1-compound": "2-usage", "2-usage": "3-course", "3-course": "4-outcome", "4-outcome": "5-effects",
           "5-effects": "6-about", "6-about": "review"}
    screens = {"start": [("at", "start")]}
    for at, after in nxt.items():
        screens[at] = [("at", after), ("go", "back"), ("s", enc)]
    screens["review"] = [("at", "6-about"), ("go", "next"), ("s", enc), ("age_band", "35-44"), ("sex", "male")]
    failures, seen_text = [], []
    for name, data in screens.items():
        html = post(origin, data)
        for tag, cname, ctype in controls(html):
            if tag == "button":
                if cname not in {"go", None}:
                    failures.append(f"{name}: button named {cname!r}")
                continue
            if tag == "textarea":
                failures.append(f"{name}: <textarea> present")
                continue
            if cname is None:
                failures.append(f"{name}: unnamed {tag}")
                continue
            base = cname.split(":")[0]
            if ctype in ("radio", "checkbox") or tag == "select":
                ok = (base in FIELDS | {"no_effects"} and ":" not in cname) or \
                     (":" in cname and base in {"onset", "dechallenge"})
                if not ok:
                    failures.append(f"{name}: {tag} {ctype} named {cname!r} is not a schema field")
            elif ctype == "hidden":
                if cname not in CONTROL:
                    failures.append(f"{name}: hidden field {cname!r} is not a routing field")
            elif ctype == "text":
                seen_text.append(cname)
                if cname != HONEYPOT:
                    failures.append(f"{name}: text input {cname!r} — the only text input allowed is the bot trap")
            else:
                failures.append(f"{name}: {tag} type={ctype!r} named {cname!r} is not an allowed control")
    if not seen_text:
        failures.append("bot trap text input not found on any screen")
    print(f"checked {len(screens)} screens: {len(failures)} problems")
    for f in failures:
        print("  FAIL", f)
    print("RESULT:", "FAILED" if failures else "every control is a schema field, a routing field, or the bot trap")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
