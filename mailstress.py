#!/usr/bin/env python3
"""
mailstress.py — Email Inbox Stress Tester
Specter | Bug Bounty Toolkit

Signs a target (test-owned) email up to hundreds of public, free mailing lists
to stress-test email infrastructure, spam filters, and inbox handling capacity.

⚠️  AUTHORIZED USE ONLY — only use against email addresses you own/control.

Usage:
    python3 mailstress.py -e test@yourdomain.com
    python3 mailstress.py -e test@yourdomain.com --threads 20
    python3 mailstress.py -e test@yourdomain.com --dry-run
    python3 mailstress.py -e test@yourdomain.com --category tech
    python3 mailstress.py --list-categories
"""

import argparse
import asyncio
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiohttp

# ─────────────────────────────────────────────────────────
#  ANSI
# ─────────────────────────────────────────────────────────
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"
C = "\033[96m"; D = "\033[90m"; B = "\033[1m"; X = "\033[0m"

BANNER = f"""{C}
  ███╗   ███╗ █████╗ ██╗██╗     ███████╗████████╗██████╗ ███████╗███████╗███████╗
  ████╗ ████║██╔══██╗██║██║     ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔════╝██╔════╝
  ██╔████╔██║███████║██║██║     ███████╗   ██║   ██████╔╝█████╗  ███████╗███████╗
  ██║╚██╔╝██║██╔══██║██║██║     ╚════██║   ██║   ██╔══██╗██╔══╝  ╚════██║╚════██║
  ██║ ╚═╝ ██║██║  ██║██║███████╗███████║   ██║   ██║  ██║███████╗███████║███████║
  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
           Email Inbox Stress Tester  |  Specter Bug Bounty Toolkit
{X}"""

# ─────────────────────────────────────────────────────────
#  DATA MODEL
# ─────────────────────────────────────────────────────────

@dataclass
class Target:
    """One mailing list signup endpoint."""
    name:     str
    url:      str
    method:   str          # GET or POST
    payload:  dict         # field_name → value ("{EMAIL}" replaced at runtime)
    headers:  dict = field(default_factory=dict)
    category: str  = "general"
    note:     str  = ""


@dataclass
class Result:
    name:    str
    success: bool
    status:  int  = 0
    error:   str  = ""


# ─────────────────────────────────────────────────────────
#  MAILING LIST DATABASE
#  All entries are publicly available, free-tier newsletter
#  or digest signup endpoints.  "{EMAIL}" is substituted
#  with the operator-supplied test address at runtime.
# ─────────────────────────────────────────────────────────

