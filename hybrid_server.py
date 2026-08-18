from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import time
import requests
import traceback

app = Flask(__name__)
CORS(app)

SIAMBHAU_BASE = "https://siambhau69.eu.cc"
SIAMBHAU_KEY = "FFINFO-Free69"

token_cache = {}
CACHE_TTL = 300

def get_garena_token(uid, password):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = {
        'uid': uid,
        'password': password,
        'response_type': "token",
        'client_type': "2",
        'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        'client_id': "100067"
    }
    headers = {
        'User-Agent': "GarenaMSDK/4.0.19P9(A063 ;Android 13;en;IN;)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip"
    }
    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[GarenaToken] Error: {e}")
        return None

def get_major_login(access_token, open_id):
    try:
        from Utilities.until import encode_protobuf, decode_protobuf
        import Proto.compiled.MajorLogin_pb2
        from Configuration.APIConfiguration import RELEASEVERSION

        encrypted = encode_protobuf({
            "openid": open_id,
            "logintoken": access_token,
            "platform": "4",
        }, Proto.compiled.MajorLogin_pb2.request())

        url = "https://loginbp.ggpolarbear.com/MajorLogin"
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; A063 Build/TKQ1.221220.001)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'Authorization': "Bearer",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': RELEASEVERSION,
        }
        resp = requests.post(url, data=encrypted, headers=headers, timeout=15)
        if resp.status_code == 200 and b'503' not in resp.content[:200]:
            msg = decode_protobuf(resp.content, Proto.compiled.MajorLogin_pb2.response)
            if msg and isinstance(msg, dict) and 'token' in msg:
                return msg
        print(f"[MajorLogin] Status {resp.status_code} or 503")
        return None
    except Exception as e:
        print(f"[MajorLogin] Error: {e}")
        return None

def get_own_session(region, accounts):
    cache_key = f"own_{region}"
    if cache_key in token_cache and time.time() - token_cache[cache_key]['ts'] < CACHE_TTL:
        return token_cache[cache_key]['session']

    if region not in accounts:
        return None

    garena = get_garena_token(accounts[region]['uid'], accounts[region]['password'])
    if not garena or 'access_token' not in garena:
        return None

    major = get_major_login(garena['access_token'], garena['open_id'])
    if not major or 'token' not in major:
        return None

    session = {
        'token': major['token'],
        'serverUrl': major.get('serverUrl', ''),
        'accountid': major.get('accountid', ''),
    }
    token_cache[cache_key] = {'session': session, 'ts': time.time()}
    return session

def siambhau_request(endpoint, params):
    params['key'] = SIAMBHAU_KEY
    url = f"{SIAMBHAU_BASE}{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.status_code, resp.json() if resp.headers.get('content-type','').startswith('application/json') else {"raw": resp.text}
    except Exception as e:
        return 500, {"error": str(e)}

def load_accounts():
    try:
        with open('./Configuration/AccountConfiguration.json', 'r') as f:
            return json.load(f)
    except:
        return {}

accounts = load_accounts()


@app.route('/')
def home():
    return jsonify({
        "name": "Free Fire API v5.0 (Hybrid)",
        "version": "5.0",
        "mode": "hybrid",
        "note": "Direct Protobuf (when MajorLogin up) + SiamBhau fallback",
        "endpoints": {
            "/info": "GET ?uid=XXX&region=IND",
            "/stats": "GET ?uid=XXX&region=IND&gamemode=br&matchmode=CAREER",
            "/search": "GET ?keyword=XXX&region=IND",
            "/health": "GET health check",
        }
    })


@app.route('/health')
def health():
    return jsonify({"status": "ok", "version": "5.0", "time": time.time()})


@app.route('/info')
def player_info():
    uid = request.args.get('uid')
    region = request.args.get('region', 'IND').upper()

    if not uid or not uid.isdigit():
        return jsonify({"error": "Valid UID required", "example": "/info?uid=11959685790&region=IND"}), 400

    status, data = siambhau_request("/freefireinfo/bhau", {"uid": uid, "region": region})
    return jsonify(data), status


@app.route('/stats')
def player_stats():
    uid = request.args.get('uid')
    region = request.args.get('region', 'IND').upper()
    gamemode = request.args.get('gamemode', 'br').lower()
    matchmode = request.args.get('matchmode', 'CAREER').upper()

    if not uid or not uid.isdigit():
        return jsonify({"error": "Valid UID required", "example": "/stats?uid=11959685790&region=IND"}), 400

    status, data = siambhau_request("/freefireinfo/stats", {
        "uid": uid,
        "region": region,
        "gamemode": gamemode,
        "matchmode": matchmode
    })
    return jsonify(data), status


@app.route('/search')
def search_player():
    keyword = request.args.get('keyword')
    region = request.args.get('region', 'IND').upper()

    if not keyword or len(keyword.strip()) < 3:
        return jsonify({"error": "Keyword must be at least 3 characters"}), 400

    status, data = siambhau_request("/freefireinfo/search", {"keyword": keyword, "region": region})
    return jsonify(data), status


if __name__ == '__main__':
    print("[*] FF API v5.0 Hybrid Server starting on port 5000...")
    print("[*] Direct Protobuf + SiamBhau fallback")
    app.run(debug=True, host='0.0.0.0', port=5000)
