"""Operator CLI (PRD FR-7.1).

Scaffold commands: status (stage counts), demo (offline lead walk),
suppress/list. Network-bearing commands arrive with their FRs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

import re as _re_mod
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 - very old pythons
    pass

from . import builder_agent, markets
from .models import Lead, Stage
from .pipeline import demo_walk
from .store import Store


def cmd_status(args) -> int:
    s = Store(args.db)
    leads = s.list_leads()
    counts = s.stage_counts()
    print(f"leads: {len(leads)}")
    for stage, n in sorted(counts.items()):
        print(f"  {stage:<16} {n}")
    return 0


def cmd_demo(args) -> int:
    s = Store(args.db)
    lead = demo_walk(s)
    print(f"demo lead {lead.id} ({lead.domain}) score={lead.ugly_score}")
    print(f"final stage: {lead.stage.value}")
    print("wiring OK - real handlers pending PRD approval")
    return 0


def cmd_suppress(args) -> int:
    s = Store(args.db)
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    s.suppress(args.value, args.reason, ts)
    print(f"suppressed {args.value} ({args.reason})")
    return 0


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be 'south,west,north,east'")
    return tuple(parts)  # type: ignore[return-value]


def cmd_discover(args) -> int:
    from . import sources

    bbox = _parse_bbox(args.bbox)
    leads = sources.overpass_search(bbox, limit=args.limit)
    if not leads:
        print("no website-bearing businesses found in bbox (try wider area)")
        return 0
    print(f"{'domain':<40} {'name':<30} osm_ref")
    deduped: dict[str, object] = {}
    for ld in leads:
        if ld.domain in deduped:
            continue
        deduped[ld.domain] = ld
        print(f"{ld.domain:<40} {ld.name[:28]:<30} {ld.id}")
    if args.commit:
        s = Store(args.db)
        for ld in deduped.values():
            assert isinstance(ld, Lead)
            ld.market_profile = args.market
            s.upsert_lead(ld)
        s.log(
            "discover_run",
            {"market": args.market, "count": len(deduped), "bbox": args.bbox},
            ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        )
        print(f"committed {len(deduped)} leads to store")
    else:
        print("(dry run - pass --commit to store)")
    return 0


def cmd_score(args) -> int:
    from .measure import UGLY_PASS, score_many

    s = Store(args.db)
    targets = [ld for ld in s.list_leads() if ld.stage == Stage.DISCOVERED]
    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        print("nothing to score - run discover first")
        return 0
    results = score_many(targets)
    print(f"{'score':>5}  {'domain':<40} note")
    kept = 0
    for ld, sc, sig, err in results:
        if err:
            print(f"{'-':>5}  {ld.domain:<40} UNREACHABLE ({err[:48]})")
        elif sc >= UGLY_PASS:
            kept += 1
            flags = [f"{x['signal']}={x['value']}" for x in sig
                     if x.get("value") and x["signal"] != "weight_kb"]
            print(f"{sc:>5}  {ld.domain:<40} PASS {' '.join(flags[:3])}")
        else:
            print(f"{sc:>5}  {ld.domain:<40} below threshold")
        ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if err:
            s.log("score_error", {"error": err}, ld.id, ts=ts)
        else:
            ld.ugly_score = sc
            ld.signals = sig
            ld.stage = Stage.SCORED
            s.upsert_lead(ld)
            s.log("scored", {"score": sc}, ld.id, ts=ts)
    print(f"\n{kept}/{len(results)} pass ugly>={UGLY_PASS}")
    if not args.commit:
        print("(results committed - scoring is idempotent; use status to view)")
    return 0


def cmd_extract(args) -> int:
    import json as _json

    s = Store(args.db)
    lead = s.get_lead(args.lead_id)
    if lead is None:
        print(f"no such lead: {args.lead_id}")
        return 1
    data = _extract_facts(s, lead)
    print(_json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def _extract_facts(s: Store, lead) -> dict:
    import json as _json
    import re as _re

    from .llm import chat, parse_json_loose
    from .measure import fetch_homepage

    html = fetch_homepage(lead.domain)
    text = _re.sub(r"<(script|style).*?</\1>", " ", html, flags=_re.S | _re.I)
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()[:4000]
    if len(text) < 80:
        raise RuntimeError("page text too thin to extract")
    prompt = (
        "Extract business facts from this homepage text. Output ONE JSON "
        "object with exactly these keys: \"business_name\", \"tagline\", "
        "\"services\" (array), \"phone\", \"whatsapp\", \"address\", "
        "\"hours\", \"social_links\" (array), \"confidence_0_10\" (int). "
        "Use \"\" or [] for anything not present. Never invent values.\n\n"
        "HOMEPAGE TEXT:\n" + text
    )
    system = (
        "You are a strict JSON extraction API. Reply with a single JSON "
        "object and nothing else - no prose, no markdown, no explanations."
    )
    raw, model = chat(prompt, system=system, max_tokens=2500, json_mode=True)
    data = parse_json_loose(raw)
    data["_model"] = model
    s.log(
        "extracted",
        {"model": model, "data": {k: v for k, v in data.items()
                                  if k != "_model"}},
        lead.id,
        ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
    return data


def cmd_audit(args) -> int:
    from . import audit as psi_mod
    from .measure import score as rescore

    s = Store(args.db)
    lead = s.get_lead(args.lead_id)
    if lead is None:
        print(f"no such lead: {args.lead_id}")
        return 1
    mobile, desktop = psi_mod.audit_domain(lead.domain)
    print(f"PSI audit: {lead.domain}")
    print(f"  mobile : {mobile}")
    print(f"  desktop: {desktop}")
    if args.commit:
        sigs = [x for x in lead.signals if x.get("signal") != "psi_mobile_perf"]
        perf = mobile.get("performance")
        if isinstance(perf, int):
            sigs.append({"signal": "psi_mobile_perf", "value": perf})
        lead.signals = sigs
        lead.ugly_score = rescore(sigs)
        lead.stage = Stage.AUDITED
        s.upsert_lead(lead)
        s.log(
            "audited",
            {"mobile": mobile, "desktop": desktop,
             "ugly_score": lead.ugly_score},
            lead.id,
            ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        )
        print(f"  committed - stage=AUDITED ugly_score={lead.ugly_score}")
    return 0


def cmd_sweep(args) -> int:
    from . import sources

    cities = (
        [c.strip() for c in args.cities.split(",")]
        if args.cities
        else sorted(markets.CITY_BOXES_IN)
    )
    unknown = [c for c in cities if c not in markets.CITY_BOXES_IN]
    if unknown:
        print(f"unknown cities: {', '.join(unknown)}")
        return 1
    s = Store(args.db)
    total_new = 0
    seen_global: set[str] = set()
    known = _known_domains(s)
    print(f"sweeping {len(cities)} cities, <= {args.limit_per_city} leads each...")
    for i, city in enumerate(cities):
        if i:
            time.sleep(3)
        bbox = markets.CITY_BOXES_IN[city]
        try:
            leads = sources.overpass_search(
                bbox, limit=args.limit_per_city, verticals=not args.all
            )
            mode = "vertical"
        except Exception as ex:  # noqa: BLE001 - degrade to plain query
            if args.all:
                print(f"  {city:<12} FAILED ({str(ex)[:60]})")
                continue
            try:
                leads = sources.overpass_search(
                    bbox, limit=args.limit_per_city, verticals=False
                )
                mode = "fallback-all"
            except Exception as ex2:  # noqa: BLE001 - per-city isolation
                print(f"  {city:<12} FAILED ({str(ex2)[:60]})")
                continue
        fresh = [
            ld
            for ld in leads
            if ld.domain not in seen_global
            and ld.domain not in known
        ]
        for ld in fresh:
            seen_global.add(ld.domain)
        for ld in fresh[: args.limit_per_city]:
            ld.market_profile = args.market
            s.upsert_lead(ld)
            total_new += 1
        print(
            f"  {city:<12} +{len(fresh[:args.limit_per_city])} "
            f"(found {len(leads)}, {mode})"
        )
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    s.log("sweep", {"cities": cities, "new": total_new}, ts=ts)
    print(f"\nsweep complete: +{total_new} new leads")
    return 0


def _known_domains(store: Store) -> set[str]:
    return {ld.domain for ld in store.list_leads()}


def cmd_enrich(args) -> int:
    from .measure import is_excludable, score as rescore
    from .wayback import enrich_signal

    s = Store(args.db)
    targets = [
        ld
        for ld in s.list_leads()
        if ld.stage in (Stage.DISCOVERED, Stage.SCORED)
        and not is_excludable(ld)
        and not any(x.get("signal", "").startswith("wayback") for x in ld.signals)
    ][: args.limit]
    if not targets:
        print("nothing to enrich (all leads have wayback signals)")
        return 0
    print(f"enriching {len(targets)} leads via Wayback CDX...")
    enriched = 0
    for i, ld in enumerate(targets):
        if i:
            time.sleep(1.2)
        sig = enrich_signal(ld.domain)
        ld.signals = ld.signals + [sig]
        old_score = ld.ugly_score
        if sig["signal"] != "wayback_error":
            new_score = rescore(ld.signals)
            ld.ugly_score = max(old_score, new_score) if args.keep_best else new_score
        enriched += 1
        print(
            f"  {ld.domain:<38} {sig['signal']:<20} "
            f"score {old_score}->{ld.ugly_score}"
        )
        if args.commit:
            s.upsert_lead(ld)
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    s.log("enriched", {"count": enriched}, ts=ts)
    print(f"\nenriched {enriched} leads")
    return 0


def cmd_rebuild(args) -> int:
    import json as _json
    import re as _re
    from pathlib import Path

    from .build import compose, harvest_images
    from . import deploy

    s = Store(args.db)
    lead = s.get_lead(args.lead_id)
    if lead is None:
        print(f"no such lead: {args.lead_id}")
        return 1
    is_no_site = lead.domain.startswith("no-site-")
    ev = s.last_event_detail(lead.id, "extracted") or {}
    ext = dict(ev.get("data") or {})
    if not ext.get("business_name"):
        if is_no_site:
            print("CREATE-class: synthesizing Facts from OSM listing...")
            from . import sources as _src

            tags = (_src.overpass_lookup(_osm_ref(lead)) or {}).get("tags") \
                or {}
            addr = ", ".join(
                t for t in (
                    tags.get("addr:housenumber", ""),
                    tags.get("addr:street", ""),
                    tags.get("addr:suburb", ""),
                    tags.get("addr:city", ""),
                ) if t
            )
            ext = {
                "business_name": lead.name,
                "tagline": "",
                "services": [
                    v.replace("_", " ").title()
                    for k, v in tags.items()
                    if k in ("cuisine", "shop", "office") and v
                ],
                "phone": tags.get("phone")
                or tags.get("contact:phone", ""),
                "whatsapp": tags.get("contact:whatsapp", ""),
                "address": addr,
                "hours": tags.get("opening_hours", ""),
                "_vertical_tags": " ".join(
                    f"{k}={v}" for k, v in tags.items()
                    if k in ("amenity", "tourism", "shop", "office", "cuisine")
                ) + " " + lead.name,
            }
            s.log("extracted", {"model": "osm-tags", "data": {
                k: v for k, v in ext.items() if not k.startswith("_")}},
                lead.id,
                ts=dt.datetime.now(dt.timezone.utc).isoformat(
                    timespec="seconds"))
        else:
            print("no stored extraction - extracting now...")
            ext = _extract_facts(s, lead)
    audit_ev = s.last_event_detail(lead.id, "audited") or {}
    mobile = (audit_ev.get("mobile") or {})
    stats = {
        "perf": mobile.get("performance", "?"),
        "lcp": mobile.get("lcp_s", "?"),
        "date": dt.date.today().isoformat(),
    }
    biz = str(ext.get("business_name") or lead.name)
    orig = f"https://{lead.domain}/"
    ext.setdefault("_market", lead.market_profile)
    try:
        from . import research as _research

        city_hint = str(ext.get("address") or "")[:40]
        ext["_field_research"] = _research.research_lead(
            biz,
            _research.detect_vertical_key(ext),
            markets.MARKETS.get(lead.market_profile, {}).get("label", ""),
            city_hint,
        )
        print(f"field research compiled: "
              f"{len(ext['_field_research'])} chars")
    except Exception as ex:  # noqa: BLE001 - research optional
        print(f"(field research skipped: {str(ex)[:60]})")
    try:
        from .copywriter import write_copy
        from .research import detect_vertical_key

        vkey = detect_vertical_key(ext)
        copy_data = write_copy(biz, ext, vkey, lead.market_profile)
        if copy_data and copy_data.get("headlines"):
            ext["_proposed_copy"] = json.dumps(copy_data, ensure_ascii=False)
            print(f"copy engine: {len(copy_data.get('headlines', []))} "
                  f"headlines by {copy_data.get('_model', 'llm')}")
    except Exception as ex:  # noqa: BLE001 - copy optional
        print(f"(copy engine skipped: {str(ex)[:60]})")
    slug = _re.sub(r"[^a-z0-9]+", "-", biz.lower()).strip("-")[:20] or "site"
    worker = f"facelift-{slug}-{lead.id.rsplit('-', 1)[-1][:8]}"
    dist = Path("builds") / worker / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    images: list[str] = []
    snapshot = Path("data") / "snapshots" / lead.domain / "index.html"
    if is_no_site:
        try:
            from . import imagery

            detected = " ".join(str(x) for x in
                                (ext.get("services") or [])) + " " + lead.name
            scenes = imagery.scenes_for_vertical("", detected)
            gen_files = []
            for i, scene in enumerate(scenes[:2], 1):
                png = imagery.generate(scene)
                if png:
                    rel = f"img/gen-hero.{i}.png" if i == 1 else \
                        f"img/gen-{i}.png"
                    (dist / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dist / rel).write_bytes(png)
                    gen_files.append(rel)
            if gen_files:
                print(f"concept imagery generated: {len(gen_files)}")
                images = gen_files
        except Exception as ex:  # noqa: BLE001 - imagery optional
            print(f"(imagery skipped: {str(ex)[:60]})")
    if not images and snapshot.exists():
        try:
            from .build import extract_data_uris

            snap_text = snapshot.read_text(encoding="utf-8", errors="ignore")
            images = extract_data_uris(snap_text, dist)
            print(f"snapshot photos extracted: {len(images)}")
        except Exception as ex:  # noqa: BLE001 - snapshots optional
            print(f"(snapshot parse skipped: {str(ex)[:70]})")
    if not images:
        try:
            from .measure import fetch_homepage

            page_html = fetch_homepage(lead.domain)
        except Exception:  # noqa: BLE001 - images are optional garnish
            page_html = ""
        images = harvest_images(page_html, orig)
    images = _localize_images(images, dist)

    from . import compete

    comp_rows: list[dict] = []
    try:
        print("scanning neighborhood rivals...")
        comp_rows = compete.list_rivals(
            _osm_ref(lead), max_rivals=2,
            exclude_domain=None if is_no_site else lead.domain,
        )
        for r in comp_rows:
            print(f"  rival: {r['name']} ({r['domain']})")
    except Exception as ex:  # noqa: BLE001 - optional intelligence
        print(f"(competitor scan skipped: {str(ex)[:60]})")

    use_agent = bool(
        getattr(args, "agent", False)
        or (
            not getattr(args, "no_agent", False)
            and builder_agent.opencode_cmd() is not None
        )
    )
    vprof_key = None
    try:
        from . import research as _res

        vprof_key = _res.detect_vertical_key(ext)
    except Exception:  # noqa: BLE001
        pass
    dna = __import__("facelift.design_dna",
                     fromlist=["choose"]).choose(lead.id, vprof_key or "")
    n_gen = sum(1 for i in images if "gen-" in i)
    print("\n" + "=" * 62)
    print(" MISSION BRIEFING")
    print(f"   target   : {biz} ({lead.domain}) "
          f"{'[CREATE]' if is_no_site else '[FIX]'} score={lead.ugly_score}")
    print(f"   dna      : {dna['name']} (anti-repeat memory active)")
    print(f"   playbook : {vprof_key or 'default'} | craft tier: C2+")
    print(f"   research : {len(ext.get('_field_research', ''))} chars field "
          f"notes | rivals: {len(comp_rows)} | images: "
          f"{len(images)} ({n_gen} generated)")
    print("=" * 62 + "\n")
    html_out = None
    built_by = "template"
    if use_agent:
        snap_html = snapshot if snapshot.exists() else None
        snap_css = snapshot.parent / "styles.css"
        snap_css = snap_css if snap_css.exists() else None
        try:
            builder_agent.build_brief(
                dist.parent, biz, ext,
                mobile, orig, snap_html, snap_css,
                [str((dist / rel).resolve()) for rel in images],
                rivals=comp_rows,
                market_profile=lead.market_profile,
                is_no_site=is_no_site,
                date=stats["date"],
            )
            print("invoking opencode build agent (this can take minutes)...")
            ok, tail = builder_agent.run_agent(dist.parent)
            if ok and builder_agent.verify(dist):
                built_by = "opencode-agent"
                print("agent build: SUCCESS")
                fails = builder_agent.quality_check(dist)
                if fails:
                    print(f"quality gate: {len(fails)} issue(s) -> "
                          f"one revision pass")
                    builder_agent.revision_brief(dist.parent, fails)
                    ok2, _t2 = builder_agent.run_agent(dist.parent,
                                                       timeout_s=600)
                    fails2 = builder_agent.quality_check(dist)
                    if fails2:
                        print("post-revision gate still flags:")
                        for f in fails2:
                            print(f"  - {f}")
                    else:
                        print("revision pass: quality gate PASSED")
            else:
                print(f"agent build failed ({tail[:120]}) - template fallback")
        except Exception as ex:  # noqa: BLE001 - fallback keeps pipeline alive
            print(f"agent build error ({str(ex)[:90]}) - template fallback")
    if built_by == "template":
        html_out = compose(biz, ext, stats, orig, market=lead.market_profile,
                           images=images)
        (dist / "index.html").write_text(html_out, encoding="utf-8")

    url = deploy.deploy_dir(dist, worker)
    print(f"deployed: {url}")
    try:
        from .beforeafter import screenshot as take_shot

        # Aesthetic critic loop: look at the page, not just the code.
        for round_no in (1, 2):
            shot = dist / "critique.png"
            if not take_shot(url, shot, width=1280, height=1100):
                print("(critic skipped - screenshot failed)")
                break
            notes = builder_agent.design_critique(
                shot.read_bytes())
            if not notes:
                print("(critic unavailable)")
                break
            if notes == ["APPROVED"]:
                print(f"aesthetic critic: APPROVED (round {round_no})")
                break
            print(f"aesthetic critic round {round_no}: "
                  f"{len(notes)} visual defects")
            for n in notes:
                print(f"  - {n[:90]}")
            (dist.parent / "DESIGN-NOTES.md").write_text(
                "# DESIGN REVISION\n\nA senior art director reviewed the "
                "rendered page screenshot and flagged:\n"
                + "\n".join(f"- {n}" for n in notes)
                + "\n\nFix these VISUAL issues in dist/index.html "
                "(layout/spacing/hierarchy/color/type/depth/polish). Keep "
                "all content, links and structure intact. Then print "
                "`BUILD COMPLETE`.",
                encoding="utf-8",
            )
            print("invoking revision agent...")
            builder_agent.run_agent(dist.parent, timeout_s=600)
            deploy.deploy_dir(dist, worker)
    except Exception as ex:  # noqa: BLE001 - critic optional
        print(f"(aesthetic critic skipped: {str(ex)[:90]})")

    try:
        from . import compete
        from .beforeafter import build_report

        import html as _h

        you_perf = mobile.get("performance", "?")
        you_lcp = mobile.get("lcp_s", "?")
        comp_html = ""
        if comp_rows:
            comp_html = compete.render_table([], you_perf, you_lcp)
            try:
                you_url = f"https://{lead.domain}/"
                matrix = compete.render_matrix(
                    you_url if lead.domain
                    and not lead.domain.startswith("no-site-") else None,
                    [{"name": d.split(".")[0].title(),
                      "domain": d} for d in
                     [r["domain"] for r in comp_rows]],
                )
                intent = "<div class='card' style='margin-top:12px'><p>" \
                         + "</p><p>".join(
                             _h.escape(x) for x in compete.INTENT_LINES
                           ) + "</p></div>"
                comp_html = matrix + intent + comp_html
            except Exception as ex:  # noqa: BLE001 - matrix optional
                print(f"(spec matrix skipped: {str(ex)[:60]})")
        pair = build_report(
            biz, lead.domain, url, dist, mobile,
            market=lead.market_profile, date=stats.get("date", ""),
            competitors_html=comp_html,
        )
        if pair:
            deploy.deploy_dir(dist, worker)
            print(f"before/after: {url}/before-after.html")
    except Exception as ex:  # noqa: BLE001 - artifact is optional
        print(f"(pair page skipped: {str(ex)[:90]})")
    s.log(
        "rebuilt",
        {"url": url, "worker": worker, "business": biz},
        lead.id,
        ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )
    if args.commit:
        lead.stage = Stage.REBUILT
        s.upsert_lead(lead)
        print(f"stage -> REBUILT")
    return 0


def cmd_contacts(args) -> int:
    from .contacts import waterfall

    s = Store(args.db)
    lead = s.get_lead(args.lead_id)
    if lead is None:
        print(f"no such lead: {args.lead_id}")
        return 1
    print(f"waterfall: {lead.domain}")
    cands = waterfall(lead.domain)
    if not cands:
        print("  nothing found - manual research needed")
        return 1
    best_email = None
    for kind, val, src, conf, ver in cands:
        flag = "VERIFIED" if ver else ("unverified-form-only" if kind == "form_target" else "unverified")
        print(f"  [{conf:>2}] {kind:<12} {val:<40} {src} ({flag})")
        if args.commit:
            s.add_contact(lead.id, kind, val, src, conf, ver)
        if kind == "email" and ver and best_email is None:
            best_email = val
    print(
        f"\nbest email: {best_email or 'NONE - form channel only'}"
        f"{'' if not args.commit else ' (saved)'}"
    )
    return 0


def cmd_draft(args) -> int:
    import json as _json

    from .outreach import NotReady, draft as mk_draft

    s = Store(args.db)
    try:
        msg = mk_draft(s, args.lead_id)
    except NotReady as ex:
        print(f"GATE: {ex}")
        return 1
    print(f"to     : {msg['to']}")
    print(f"subject: {msg['subject']}")
    print(f"hash   : {msg['body_hash']}  <- approve with this exact hash")
    print("\n--- body ---")
    print(msg["body"])
    print("------------")
    return 0


def cmd_send(args) -> int:
    from .outreach import NotReady, send as do_send

    s = Store(args.db)
    try:
        to = do_send(s, args.lead_id, args.approve)
    except NotReady as ex:
        print(f"GATE: {ex}")
        return 1
    print(f"sent to {to}")
    return 0


def _triage_prospects(cands: list) -> tuple[list, list]:
    """Speculative programmatic triage: deterministic veto (0 tokens) +
    single batched LLM call for all ambiguous leads. Falls back to
    per-lead calls only if batch fails."""
    try:
        from .speculative import batched_triage

        results = batched_triage(cands)
        prospects, rejected = [], []
        for ld, res in zip(cands, results):
            if res and res.get("prospect") is True:
                prospects.append(ld)
            else:
                reason = (res.get("reason") if res else "") or "rejected"
                rejected.append((ld, str(reason)[:80]))
        return prospects, rejected
    except Exception:
        pass
    # fallback: deterministic veto + per-lead LLM (original path)
    from .llm import chat
    from .llm import parse_json_loose

    import re as _re

    RULE_VETO = _re_mod.compile(
        r"bank|embassy|commission|authority|ministr|secretariat|bhavan"
        r"|bhawan|sadan|nigam|parishad|corporate park|tech park|state "
        r"board|branch \d+|zonal|welfare|housing board|develop.* authority"
        r"|pvt|ltd|inc\b|corporation",
        _re_mod.I,
    )

    prospects, rejected = [], []
    for ld in cands:
        name_l = ld.name.lower()
        if RULE_VETO.search(name_l):
            rejected.append((ld, "rule veto: institutional/corporate name"))
            continue
        prompt = (
            'A business named "' + ld.name + '" in India has NO website. '
            "Is this a SMALL LOCAL BUSINESS (family restaurant, cafe, "
            "boutique hostel/guesthouse, dental clinic, salon, coaching "
            "center, local shop, tradesperson) that would plausibly pay "
            "about ₹8,000 for its first simple website? "
            "STRICTLY REJECT: banks & financial institutions, political "
            "party offices, government estate/works offices, tech parks, "
            "corporate office complexes, multinationals, landmarks, "
            "cemetery/places, universities. "
            "Reply ONLY JSON: "
            '{"prospect": true/false, "reason": "<=14 words"}'
        )
        data = None
        last_err = ""
        for suffix in ("", "\nCRITICAL: your entire reply must be exactly "
                            "one JSON object, nothing else."):
            try:
                raw, model = chat(prompt + suffix, max_tokens=150,
                                  json_mode=True)
                data = parse_json_loose(raw)
                break
            except Exception as ex:  # noqa: BLE001 - retry w/ stricter ask
                last_err = str(ex)[:80]
        if data is None:
            up = (raw or "").upper()
            if "REJECT" in up or "NOT" in up.split("{")[0]:
                rejected.append((ld, "model verdict: reject"))
            else:
                rejected.append((ld, f"triage error: {last_err}"))
            continue
        if data.get("prospect") is True:
            prospects.append(ld)
        else:
            reason = str(data.get("reason", ""))[:80]
            rejected.append((ld, reason or model))
    return prospects, rejected


def cmd_discover_nosite(args) -> int:
    from . import sources

    bbox = _parse_bbox(args.bbox)
    leads = sources.overpass_no_site_search(bbox, limit=args.limit)
    if not leads:
        print("no no-site businesses found in bbox")
        return 0
    known = _known_domains(Store(args.db))
    fresh = [ld for ld in leads if ld.domain not in known]
    print(f"{'name':<34} {'osm':<24}")
    for ld in fresh:
        print(f"{ld.name[:32]:<34} {ld.id:<24}")
    if args.commit and fresh:
        print("triaging candidates (LLM small-business gate)...")
        prospects, rejected = _triage_prospects(fresh)
        for ld, why in rejected:
            print(f"  ✗ {ld.name[:32]:<34} rejected: {why}")
    else:
        prospects = fresh
    s = Store(args.db)
    for ld in prospects:
        ld.market_profile = args.market
        s.upsert_lead(ld)
        ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        s.log("discover_nosite", {"name": ld.name}, ld.id, ts=ts)
    for ld in prospects:
        print(f"  [OK]   {ld.name[:32]:<34} accepted")
    print(f"\ncommitted {len(prospects)} CREATE-class leads "
          f"(rejected {len(fresh) - len(prospects)})")
    return 0


def _localize_images(images: list[str], dist: Path) -> list[str]:
    """Download hotlinked photos into dist so sites never rot from link
    decay (PRD FR-9 self-maintenance). Snapshot-extracted images are
    already local and pass through untouched."""
    import urllib.request

    from .sources import USER_AGENT

    out: list[str] = []
    n = 0
    for u in images:
        if not u.startswith("http"):
            out.append(u)
            continue
        ext = u.rsplit(".", 1)[-1].lower()[:4]
        ext = ext if ext in ("jpg", "jpeg", "png", "webp", "avif") else "jpg"
        n += 1
        rel = f"img/dl-{n}.{ext}"
        try:
            req = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read(8_000_000)
            if len(data) < 5000:
                raise RuntimeError("too small")
            (dist / rel).parent.mkdir(parents=True, exist_ok=True)
            (dist / rel).write_bytes(data)
            out.append(rel)
        except Exception:  # noqa: BLE001 - dead image = drop it silently
            continue
    return out


def _osm_ref(lead) -> str:
    if lead.source.startswith("osm") and "/" in lead.source_url:
        return "/".join(lead.source_url.split("/")[-2:])
    if lead.id.startswith("osm-"):
        parts = lead.id.split("-")
        return f"{parts[1]}-{parts[2]}"
    return ""


def cmd_watch(args) -> int:
    """FR-9: liveness + drift watchdog over every deployed site."""
    s = Store(args.db)
    targets = []
    for ld in s.list_leads():
        ev = s.last_event_detail(ld.id, "rebuilt")
        if ev and ev.get("url"):
            targets.append((ld, ev["url"]))
    if not targets:
        print("nothing deployed to watch yet")
        return 0
    import urllib.request

    print(f"watching {len(targets)} deployed sites:")
    for ld, url in targets:
        t0 = time.monotonic()
        status = "?"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "facelift-watch/0.1"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                status = str(resp.status)
        except urllib.error.HTTPError as ex:
            status = f"HTTP {ex.code}"
        except Exception as ex:  # noqa: BLE001 - surfaced per row
            status = f"ERR {str(ex)[:30]}"
        ms = int((time.monotonic() - t0) * 1000)
        healthy = status == "200"
        print(f"  {'OK ' if healthy else 'BAD'} {url} ({status}, {ms}ms)")
        s.log(
            "watch_check",
            {"status": status, "ms": ms, "healthy": healthy},
            ld.id,
            ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        )
    print("\nnext: monthly cron re-runs this + audit -> care reports (FR-6.5)")
    return 0


def cmd_replies(args) -> int:
    from .outreach import NotReady, poll_replies

    s = Store(args.db)
    try:
        rs = poll_replies(s, limit=args.limit)
    except NotReady as ex:
        print(f"REPLIES: {ex}")
        return 1
    hot = [r for r in rs if r["kind"] == "hot"]
    for r in rs:
        if r["kind"] != "other":
            print(f"  {r['kind']:<8} {r['from'][:36]:<38} {r['subject'][:44]}")
    print(f"\nscanned {len(rs)} recent messages | hot: {len(hot)}")
    return 0


def cmd_agents(args) -> int:
    from .agents import Pool, Role

    role = Role(args.role)
    lead_ids = [x.strip() for x in args.leads.split(",") if x.strip()]
    print(f"spawning {len(lead_ids)} x {role.value} agents "
          f"with {args.workers} workers (shared WAL store)...")
    pool = Pool(max_workers=args.workers)
    tasks = pool.spawn(role, lead_ids)
    for t in tasks:
        icon = "✅" if t.status == "done" else "❌"
        print(f"  {icon} {t.lead_id} [{t.role.value}] "
              f"{t.status} {t.elapsed}s {str(t.result)[:80]}")
    ok = sum(1 for t in tasks if t.status == "done")
    print(f"\n{ok}/{len(tasks)} agents completed")
    return 0 if ok == len(tasks) else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="facelift")
    p.add_argument("--db", default=None)
    sub = p.add_subparsers(required=True)

    st = sub.add_parser("status", help="lead counts by stage")
    st.set_defaults(fn=cmd_status)

    dm = sub.add_parser("demo", help="offline pipeline wiring check")
    dm.set_defaults(fn=cmd_demo)

    sp = sub.add_parser("suppress", help="add permanent suppression")
    sp.add_argument("value")
    sp.add_argument("--reason", default="manual")
    sp.set_defaults(fn=cmd_suppress)

    dv = sub.add_parser("discover", help="FR-1: find businesses w/ websites in bbox (south,west,north,east)")
    dv.add_argument("--market", default="in", choices=sorted(markets.MARKETS))
    dv.add_argument("--bbox", required=True)
    dv.add_argument("--limit", type=int, default=25)
    dv.add_argument("--commit", action="store_true")
    dv.set_defaults(fn=cmd_discover)

    sc = sub.add_parser("score", help="FR-1.2: staleness-score DISCOVERED leads")
    sc.add_argument("--limit", type=int, default=0)
    sc.add_argument("--commit", action="store_true")
    sc.set_defaults(fn=cmd_score)

    ex = sub.add_parser("extract", help="FR-2.3: LLM-extract business facts from a lead's homepage")
    ex.add_argument("lead_id")
    ex.set_defaults(fn=cmd_extract)

    au = sub.add_parser("audit", help="FR-2.1: PageSpeed audit a lead (mobile+desktop)")
    au.add_argument("lead_id")
    au.add_argument("--commit", action="store_true")
    au.set_defaults(fn=cmd_audit)

    sw = sub.add_parser("sweep", help="FR-1: multi-city lead sweep (India boxes)")
    sw.add_argument("--market", default="in", choices=sorted(markets.MARKETS))
    sw.add_argument("--cities", default="", help="comma list; default = all")
    sw.add_argument("--limit-per-city", type=int, default=8)
    sw.add_argument("--all", action="store_true", help="skip vertical narrowing")
    sw.set_defaults(fn=cmd_sweep)

    en = sub.add_parser("enrich", help="FR-1.2: Wayback CDX staleness signals")
    en.add_argument("--limit", type=int, default=10)
    en.add_argument("--commit", action="store_true")
    en.add_argument("--keep-best", action="store_true")
    en.set_defaults(fn=cmd_enrich)

    rb = sub.add_parser("rebuild", help="FR-3: compose + deploy a live concept preview")
    rb.add_argument("lead_id")
    rb.add_argument("--commit", action="store_true")
    rb.add_argument("--agent", action="store_true",
                    help="force opencode agent build (default: auto)")
    rb.add_argument("--no-agent", action="store_true",
                    help="force template composer, skip agent")
    rb.set_defaults(fn=cmd_rebuild)

    dn = sub.add_parser("discover-nosite", help="FR-1: find businesses with NO website (CREATE class)")
    dn.add_argument("--market", default="in", choices=sorted(markets.MARKETS))
    dn.add_argument("--bbox", required=True)
    dn.add_argument("--limit", type=int, default=25)
    dn.add_argument("--commit", action="store_true")
    dn.set_defaults(fn=cmd_discover_nosite)

    wt = sub.add_parser("watch", help="FR-9: liveness check on all deployed sites")
    wt.set_defaults(fn=cmd_watch)

    rp = sub.add_parser("replies", help="FR-5.5: IMAP reply watcher")
    rp.add_argument("--limit", type=int, default=25)
    rp.set_defaults(fn=cmd_replies)

    ct = sub.add_parser("contacts", help="FR-4: contact waterfall for a lead")
    ct.add_argument("lead_id")
    ct.add_argument("--commit", action="store_true")
    ct.set_defaults(fn=cmd_contacts)

    dr = sub.add_parser("draft", help="FR-5: render gated outreach draft")
    dr.add_argument("lead_id")
    dr.set_defaults(fn=cmd_draft)

    sd = sub.add_parser("send", help="FR-5: send draft (requires approval hash)")
    sd.add_argument("lead_id")
    sd.add_argument("--approve", required=True)
    sd.set_defaults(fn=cmd_send)

    ag = sub.add_parser("agents", help="multi-agent: spawn parallel workers with synced store")
    ag.add_argument("--role", choices=["researcher", "builder", "reviewer", "hunter"], default="builder")
    ag.add_argument("--leads", required=True, help="comma-separated lead_ids")
    ag.add_argument("--workers", type=int, default=3)
    ag.set_defaults(fn=cmd_agents)

    vz = sub.add_parser("viz", help="live side-workspace: see researching, where, each turn (read-only)")
    vz.add_argument("--port", type=int, default=8765)
    vz.add_argument("--open", action="store_true", help="open browser")
    def _wrap_viz(a):  # lazy import
        from .viz import cmd_viz
        return cmd_viz(a)
    vz.set_defaults(fn=_wrap_viz)

    ch = sub.add_parser("chat", help="immersive qwen.chat-style UI — center chat + right artifacts + tool waterfall")
    ch.add_argument("--port", type=int, default=8766)
    ch.add_argument("--open", action="store_true", help="open browser")
    def _wrap_chat(a):
        from .chat import cmd_chat
        return cmd_chat(a)
    ch.set_defaults(fn=_wrap_chat)

    wk = sub.add_parser("work", help="how I work on any task — TodoWrite + tool stream + diff (most immersive, like agent trace)")
    wk.add_argument("--port", type=int, default=8767)
    wk.add_argument("--open", action="store_true", help="open browser")
    def _wrap_work(a):
        from .workview import cmd_work
        return cmd_work(a)
    wk.set_defaults(fn=_wrap_work)

    args = p.parse_args(argv)
    if getattr(args, "db", None) is None:
        args.db = None
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
