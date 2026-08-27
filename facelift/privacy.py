"""Privacy policy page generator (SECURITY-AUDIT F4/F12, README OQ-5).

Deployed once to its own worker; URL becomes FACELIFT_PRIVACY_URL and is
linked from every outbound footer. Content matches what the pipeline
actually does: business-contact data only, sourced from the business's own
public listings, permanent opt-out honored, deletion on request.
"""

from __future__ import annotations

from pathlib import Path

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Notice - Facelift</title>
<style>
body{{font-family:system-ui,sans-serif;background:#fafaf8;color:#14161a;line-height:1.65;margin:0}}
main{{max-width:760px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:30px}}h2{{font-size:19px;margin-top:30px}}
.card{{background:#fff;border:1px solid #e7e7e2;border-radius:14px;padding:20px 22px;margin-top:14px}}
a{{color:#0e9f6e}}
.small{{color:#5c6470;font-size:13px}}
</style>
</head>
<body><main>
<h1>Privacy Notice</h1>
<p class="small">Last updated {date} &middot; Facelift (owner-operated web services)</p>

<div class="card">
<h2>Who we are</h2>
<p>Facelift builds and improves websites for small businesses. We contact
business owners with a free preview of an improved version of their own
website. Contact: <b>{email}</b>, {address}.</p>
</div>

<div class="card">
<h2>What we collect (and from where)</h2>
<p>Only business contact information that a business has published about
itself publicly - for example the email, phone number and address shown on
the business's own website or public business listing. We do not buy lists,
we do not collect private individuals' personal data, and we do not collect
anything behind logins.</p>
</div>

<div class="card">
<h2>Why we use it</h2>
<p>To send one personalized message offering our services, with proof of
work attached. If you reply "no" or use any opt-out link, your contact goes
on a permanent suppression list and you will not be contacted again. We
process such data under applicable legitimate-use / consent frameworks,
including India's DPDP Act 2023 Section 7(a) (contact voluntarily published
by a business for commercial contact) where applicable.</p>
</div>

<div class="card">
<h2>Your choices and rights</h2>
<p>- Reply <b>"no"</b> to any message: permanent opt-out, effective within
one day.<br>
- Email us to request access, correction or deletion of your data: we act
within 30 days.<br>
- Previews built for demonstration can be taken down on request, usually
within minutes.</p>
</div>

<div class="card">
<h2>Retention &amp; security</h2>
<p>We keep only the minimum business contact data needed to honor this
notice. Opt-out records are kept indefinitely so that we never contact you
again. No payment card data ever touches our systems - payments run on
hosted Razorpay/Stripe pages.</p>
</div>

<p class="small">Questions? {email} &middot; {address}</p>
</main></body></html>
"""


def write_privacy(dist_dir: Path) -> Path:
    import datetime as dt

    dist_dir.mkdir(parents=True, exist_ok=True)
    html = PAGE.format(
        date=dt.date.today().isoformat(),
        email="operator@example.com",
        address="ADDRESS_LINE",
    )
    out = dist_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