LISTS: list[Target] = [

    # ── TECH / DEV ────────────────────────────────────────
    Target("TLDR Newsletter",     "https://tldr.tech/api/signup/tech",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("TLDR AI Digest",      "https://tldr.tech/api/signup/ai",
           "POST", {"email": "{EMAIL}"}, category="tech,ai"),

    Target("TLDR Web Dev",        "https://tldr.tech/api/signup/webdev",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("TLDR DevOps",         "https://tldr.tech/api/signup/devops",
           "POST", {"email": "{EMAIL}"}, category="tech,devops"),

    Target("TLDR Security",       "https://tldr.tech/api/signup/infosec",
           "POST", {"email": "{EMAIL}"}, category="tech,security"),

    Target("TLDR Founders",       "https://tldr.tech/api/signup/founders",
           "POST", {"email": "{EMAIL}"}, category="tech,business"),

    Target("Hacker Newsletter",   "https://hackernewsletter.com/",
           "POST", {"email": "{EMAIL}", "embed": "1"}, category="tech"),

    Target("Pointer.io",          "https://www.pointer.io/api/subscribe",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("Changelog Weekly",    "https://changelog.com/weekly",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("O'Reilly Programming","https://www.oreilly.com/emails/newsletters/",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress Node",    "https://nodeweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress JS",      "https://javascriptweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress Python",  "https://pythonweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress Go",      "https://golangweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress Ruby",    "https://rubyweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress React",   "https://react.statuscode.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress Postgres","https://postgresweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Cooperpress Rust",    "https://this-week-in-rust.org/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Bytes (UI.dev)",      "https://bytes.dev/",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("Smashing Magazine",   "https://www.smashingmagazine.com/the-smashing-newsletter/",
           "POST", {"email": "{EMAIL}"}, category="tech,design"),

    Target("CSS Weekly",          "https://css-weekly.com/",
           "POST", {"email": "{EMAIL}"}, category="tech,design"),

    Target("CSS Tricks",          "https://css-tricks.com/",
           "POST", {"email": "{EMAIL}"}, category="tech,design"),

    Target("Frontend Focus",      "https://frontendfoc.us/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Mobile Dev Weekly",   "https://mobiledevweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("DB Weekly",           "https://dbweekly.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Serverless Status",   "https://serverless.email/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech,devops"),

    Target("SRE Weekly",          "https://sreweekly.com/",
           "POST", {"email": "{EMAIL}"}, category="tech,devops"),

    Target("DevOps Weekly",       "https://www.devopsweekly.com/",
           "POST", {"email": "{EMAIL}"}, category="tech,devops"),

    Target("Docker Weekly",       "https://www.docker.com/newsletter-subscription",
           "POST", {"email": "{EMAIL}"}, category="tech,devops"),

    Target("KubeWeekly",          "https://kubeweekly.io/",
           "POST", {"email": "{EMAIL}"}, category="tech,devops"),

    Target("StatusCode Weekly",   "https://statuscode.com/",
           "POST", {"email": "{EMAIL}", "form_email": "{EMAIL}"}, category="tech"),

    Target("Software Lead Weekly","https://softwareleadweekly.com/",
           "POST", {"email": "{EMAIL}"}, category="tech,business"),

    Target("The Pragmatic Engineer","https://newsletter.pragmaticengineer.com/",
           "POST", {"email": "{EMAIL}"}, category="tech,business"),

    Target("Engineering Enablement","https://www.engineeringenablement.com/",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("Console Newsletter",  "https://console.dev/",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("Unzip.dev",           "https://unzip.dev/",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    Target("Syntax.fm Newsletter","https://syntax.fm/",
           "POST", {"email": "{EMAIL}"}, category="tech"),

    # ── SECURITY / INFOSEC ────────────────────────────────
    Target("Krebs on Security",   "https://krebsonsecurity.com/",
           "POST", {"email": "{EMAIL}", "subscribe": "Subscribe"}, category="security"),

    Target("Risky Biz Newsletter","https://risky.biz/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("tl;dr sec",           "https://tldrsec.com/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Security Weekly",     "https://securityweekly.com/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Hacker News Digest",  "https://www.hndigest.com/",
           "POST", {"email": "{EMAIL}"}, category="security,tech"),

    Target("SANS NewsBites",      "https://www.sans.org/newsletters/newsbites/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Dark Reading Digest", "https://www.darkreading.com/newsletter",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Schneier on Security","https://www.schneier.com/crypto-gram/subscribe/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Troy Hunt Blog",      "https://www.troyhunt.com/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Zero Day Initiative", "https://www.zerodayinitiative.com/blog",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Recorded Future Intel","https://www.recordedfuture.com/",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("The Hacker News",     "https://feeds.feedburner.com/TheHackersNews",
           "GET",  {"email": "{EMAIL}"}, category="security"),

    Target("CISA Alerts",         "https://www.cisa.gov/subscribe-updates-cisa",
           "POST", {"email": "{EMAIL}"}, category="security"),

    Target("Wizer Security",      "https://www.wizer-training.com/blog",
           "POST", {"email": "{EMAIL}"}, category="security"),

    # ── AI / ML ───────────────────────────────────────────
    Target("The Batch (DeepLearningAI)",
           "https://www.deeplearning.ai/the-batch/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("Import AI",           "https://us13.list-manage.com/subscribe/post",
           "POST", {"EMAIL": "{EMAIL}", "u": "67bd06787039f7b3c1b7d3d5c",
                    "id": "87efff942c"}, category="ai"),

    Target("The Algorithm (MIT TR)","https://www.technologyreview.com/newsletter/the-algorithm/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("Last Week in AI",     "https://lastweekin.ai/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("The Neuron AI",       "https://www.theneurondaily.com/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("Superhuman AI",       "https://www.superhuman.ai/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("Ben's Bites",         "https://www.bensbites.co/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("Hugging Face Newsletter","https://huggingface.co/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("AlphaSignal AI",      "https://alphasignal.ai/",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    Target("AI Breakfast",        "https://aibreakfast.beehiiv.com/subscribe",
           "POST", {"email": "{EMAIL}"}, category="ai"),

    # ── CRYPTO / WEB3 ─────────────────────────────────────
    Target("CoinDesk Newsletter", "https://www.coindesk.com/newsletters/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("The Defiant",         "https://thedefiant.io/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("Bankless",            "https://www.bankless.com/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("Week in Ethereum",    "https://weekinethereumnews.com/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("Messari Crypto",      "https://messari.io/newsletter",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("Decrypt Daily",       "https://decrypt.co/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("The Block Research",  "https://www.theblock.co/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("CryptoSlate Weekly",  "https://cryptoslate.com/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    Target("Milk Road",           "https://www.milkroad.com/",
           "POST", {"email": "{EMAIL}"}, category="crypto"),

    # ── BUSINESS / STARTUPS ──────────────────────────────
    Target("Morning Brew",        "https://www.morningbrew.com/daily/r",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Axios Pro Rata",      "https://www.axios.com/newsletters/axios-pro-rata",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("The Hustle",          "https://thehustle.co/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Stratechery",         "https://stratechery.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("First Round Review",  "https://review.firstround.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("a16z Newsletter",     "https://a16z.com/newsletters/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("SaaStr Weekly",       "https://www.saastr.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Indie Hackers",       "https://www.indiehackers.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Product Hunt Daily",  "https://www.producthunt.com/newsletter",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Startup Digest",      "https://www.startupdigest.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Failory Newsletter",  "https://www.failory.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    Target("Newsletter Operator", "https://www.newsletteroperator.com/",
           "POST", {"email": "{EMAIL}"}, category="business"),

    # ── MARKETING / GROWTH ───────────────────────────────
    Target("Growth Hackers",      "https://growthhackers.com/",
           "POST", {"email": "{EMAIL}"}, category="marketing"),

    Target("Marketing Brew",      "https://www.morningbrew.com/marketing/r",
           "POST", {"email": "{EMAIL}"}, category="marketing"),

    Target("SparkLoop",           "https://sparkloop.app/",
           "POST", {"email": "{EMAIL}"}, category="marketing"),

    Target("MKT1 Newsletter",     "https://mkt1.substack.com/",
           "POST", {"email": "{EMAIL}"}, category="marketing"),

    Target("Everyone Hates Marketers","https://www.everyonehatesmarketers.com/",
           "POST", {"email": "{EMAIL}"}, category="marketing"),

    # ── GENERAL / NEWS ───────────────────────────────────
    Target("The Browser",         "https://thebrowser.com/",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("Quartz Daily Brief",  "https://qz.com/emails/daily-brief/",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("NextDraft",           "https://nextdraft.com/",
           "POST", {"email": "{EMAIL}", "ne": "{EMAIL}"}, category="general"),

    Target("Five Things (BBC)",   "https://www.bbc.com/newsletters",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("Politico Playbook",   "https://www.politico.com/newsletters/playbook",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("The Skimm",           "https://www.theskimm.com/",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("1440 Daily Digest",   "https://join1440.com/",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("Dense Discovery",     "https://www.densediscovery.com/",
           "POST", {"email": "{EMAIL}"}, category="general"),

    Target("Kottke Noticing",     "https://kottke.org/newsletter",
           "POST", {"email": "{EMAIL}"}, category="general"),

    # ── SCIENCE / DATA ───────────────────────────────────
    Target("Data Elixir",         "https://dataelixir.com/",
           "POST", {"email": "{EMAIL}"}, category="data"),

    Target("Data Science Weekly", "https://www.datascienceweekly.org/",
           "POST", {"email": "{EMAIL}"}, category="data"),

    Target("Towards Data Science","https://towardsdatascience.com/",
           "POST", {"email": "{EMAIL}"}, category="data"),

    Target("Analytics Vidhya",    "https://www.analyticsvidhya.com/blog/",
           "POST", {"email": "{EMAIL}"}, category="data"),

    Target("O'Reilly Data",       "https://www.oreilly.com/emails/newsletters/",
           "POST", {"email": "{EMAIL}", "interest": "data"}, category="data"),

    Target("Numlock News",        "https://numlock.substack.com/",
           "POST", {"email": "{EMAIL}"}, category="data"),

    # ── OPEN SOURCE ──────────────────────────────────────
    Target("GitHub Newsletter",   "https://resources.github.com/newsletter/",
           "POST", {"email": "{EMAIL}"}, category="opensource"),

    Target("Linux Foundation",    "https://www.linuxfoundation.org/newsletter/",
           "POST", {"email": "{EMAIL}"}, category="opensource"),

    Target("OSS Security Digest", "https://oss-security.openwall.org/wiki/mailing-lists",
           "GET",  {"email": "{EMAIL}"}, category="opensource,security"),

    Target("Apache Announce",     "https://www.apache.org/foundation/mailinglists.html",
           "GET",  {"email": "{EMAIL}"}, category="opensource"),
]


# ─────────────────────────────────────────────────────────
#  ASYNC SUBMISSION ENGINE
# ─────────────────────────────────────────────────────────

UA_POOL = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 Safari/605.1.15",
]


def inject_email(d: dict, email: str) -> dict:
    return {k: v.replace("{EMAIL}", email) for k, v in d.items()}


async def submit(session: aiohttp.ClientSession, target: Target,
                 email: str, dry_run: bool) -> Result:
    payload = inject_email(target.payload, email)
    hdrs = {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/json,*/*",
        **target.headers
    }

    if dry_run:
        return Result(target.name, True, 0, "DRY-RUN")

    try:
        if target.method == "POST":
            r = await session.post(target.url, data=payload, headers=hdrs,
                                   timeout=aiohttp.ClientTimeout(total=12),
                                   allow_redirects=True)
        else:
            r = await session.get(target.url, params=payload, headers=hdrs,
                                  timeout=aiohttp.ClientTimeout(total=12),
                                  allow_redirects=True)

        # Many signup pages return 200/302 for any input — we treat both as success
        success = r.status in (200, 201, 301, 302, 303)
        return Result(target.name, success, r.status)

    except asyncio.TimeoutError:
        return Result(target.name, False, 0, "timeout")
    except aiohttp.ClientSSLError:
        return Result(target.name, False, 0, "ssl_error")
    except aiohttp.ClientConnectorError:
        return Result(target.name, False, 0, "connection_refused")
    except Exception as e:
        return Result(target.name, False, 0, str(e)[:60])


async def run_all(targets: list[Target], email: str,
                  concurrency: int, dry_run: bool,
                  delay: float) -> list[Result]:

    results: list[Result] = []
    semaphore = asyncio.Semaphore(concurrency)
    total = len(targets)

    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:

        async def bounded(t: Target, idx: int) -> Result:
            async with semaphore:
                if delay > 0:
                    await asyncio.sleep(delay + random.uniform(0, delay * 0.5))
                res = await submit(session, t, email, dry_run)

                icon  = f"{G}✓{X}" if res.success else f"{R}✗{X}"
                label = f"{G}{res.name}{X}" if res.success else f"{D}{res.name}{X}"
                err   = f" {D}[{res.error}]{X}" if res.error and res.error != "DRY-RUN" else ""
                status_str = f"{D}[{res.status}]{X}" if res.status else ""
                print(f"  {icon} {label} {status_str}{err}  "
                      f"{D}({idx}/{total}){X}")
                return res

        tasks = [bounded(t, i + 1) for i, t in enumerate(targets)]
        results = await asyncio.gather(*tasks)

    return results


# ─────────────────────────────────────────────────────────
#  REPORTING
# ─────────────────────────────────────────────────────────

def print_report(results: list[Result], email: str, elapsed: float):
    ok    = [r for r in results if r.success]
    fail  = [r for r in results if not r.success]
    total = len(results)

    print(f"\n{C}{'═'*60}")
    print(f"  📊  STRESS TEST REPORT")
    print(f"{'═'*60}{X}")
    print(f"  {B}Target Email :{X} {email}")
    print(f"  {B}Total Lists  :{X} {total}")
    print(f"  {B}Submitted    :{X} {G}{len(ok)}{X}")
    print(f"  {B}Failed/Skip  :{X} {R}{len(fail)}{X}")
    print(f"  {B}Success Rate :{X} {round(len(ok)/total*100, 1)}%")
    print(f"  {B}Elapsed      :{X} {round(elapsed, 2)}s")
    print(f"{C}{'═'*60}{X}\n")

    if fail:
        print(f"{Y}── Failed submissions ─────────────────────────────────{X}")
        for r in fail:
            print(f"  {R}✗{X} {r.name:<35} {D}{r.error}{X}")
        print()


def export_json(results: list[Result], email: str):
    fname = f"mailstress_{email.replace('@','_at_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    data = [{"name": r.name, "success": r.success,
             "status": r.status, "error": r.error} for r in results]
    with open(fname, "w") as f:
        json.dump({"email": email, "results": data}, f, indent=2)
    print(f"{G}[✓] Report saved → {fname}{X}\n")


# ─────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────

def get_categories() -> list[str]:
    cats: set[str] = set()
    for t in LISTS:
        for c in t.category.split(","):
            cats.add(c.strip())
    return sorted(cats)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Specter MailStress — Inbox flood stress tester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    p.add_argument("-e", "--email",     required=False, metavar="ADDR",
                   help="Target test email address (must be owned/authorized)")
    p.add_argument("--threads",         type=int, default=15, metavar="N",
                   help="Concurrent submissions (default: 15)")
    p.add_argument("--delay",           type=float, default=0.1, metavar="SECS",
                   help="Base delay between submissions per worker (default: 0.1)")
    p.add_argument("--category",        metavar="CAT",
                   help="Filter to a specific category (e.g. tech, security, ai)")
    p.add_argument("--list-categories", action="store_true",
                   help="List available categories and count")
    p.add_argument("--dry-run",         action="store_true",
                   help="Simulate without sending any real requests")
    p.add_argument("--export",          action="store_true",
                   help="Save results to JSON")
    p.add_argument("--no-banner",       action="store_true",
                   help="Suppress ASCII banner")
    return p


async def async_main(args):
    if not args.no_banner:
        print(BANNER)

    if args.list_categories:
        cats = get_categories()
        print(f"\n{C}Available categories:{X}")
        for cat in cats:
            count = sum(1 for t in LISTS if cat in t.category)
            print(f"  {B}{cat:<20}{X} {count} lists")
        print()
        sys.exit(0)

    if not args.email:
        print(f"{R}[!] --email is required. Run with --help for usage.{X}")
        sys.exit(1)

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", args.email):
        print(f"{R}[!] Invalid email address: {args.email}{X}")
        sys.exit(1)

    targets = LISTS
    if args.category:
        targets = [t for t in LISTS if args.category.lower() in t.category]
        if not targets:
            print(f"{R}[!] No lists found for category: {args.category}{X}")
            sys.exit(1)

    dry_tag = f" {Y}[DRY-RUN]{X}" if args.dry_run else ""
    print(f"{B}[*] Target       :{X} {args.email}")
    print(f"{B}[*] Lists queued :{X} {len(targets)}")
    print(f"{B}[*] Concurrency  :{X} {args.threads}{dry_tag}")
    print(f"\n{D}{'─'*60}{X}\n")

    t0 = time.time()
    results = await run_all(targets, args.email, args.threads,
                             args.dry_run, args.delay)
    elapsed = time.time() - t0

    print_report(results, args.email, elapsed)

    if args.export:
        export_json(results, args.email)


def main():
    parser = build_parser()
    args   = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
