import os
import time
import random
import string
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, 
    url_for, session, flash, jsonify
)
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException

app = Flask(
    __name__, 
    template_folder='../templates', 
    static_folder='../static'
)

app.secret_key = os.getenv("SECRET_KEY", "microearnx_permanent_super_secure_key_2026_xyz99")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=60)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

@app.before_request
def make_session_permanent():
    session.permanent = True
    
class VercelPathFixer:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # আসল রিকোয়েস্ট পাথ ঠিক রাখা
        raw_uri = environ.get('HTTP_X_FORWARDED_URI') or environ.get('REQUEST_URI') or ''
        if raw_uri:
            environ['PATH_INFO'] = raw_uri.split('?')[0]
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixer(app.wsgi_app)


SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_SECRET_PASS = os.getenv("ADMIN_KEY", "Admin@MicroEarnX_2026")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "778208271755-8oh2uvvmme9mgjdco00ja58hv91jojbt.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://taskawallet.online/auth/google/callback")

BREVO_SMTP_LOGIN = os.getenv("BREVO_SMTP_LOGIN", "")
BREVO_SMTP_KEY = os.getenv("BREVO_SMTP_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "support@taskwallet.online")

def send_brevo_otp_email(to_email, otp_code):
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_KEY:
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"{otp_code} is your TaskWallet Password Reset Code"
        msg['From'] = f"TaskWallet Security <{BREVO_SENDER_EMAIL}>"
        msg['To'] = to_email

        html_content = f"""
        <div style="background-color: #04060b; color: #f1f5f9; padding: 40px 20px; font-family: 'Segoe UI', Tahoma, sans-serif; text-align: center;">
            <div style="max-width: 480px; margin: 0 auto; background-color: #0a0e17; border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; padding: 35px 25px;">
                <h1 style="font-size: 24px; font-weight: normal; color: #ffffff; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px;">TASK<span style="color: #38bdf8; font-style: italic; text-transform: lowercase;">wallet</span></h1>
                <p style="color: #94a3b8; font-size: 13px; margin-bottom: 25px;">পাসওয়ার্ড রিসেট ভেরিফিকেশন কোড</p>
                
                <div style="background: rgba(37, 99, 235, 0.1); border: 1px solid rgba(37, 99, 235, 0.3); border-radius: 16px; padding: 18px; margin-bottom: 25px;">
                    <span style="font-size: 36px; font-weight: 900; letter-spacing: 8px; color: #38bdf8; font-family: monospace;">{otp_code}</span>
                </div>
                
                <p style="color: #94a3b8; font-size: 12px; line-height: 1.6; margin-bottom: 20px;">
                    এই কোডটি আগামী ১৫ মিনিটের জন্য কার্যকর থাকবে। আপনি যদি এই অনুরোধ না করে থাকেন, তবে মেসেজটি এড়িয়ে যান।
                </p>
                <div style="border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 15px;">
                    <p style="color: #f59e0b; font-size: 11px;">⚠️ ইনবক্সে না পেলে অবশ্যই আপনার জিমেইলের <strong>Spam / Junk</strong> ফোল্ডার চেক করুন।</p>
                </div>
            </div>
        </div>
        """
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp-relay.brevo.com', 587, timeout=10)
        server.starttls()
        server.login(BREVO_SMTP_LOGIN, BREVO_SMTP_KEY)
        server.sendmail(BREVO_SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("SMTP Error:", e)
        return False




@app.errorhandler(Exception)
def handle_global_error(e):
    if isinstance(e, HTTPException):
        return e
    return render_template('base.html', content="সার্ভারে সাময়িক চাপ রয়েছে। অনুগ্রহ করে রিলোড দিন।"), 200

def kyc_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("অনুগ্রহ করে প্রথমে লগইন করুন!", "danger")
            return redirect(url_for('index'))
        
        sb = get_supabase()
        user_id = session['user_id']
        
        user = sb.table('users').select('email').eq('id', user_id).single().execute().data
        if user and user.get('email') == 'admin@gmail.com':
            return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("অনুগ্রহ করে প্রথমে লগইন করুন!", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("শুধুমাত্র অনুমোদিত অ্যাডমিন এক্সেস করতে পারবে!", "danger")
            return redirect(url_for('index'))
        
        sb = get_supabase()
        user = sb.table('users').select('email').eq('id', session['user_id']).single().execute().data
        if not user or user.get('email') != 'admin@gmail.com':
            flash("অননুমোদিত প্রবেশ! আপনার এই পেজে আসার অনুমতি নেই।", "danger")
            return redirect(url_for('dashboard'))

        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))

        return f(*args, **kwargs)
    return decorated_function

def upload_to_imgbb(file_bytes):
    sb = get_supabase()
    keys_res = sb.table('imgbb_keys').select('*').eq('is_active', True).execute()
    keys = keys_res.data or []

    for key_row in keys:
        api_key = key_row['api_key']
        try:
            url = "https://api.imgbb.com/1/upload"
            payload = {'key': api_key}
            files = {'image': file_bytes}
            res = requests.post(url, data=payload, files=files, timeout=8)
            data = res.json()
            if res.status_code == 200 and data.get('success'):
                return data['data']['url']
            else:
                continue
        except Exception:
            continue
    return None

def extract_yt_id(url):
    regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    return match.group(1) if match else None

def generate_math_problem():
    op_type = random.choice(['add', 'sub', 'mul'])
    if op_type == 'add':
        n1 = random.randint(25, 75)
        n2 = random.randint(15, 65)
        ans = n1 + n2
        expr = f"{n1} + {n2}"
    elif op_type == 'sub':
        n1 = random.randint(50, 99)
        n2 = random.randint(15, 49)
        ans = n1 - n2
        expr = f"{n1} - {n2}"
    else:
        n1 = random.randint(8, 16)
        n2 = random.randint(5, 12)
        ans = n1 * n2
        expr = f"{n1} × {n2}"

    options = {ans}
    while len(options) < 4:
        offset = random.choice([-10, -5, -2, -1, 1, 2, 5, 10])
        fake = ans + offset
        if fake > 0:
            options.add(fake)

    opts = list(options)
    random.shuffle(opts)
    return expr, ans, opts

def auto_release_expired_gmail_tasks(sb):
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    sb.table('gmail_tasks').update({
        'status': 'available',
        'locked_by': None,
        'locked_at': None
    }).eq('status', 'locked').lt('locked_at', two_hours_ago).execute()




# ==========================================================
# VIP TIERS CONFIGURATION (UPDATED WITH NEW RULES)
# ==========================================================
TIER_CONFIG = {
    'wood': {
        'name': 'Wood (কাঠ)',
        'price': 0,
        'validity_days': None,
        'min_withdraw': 500,
        'withdraw_time': '6 Hours',
        'ref_required': 5,      # ৫টি রেফার
        'daily_free': 0,
        'spin_quiz_mult': 1.0,
        'badge_color': 'amber',
        'accent': '#b45309'
    },
    'bronze': {
        'name': 'Bronze (ব্রোঞ্জ)',
        'price': 110,
        'validity_days': 15,
        'min_withdraw': 200,    # মাত্র ২০০৳
        'withdraw_time': '3 Hours',
        'ref_required': 1,      # মাত্র ১টি রেফার!
        'daily_free': 10,
        'spin_quiz_mult': 1.0,
        'badge_color': 'orange',
        'accent': '#ea580c'
    },
    'silver': {
        'name': 'Silver (সিলভার)',
        'price': 250,
        'validity_days': 15,
        'min_withdraw': 100,    # মাত্র ১০০৳
        'withdraw_time': '1 Hour',
        'ref_required': 0,      # ০ রেফারেল
        'daily_free': 23,
        'spin_quiz_mult': 1.0,
        'badge_color': 'slate',
        'accent': '#94a3b8'
    },
    'gold': {
        'name': 'Gold (গোল্ড)',
        'price': 400,
        'validity_days': 15,
        'min_withdraw': 50,     # মাত্র ৫০৳
        'withdraw_time': '30 Mins',
        'ref_required': 0,      # ০ রেফারেল
        'daily_free': 30,
        'spin_quiz_mult': 1.5,
        'badge_color': 'yellow',
        'accent': '#f59e0b'
    },
    'diamond': {
        'name': 'Diamond (ডায়মন্ড)',
        'price': 700,
        'validity_days': 15,
        'min_withdraw': 20,     # মাত্র ২০৳
        'withdraw_time': '2 Mins', # ২ মিনিট পেআউট
        'ref_required': 0,      # ০ রেফারেল
        'daily_free': 55,
        'spin_quiz_mult': 2.0,
        'badge_color': 'cyan',
        'accent': '#06b6d4'
    }
        }

# ==========================================================
# PASSWORD RESET SYSTEM (/reset)
# ==========================================================
@app.route('/reset')
def reset_page():
    return render_template('reset.html')

@app.route('/reset/check-email', methods=['POST'])
def reset_check_email():
    sb = get_supabase()
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({"success": False, "status": "empty", "message": "ইমেইল প্রদান করুন!"})

    # ১. ইউজার খুঁজে দেখা
    user_res = sb.table('users').select('*').eq('email', email).execute().data
    if not user_res:
        return jsonify({
            "success": False,
            "status": "not_registered",
            "message": "আপনার কোনো অ্যাকাউন্ট খোলা নেই! অ্যাকাউন্ট খুলতে সাইন-আপ পেইজে যান।"
        })

    user = user_res[0]

    # ২. গুগল সোশ্যাল লগইন কিনা চেক
    pwd_hash = user.get('password_hash', '')
    avatar = user.get('avatar_url', '') or ''
    if pwd_hash.startswith('G-AUTH') or 'googleusercontent.com' in avatar:
        return jsonify({
            "success": False,
            "status": "social_account",
            "message": "আপনি Continue with Google-এর মাধ্যমে অ্যাকাউন্ট খুলেছেন। লগইন পেইজে গিয়ে গুগলে চেষ্টা করুন অথবা সাপোর্টে মেসেজ দিন।"
        })

    # ৩. ডাটাবেসে রিসেন্ট ওটিপি চেক (রিফ্রেশ দিলেও হ্যাক আটকাবে)
    recent_res = sb.table('password_resets').select('*').eq('email', email).order('id', desc=True).limit(1).execute().data
    attempts = 0
    if recent_res:
        row = recent_res[0]
        attempts = row.get('attempts', 0)
        # যদি ইতোমধ্যে ২ বার পাঠানো হয়ে থাকে
        if attempts >= 2:
            return jsonify({
                "success": False,
                "status": "limit_exceeded",
                "message": "আপনি সর্বোচ্চ ২ বার কোড পাঠিয়েছেন! অনুগ্রহ করে আপনার জিমেইলের Spam/Junk ফোল্ডার চেক করুন অথবা সাপোর্টে কথা বলুন।"
            })

    # ৪. ওটিপি তৈরি ও সেভ
    otp_code = str(random.randint(100000, 999999))
    sent = send_brevo_otp_email(email, otp_code)
    
    if not sent:
        return jsonify({"success": False, "status": "smtp_error", "message": "ইমেইল পাঠাতে সমস্যা হচ্ছে। অনুগ্রহ করে সাপোর্টে মেসেজ দিন।"})

    new_attempts = attempts + 1
    if recent_res and attempts > 0:
        sb.table('password_resets').update({
            'otp_code': otp_code,
            'attempts': new_attempts,
            'last_sent_at': datetime.now(timezone.utc).isoformat(),
            'is_used': False
        }).eq('id', recent_res[0]['id']).execute()
    else:
        sb.table('password_resets').insert({
            'email': email,
            'otp_code': otp_code,
            'attempts': 1,
            'is_used': False
        }).execute()

    return jsonify({
        "success": True,
        "status": "otp_sent",
        "attempts": new_attempts,
        "message": "আপনার ইমেইলে ৬ ডিজিটের কোড পাঠানো হয়েছে। ইনবক্সের পাশাপাশি অবশ্যই Spam/Junk ফোল্ডার চেক করুন।"
    })

@app.route('/reset/resend-otp', methods=['POST'])
def reset_resend_otp():
    sb = get_supabase()
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    recent_res = sb.table('password_resets').select('*').eq('email', email).order('id', desc=True).limit(1).execute().data
    if not recent_res:
        return jsonify({"success": False, "message": "অবৈধ অনুরোধ!"})

    row = recent_res[0]
    if row.get('attempts', 0) >= 2:
        return jsonify({"success": False, "message": "আপনি সর্বোচ্চ ২ বার কোড পাঠিয়েছেন! স্প্যাম ফোল্ডার চেক করুন।"})

    # ১.৫ মিনিট (৯০ সেকেন্ড) কুলডাউন যাচাই
    last_sent = datetime.fromisoformat(row['last_sent_at'].replace('Z', '+00:00'))
    diff_sec = (datetime.now(timezone.utc) - last_sent).total_seconds()
    if diff_sec < 90:
        remaining_wait = int(90 - diff_sec)
        return jsonify({"success": False, "message": f"অনুগ্রহ করে আরও {remaining_wait} সেকেন্ড অপেক্ষা করুন।"})

    otp_code = str(random.randint(100000, 999999))
    send_brevo_otp_email(email, otp_code)

    sb.table('password_resets').update({
        'otp_code': otp_code,
        'attempts': 2,
        'last_sent_at': datetime.now(timezone.utc).isoformat(),
        'is_used': False
    }).eq('id', row['id']).execute()

    return jsonify({
        "success": True,
        "attempts": 2,
        "message": "দ্বিতীয়বারের মতো কোড পাঠানো হয়েছে। এটিই শেষ কোড। অবশ্যই Spam বক্স চেক করবেন।"
    })





# ==========================================================
# USER UPGRADE CONTROLLERS
# ==========================================================
@app.route('/upgrade')
@login_required
def upgrade_page():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    # মেয়াদোত্তীর্ণ টিয়ার যাচাই
    current_tier = user.get('tier') or 'wood'
    expires_at = user.get('tier_expires_at')
    is_expired = False
    if expires_at and current_tier != 'wood':
        exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > exp_dt:
            is_expired = True
            sb.table('users').update({'tier': 'wood', 'tier_expires_at': None}).eq('id', user_id).execute()
            current_tier = 'wood'

    # ব্যবহারকারীর অ্যাডমিন অনুমোদিত কোনো প্যাকেজ ক্লেইমের জন্য অপেক্ষা করছে কিনা
    ready_to_claim = sb.table('upgrade_requests').select('*')\
        .eq('user_id', user_id)\
        .eq('status', 'approved')\
        .order('id', desc=True).limit(1).execute().data
    
    pending_req = sb.table('upgrade_requests').select('*')\
        .eq('user_id', user_id)\
        .eq('status', 'pending')\
        .order('id', desc=True).limit(1).execute().data

    # দৈনিক ফ্রি রিওয়ার্ড ক্লেইম চেক
    can_claim_daily = False
    daily_reward_amount = TIER_CONFIG.get(current_tier, {}).get('daily_free', 0)
    if daily_reward_amount > 0:
        last_claim = user.get('last_daily_claim')
        if not last_claim:
            can_claim_daily = True
        else:
            last_claim_dt = datetime.fromisoformat(last_claim.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - last_claim_dt).total_seconds() >= 86400:
                can_claim_daily = True

    return render_template(
        'upgrade.html',
        user=user,
        current_tier=current_tier,
        tier_config=TIER_CONFIG,
        ready_to_claim=ready_to_claim[0] if ready_to_claim else None,
        pending_req=pending_req[0] if pending_req else None,
        can_claim_daily=can_claim_daily,
        daily_reward_amount=daily_reward_amount
    )

@app.route('/upgrade/checkout/<tier_name>', methods=['GET', 'POST'])
@login_required
def upgrade_checkout(tier_name):
    tier_name = tier_name.lower()
    if tier_name not in TIER_CONFIG or tier_name == 'wood':
        flash("অবৈধ প্যাকেজ নির্বাচন!", "danger")
        return redirect(url_for('upgrade_page'))

    tier_info = TIER_CONFIG[tier_name]
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    if request.method == 'POST':
        sender_number = request.form.get('sender_number', '').strip()
        trx_id = request.form.get('trx_id', '').strip()

        if not sender_number or not trx_id:
            flash("সবগুলো তথ্য সঠিকভাবে পূরণ করুন!", "danger")
            return redirect(url_for('upgrade_checkout', tier_name=tier_name))

        # ডুপ্লিকেট ট্রানজেকশন চেক
        dup_trx = sb.table('upgrade_requests').select('id').eq('trx_id', trx_id).execute().data
        if dup_trx:
            flash("এই TrxID দিয়ে ইতিমধ্যে একটি রিকোয়েস্ট জমা দেওয়া হয়েছে!", "danger")
            return redirect(url_for('upgrade_checkout', tier_name=tier_name))

        sb.table('upgrade_requests').insert({
            'user_id': user_id,
            'tier': tier_name,
            'price': tier_info['price'],
            'sender_number': sender_number,
            'trx_id': trx_id,
            'status': 'pending'
        }).execute()

        flash("🎉 পেমেন্ট রিকোয়েস্ট সফলভাবে জমা হয়েছে! অ্যাডমিন যাচাই করে অনুমোদন দেওয়ার পর প্যাকেজ ক্লেইম করতে পারবেন।", "success")
        return redirect(url_for('upgrade_page'))

    return render_template('upgrade_checkout.html', user=user, tier=tier_name, tier_info=tier_info)

@app.route('/upgrade/claim-tier/<int:req_id>', methods=['POST'])
@login_required
def upgrade_claim_tier(req_id):
    sb = get_supabase()
    user_id = session['user_id']

    req = sb.table('upgrade_requests').select('*')\
        .eq('id', req_id)\
        .eq('user_id', user_id)\
        .eq('status', 'approved').single().execute().data

    if not req:
        flash("অনুমোদিত কোনো প্যাকেজ পাওয়া যায়নি!", "danger")
        return redirect(url_for('upgrade_page'))

    tier_name = req['tier']
    validity = TIER_CONFIG[tier_name]['validity_days'] or 15
    expires_at = (datetime.now(timezone.utc) + timedelta(days=validity)).isoformat()

    # ইউজারের টিয়ার আপডেট ও রিকোয়েস্ট স্ট্যাটাস claimed করা
    sb.table('users').update({
        'tier': tier_name,
        'tier_expires_at': expires_at
    }).eq('id', user_id).execute()

    sb.table('upgrade_requests').update({'status': 'claimed'}).eq('id', req_id).execute()

    flash(f"🎉 অভিনন্দন! আপনার {TIER_CONFIG[tier_name]['name']} সফলভাবে সক্রিয় হয়েছে।", "success")
    return redirect(url_for('upgrade_page'))

@app.route('/upgrade/claim-daily', methods=['POST'])
@login_required
def upgrade_claim_daily():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    current_tier = user.get('tier', 'wood')
    daily_reward = TIER_CONFIG.get(current_tier, {}).get('daily_free', 0)

    if daily_reward <= 0:
        return jsonify({"success": False, "message": "আপনার বর্তমান প্যাকেজে কোনো দৈনিক ফ্রি রিওয়ার্ড নেই!"})

    last_claim = user.get('last_daily_claim')
    if last_claim:
        last_claim_dt = datetime.fromisoformat(last_claim.replace('Z', '+00:00'))
        if (datetime.now(timezone.utc) - last_claim_dt).total_seconds() < 86400:
            return jsonify({"success": False, "message": "আপনি ইতিমধ্যে আজকের ফ্রি রিওয়ার্ড নিয়ে নিয়েছেন!"})

    new_bal = float(user['balance']) + float(daily_reward)
    sb.table('users').update({
        'balance': new_bal,
        'last_daily_claim': datetime.now(timezone.utc).isoformat()
    }).eq('id', user_id).execute()

    return jsonify({
        "success": True,
        "reward": daily_reward,
        "new_balance": new_bal,
        "message": f"🎉 ৳{daily_reward:.2f} সফলভাবে আপনার মূল ব্যালেন্সে যোগ হয়েছে!"
    })

# ==========================================================
# ADMIN UPGRADE CONTROLLERS
# ==========================================================
@app.route('/admin/upgrades')
@admin_required
def admin_upgrades_list():
    sb = get_supabase()
    reqs = sb.table('upgrade_requests').select('*, users(name, email)')\
        .order('id', desc=True).limit(50).execute().data or []
    return render_template('admin/upgrades.html', requests=reqs, tier_config=TIER_CONFIG)

@app.route('/admin/upgrades/<int:req_id>/approve', methods=['POST'])
@admin_required
def admin_upgrade_approve(req_id):
    sb = get_supabase()
    sb.table('upgrade_requests').update({
        'status': 'approved',
        'approved_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', req_id).execute()
    flash("প্যাকেজ পেমেন্ট অ্যাপ্রুভ করা হয়েছে! ইউজার এখন ক্লেইম করতে পারবে।", "success")
    return redirect(url_for('admin_upgrades_list'))

@app.route('/admin/upgrades/<int:req_id>/reject', methods=['POST'])
@admin_required
def admin_upgrade_reject(req_id):
    sb = get_supabase()
    sb.table('upgrade_requests').update({'status': 'rejected'}).eq('id', req_id).execute()
    flash("প্যাকেজ পেমেন্ট রিজেক্ট করা হয়েছে!", "warning")
    return redirect(url_for('admin_upgrades_list'))
    

@app.route('/reset/verify-otp', methods=['POST'])
def reset_verify_otp():
    sb = get_supabase()
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    code = data.get('code', '').strip()

    recent_res = sb.table('password_resets').select('*').eq('email', email).order('id', desc=True).limit(1).execute().data
    if not recent_res:
        return jsonify({"success": False, "message": "কোনো কোড পাওয়া যায়নি!"})

    row = recent_res[0]
    if row.get('is_used'):
        return jsonify({"success": False, "message": "এই কোডটি ইতিমধ্যে ব্যবহৃত হয়েছে!"})

    if row.get('otp_code') != code:
        return jsonify({"success": False, "message": "ভুল কোড দিয়েছেন! সঠিক ৬ ডিজিটের কোড দিন।"})

    session['verified_reset_email'] = email
    return jsonify({"success": True, "message": "কোড যাচাই সম্পন্ন হয়েছে!"})

@app.route('/reset/confirm-password', methods=['POST'])
def reset_confirm_password():
    sb = get_supabase()
    data = request.get_json() or {}
    new_password = data.get('password', '').strip()
    email = session.get('verified_reset_email')

    if not email:
        return jsonify({"success": False, "message": "অননুমোদিত অ্যাক্সেস! পুনরায় চেষ্টা করুন।"})

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "পাসওয়ার্ড সর্বনিম্ন ৬ অক্ষরের হতে হবে!"})

    hashed = generate_password_hash(new_password)
    sb.table('users').update({'password_hash': hashed}).eq('email', email).execute()

    # কোড এক্সপায়ার করা
    sb.table('password_resets').update({'is_used': True}).eq('email', email).execute()
    session.pop('verified_reset_email', None)

    return jsonify({"success": True, "message": "আপনার পাসওয়ার্ড সফলভাবে পরিবর্তিত হয়েছে!"})
    
@app.route('/auth/google')
def google_auth():
    ref = request.args.get('ref')
    if ref:
        session['cached_ref'] = ref.strip().upper()

    state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    session['oauth_state'] = state

    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"state={state}&"
        f"prompt=select_account"
    )
    return redirect(google_auth_url)

@app.route('/auth/google/callback')
@app.route('/auth/google/callback/')
def google_callback():
    code = request.args.get('code')
    if not code:
        flash("গুগল লগইন বাতিল করা হয়েছে!", "warning")
        return redirect(url_for('login'))

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }

    try:
        res = requests.post(token_url, data=token_data, timeout=10)
        tokens = res.json()
    except Exception:
        flash("গুগল সার্ভারে সংযোগ বিচ্ছিন্ন! পুনরায় চেষ্টা করুন।", "danger")
        return redirect(url_for('login'))

    access_token = tokens.get('access_token')
    if not access_token:
        flash("গুগল সাইন-ইন সম্পন্ন হয়নি!", "danger")
        return redirect(url_for('login'))

    userinfo_res = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={'Authorization': f"Bearer {access_token}"},
        timeout=10
    )
    user_info = userinfo_res.json()
    email = user_info.get('email', '').strip().lower()

    if not email:
        flash("ইমেইল শনাক্ত করা যায়নি!", "danger")
        return redirect(url_for('login'))

    sb = get_supabase()
    user_res = sb.table('users').select('*').eq('email', email).execute().data

    if user_res:
        user = user_res[0]
        if user.get('is_banned'):
            flash("আপনার অ্যাকাউন্টটি স্থায়ীভাবে ব্যান করা হয়েছে!", "danger")
            return redirect(url_for('login'))
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        return redirect(url_for('dashboard'))

    auto_name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
    avatar_url = user_info.get('picture')
    device_id = request.cookies.get('device_id', '')

    if device_id:
        dev_check = sb.table('users').select('id').eq('device_id', device_id).execute().data
        if dev_check:
            flash("⛔ এই ডিভাইস থেকে ইতিমধ্যে একটি অ্যাকাউন্ট খোলা হয়েছে!", "danger")
            return redirect(url_for('login'))

    cached_ref = session.get('cached_ref', '')
    valid_referrer = None
    initial_balance = 50.00

    if cached_ref:
        ref_res = sb.table('users').select('*').ilike('referral_code', cached_ref).execute().data
        if ref_res:
            ref_user = ref_res[0]
            if ref_user['email'] != email and ref_user.get('device_id') != device_id:
                valid_referrer = ref_user
                initial_balance = 90.00
                new_ref_bal = float(ref_user['balance']) + 20.00
                sb.table('users').update({'balance': new_ref_bal}).eq('id', ref_user['id']).execute()

    my_ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    dummy_pass_hash = generate_password_hash("G-AUTH-" + ''.join(random.choices(string.hexdigits, k=16)))

    new_user_data = {
        'name': auto_name,
        'email': email,
        'password_hash': dummy_pass_hash,
        'device_id': device_id if device_id else 'DEV-' + ''.join(random.choices(string.hexdigits, k=16)).upper(),
        'referral_code': my_ref_code,
        'referred_by': valid_referrer['referral_code'] if valid_referrer else None,
        'balance': initial_balance,
        'avatar_url': avatar_url
    }

    inserted = sb.table('users').insert(new_user_data).execute()
    if inserted.data:
        session.permanent = True
        session['user_id'] = inserted.data[0]['id']
        session['user_name'] = auto_name
        session.pop('cached_ref', None)
        flash(f"🎉 স্বাগতম {auto_name}! গুগল দিয়ে সফলভাবে অ্যাকাউন্ট তৈরি হয়েছে।", "success")
        return redirect(url_for('dashboard'))

    flash("রেজিস্ট্রেশন ব্যর্থ হয়েছে, পুনরায় চেষ্টা করুন।", "danger")
    return redirect(url_for('login'))

@app.route('/tutorial')
def tutorial():
    fb_reel_url = "https://www.facebook.com/reel/1719120619189780/"
    return render_template('tutorial.html', fb_reel_url=fb_reel_url)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        return render_template('login.html')

    sb = get_supabase()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()

    if not email or not password:
        flash("ইমেইল ও পাসওয়ার্ড প্রদান করুন!", "danger")
        return redirect(url_for('login'))

    user_res = None
    for _ in range(3):
        try:
            res = sb.table('users').select('*').eq('email', email).execute()
            if res.data:
                user_res = res.data
                break
        except Exception:
            time.sleep(0.3)

    if not user_res:
        return redirect(url_for('index', not_found_email=email))

    user = user_res[0]
    if user['is_banned']:
        flash("আপনার অ্যাকাউন্টটি স্থায়ীভাবে ব্যান করা হয়েছে!", "danger")
        return redirect(url_for('login'))

    if check_password_hash(user['password_hash'], password):
        session.permanent = True
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        return redirect(url_for('dashboard'))
    else:
        flash("ভুল পাসওয়ার্ড দিয়েছেন! দয়া করে সঠিক পাসওয়ার্ড দিন।", "danger")
        return redirect(url_for('login'))

@app.route('/register', methods=['POST'])
def register():
    sb = get_supabase()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    ref_by = request.form.get('ref_by', '').strip().upper() or session.get('cached_ref', '')
    device_id = request.form.get('device_id', '').strip() or request.cookies.get('device_id', '')

    if not email or not password:
        flash("ইমেইল ও পাসওয়ার্ড প্রদান করুন!", "danger")
        return redirect(url_for('index'))

    if not email.endswith('@gmail.com'):
        flash("অনুগ্রহ করে একটি সঠিক ও বৈধ @gmail.com ইমেইল প্রদান করুন!", "danger")
        return redirect(url_for('index'))

    name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()

    if device_id:
        existing_device = sb.table('users').select('id').eq('device_id', device_id).execute().data
        if existing_device:
            flash("⛔ এই ডিভাইস থেকে ইতিমধ্যে একটি অ্যাকাউন্ট খোলা হয়েছে!", "danger")
            return redirect(url_for('index'))

    existing_email = sb.table('users').select('id').eq('email', email).execute().data
    if existing_email:
        flash("এই ইমেইল দিয়ে ইতিমধ্যে অ্যাকাউন্ট তৈরি করা আছে!", "danger")
        return redirect(url_for('login'))

    my_ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    initial_balance = 50.00

    valid_referrer = None
    if ref_by:
        referrer_res = sb.table('users').select('*').ilike('referral_code', ref_by).execute().data
        if referrer_res:
            ref_user = referrer_res[0]
            if ref_user['email'] != email and ref_user.get('device_id') != device_id:
                valid_referrer = ref_user
                initial_balance = 100.00
                new_ref_bal = float(ref_user['balance']) + 20.00
                sb.table('users').update({'balance': new_ref_bal}).eq('id', ref_user['id']).execute()

    new_user = {
        'name': name,
        'email': email,
        'password_hash': generate_password_hash(password),
        'device_id': device_id if device_id else 'DEV-' + ''.join(random.choices(string.hexdigits, k=16)).upper(),
        'referral_code': my_ref_code,
        'referred_by': valid_referrer['referral_code'] if valid_referrer else None,
        'balance': initial_balance
    }

    try:
        inserted = sb.table('users').insert(new_user).execute()
        if inserted.data:
            session.permanent = True
            session['user_id'] = inserted.data[0]['id']
            session['user_name'] = name
            session.pop('cached_ref', None)
            flash(f"অভিনন্দন {name}! আপনি ৳{initial_balance:.2f} জয়েনিং বোনাস পেয়েছেন।", "success")
            return redirect(url_for('dashboard'))
    except Exception:
        flash("রেজিস্ট্রেশন ত্রুটি, অনুগ্রহ করে পুনরায় চেষ্টা করুন।", "danger")
        
    return redirect(url_for('index'))

@app.route('/kyc', methods=['GET', 'POST'])
@login_required
def kyc_page():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    existing_kyc = sb.table('kyc_requests').select('*').eq('user_id', user_id).order('id', desc=True).execute().data
    latest_kyc = existing_kyc[0] if existing_kyc else None

    if request.method == 'POST':
        if latest_kyc and latest_kyc['status'] == 'approved':
            flash("আপনার KYC ইতিমধ্যে ভেরিফাইড রয়েছে!", "info")
            return redirect(url_for('kyc_page'))

        full_name = request.form.get('full_name', '').strip()
        try:
            age = int(request.form.get('age', 18))
        except ValueError:
            age = 13

        sender_number = request.form.get('sender_number', '').strip()
        trx_id = request.form.get('trx_id', '').strip()

        if not full_name or not sender_number or not trx_id:
            flash("সবগুলো তথ্য সঠিকভাবে পূরণ করুন!", "danger")
            return redirect(url_for('kyc_page'))

        dup_trx = sb.table('kyc_requests').select('id').eq('trx_id', trx_id).execute().data
        if dup_trx:
            flash("এই TrxID দিয়ে ইতিমধ্যে একটি রিকোয়েস্ট জমা দেওয়া হয়েছে!", "danger")
            return redirect(url_for('kyc_page'))

        sb.table('kyc_requests').insert({
            'user_id': user_id,
            'full_name': full_name,
            'age': age,
            'sender_number': sender_number,
            'trx_id': trx_id,
            'status': 'pending'
        }).execute()

        flash("🎉 আপনার KYC ভেরিফিকেশন ফি সফলভাবে জমা হয়েছে! অ্যাডমিন চেক করে ৩০ মিনিটের মধ্যে একাউন্ট ভেরিফাই করে দেবে।", "success")
        return redirect(url_for('kyc_page'))

    return render_template('kyc.html', user=user, latest_kyc=latest_kyc)

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/admin/kyc')
@admin_required
def admin_kyc_list():
    sb = get_supabase()
    page = int(request.args.get('page', 1))
    limit = 20
    offset = (page - 1) * limit

    query = sb.table('kyc_requests').select('*, users(name, email)').eq('status', 'pending')
    kyc_res = query.order('id', desc=True).range(offset, offset + limit - 1).execute().data or []

    all_pending = sb.table('kyc_requests').select('id').eq('status', 'pending').execute().data or []
    total_count = len(all_pending)
    has_next = (offset + limit) < total_count

    return render_template(
        'admin/kyc.html', 
        kyc_requests=kyc_res,
        page=page,
        has_next=has_next,
        total_count=total_count
    )

@app.route('/admin/kyc/<int:kyc_id>/approve', methods=['POST'])
@admin_required
def admin_kyc_approve(kyc_id):
    sb = get_supabase()
    req = sb.table('kyc_requests').select('*').eq('id', kyc_id).single().execute().data
    if not req or req.get('status') == 'approved':
        flash("অবৈধ বা ইতিমধ্যে অনুমোদিত রিকোয়েস্ট!", "danger")
        return redirect(url_for('admin_kyc_list'))

    sb.table('kyc_requests').update({'status': 'approved'}).eq('id', kyc_id).execute()
    flash("কেওয়াইসি সফলভাবে অ্যাপ্রুভ করা হয়েছে!", "success")
    return redirect(url_for('admin_kyc_list'))

@app.route('/admin/kyc/<int:kyc_id>/reject', methods=['POST'])
@admin_required
def admin_kyc_reject(kyc_id):
    sb = get_supabase()
    sb.table('kyc_requests').update({'status': 'rejected'}).eq('id', kyc_id).execute()
    flash("কেওয়াইসি রিকোয়েস্টটি রিজেক্ট করা হয়েছে!", "warning")
    return redirect(url_for('admin_kyc_list'))

@app.route('/sponsor', methods=['GET', 'POST'])
def sponsor():
    sb = get_supabase()
    user = None
    is_logged_in = 'user_id' in session

    if is_logged_in:
        user = sb.table('users').select('*').eq('id', session['user_id']).single().execute().data

    if request.method == 'POST':
        if not is_logged_in:
            flash("স্পনসরশিপের জন্য আবেদন করতে অনুগ্রহ করে প্রথমে লগইন করুন!", "danger")
            return redirect(url_for('index'))

        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        link = request.form.get('link', '').strip()
        description = request.form.get('description', '').strip()

        if not name or not email or not link or not description:
            flash("সবগুলো তথ্য সঠিকভাবে পূরণ করুন!", "danger")
            return redirect(url_for('sponsor'))

        sb.table('sponsors').insert({
            'user_id': session['user_id'],
            'name': name,
            'email': email,
            'link': link,
            'description': description
        }).execute()

        flash("🎉 অভিনন্দন! আপনার স্পনসরশিপ আবেদন সফলভাবে জমা হয়েছে। আমাদের পার্টনারশিপ টিম দ্রুতই আপনার সাথে যোগাযোগ করবে।", "success")
        return redirect(url_for('sponsor'))

    return render_template('sponsor.html', is_logged_in=is_logged_in, user=user)

# ==========================================================
# ANNOUNCEMENTS CONTROLLER (/announcements)
# ==========================================================
@app.route('/announcements')
def announcements():
    sb = get_supabase()
    
    # পেজ ভিউ হলে ডাটাবেসে ভিউ কাউন্ট +১ বাড়ানো
    try:
        sb.rpc('increment_announcement_views').execute()
    except Exception:
        pass

    # পোস্টগুলো আনা (নতুন পোস্ট সবার উপরে)
    posts = sb.table('announcements').select('*').order('id', desc=True).execute().data or []

    # ইউজার অ্যাডমিন কিনা চেক (শুধুমাত্র অ্যাডমিন ভিউ কাউন্ট ও পোস্ট করার ফরম দেখবে)
    is_admin = False
    if session.get('user_id'):
        u = sb.table('users').select('email').eq('id', session['user_id']).single().execute().data
        if u and u.get('email') == 'admin@gmail.com' and session.get('is_admin'):
            is_admin = True

    return render_template('announcements.html', posts=posts, is_admin=is_admin)

@app.route('/admin/announcement/create', methods=['POST'])
@admin_required
def admin_create_announcement():
    sb = get_supabase()
    caption = request.form.get('caption', '').strip()
    link_url = request.form.get('link_url', '').strip()
    link_title = request.form.get('link_title', '').strip() or 'বিস্তারিত দেখুন'
    image_file = request.files.get('image')

    if not caption:
        flash("ক্যাপশন দেওয়া আবশ্যক!", "danger")
        return redirect(url_for('announcements'))

    image_url = None
    # ইমেজ ImgBB-তে আপলোড করা
    if image_file and image_file.filename != '':
        image_url = upload_to_imgbb(image_file.read())

    sb.table('announcements').insert({
        'caption': caption,
        'image_url': image_url,
        'link_url': link_url if link_url else None,
        'link_title': link_title if link_url else None
    }).execute()

    flash("🎉 অ্যানাউন্সমেন্ট সফলভাবে প্রকাশ করা হয়েছে!", "success")
    return redirect(url_for('announcements'))

@app.route('/admin/announcement/<int:post_id>/delete', methods=['POST'])
@admin_required
def admin_delete_announcement(post_id):
    sb = get_supabase()
    sb.table('announcements').delete().eq('id', post_id).execute()
    flash("পোস্টটি মুছে ফেলা হয়েছে!", "info")
    return redirect(url_for('announcements'))
    

@app.route('/help')
def help_page():
    sb = get_supabase()
    user = None
    if 'user_id' in session:
        user = sb.table('users').select('*').eq('id', session['user_id']).single().execute().data
    return render_template('help.html', user=user)

@app.route('/help/vote', methods=['POST'])
def help_vote():
    sb = get_supabase()
    data = request.get_json() or {}
    has_tg = bool(data.get('has_telegram', False))
    user_id = session.get('user_id')

    sb.table('help_votes').insert({
        'user_id': user_id,
        'has_telegram': has_tg
    }).execute()

    return jsonify({"success": True, "message": "ভোট সফলভাবে জমা হয়েছে!"})

@app.route('/admin/promote')
@admin_required
def admin_promotions():
    sb = get_supabase()
    all_promos = sb.table('promotions').select('*').order('id', desc=True).execute().data or []
    pending_count = sum(1 for p in all_promos if p.get('status') == 'pending')
    completed_count = sum(1 for p in all_promos if p.get('status') == 'completed')

    return render_template(
        'admin/promote.html', 
        promotions=all_promos,
        pending_count=pending_count,
        completed_count=completed_count
    )

@app.route('/admin/promote/<int:promo_id>/status/<new_status>', methods=['POST'])
@admin_required
def admin_promotion_status(promo_id, new_status):
    sb = get_supabase()
    if new_status in ['pending', 'contacted', 'completed']:
        sb.table('promotions').update({'status': new_status}).eq('id', promo_id).execute()
        flash(f"ক্যাম্পেইন স্ট্যাটাস সফলভাবে '{new_status}' করা হয়েছে!", "success")
    return redirect(url_for('admin_promotions'))

@app.route('/admin/promote/<int:promo_id>/delete', methods=['POST'])
@admin_required
def admin_promotion_delete(promo_id):
    sb = get_supabase()
    sb.table('promotions').delete().eq('id', promo_id).execute()
    flash("প্রমোশন রিকোয়েস্টটি মুছে ফেলা হয়েছে!", "success")
    return redirect(url_for('admin_promotions'))

@app.route('/admin/pass', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    sb = get_supabase()
    reset_data = None
    
    if request.method == 'POST':
        user_identifier = request.form.get('user_identifier', '').strip()
        new_password = request.form.get('new_password', '').strip()

        if not user_identifier or not new_password:
            flash("ইউজারের ইমেইল/আইডি এবং নতুন পাসওয়ার্ড উভয়ই আবশ্যক!", "danger")
            return redirect(url_for('admin_change_password'))

        query = sb.table('users').select('id, name, email')
        if user_identifier.isdigit():
            user_data = query.eq('id', int(user_identifier)).execute().data
        else:
            user_data = query.eq('email', user_identifier.lower()).execute().data

        if not user_data:
            flash(f"'{user_identifier}' দিয়ে কোনো ইউজার খুঁজে পাওয়া যায়নি!", "danger")
            return redirect(url_for('admin_change_password'))

        target_user = user_data[0]
        hashed_password = generate_password_hash(new_password)
        sb.table('users').update({'password_hash': hashed_password}).eq('id', target_user['id']).execute()

        flash(f"🎉 ইউজার '{target_user['name']}' এর পাসওয়ার্ড সফলভাবে রিসেট হয়েছে!", "success")
        
        reset_data = {
            'id': target_user['id'],
            'name': target_user['name'],
            'email': target_user['email'],
            'password': new_password,
            'time': datetime.now().strftime('%d %b, %Y • %I:%M %p')
        }

    search_q = request.args.get('q', '').strip()
    u_query = sb.table('users').select('id, name, email, referral_code, created_at')
    if search_q:
        u_query = u_query.ilike('email', f"%{search_q}%")
    recent_users = u_query.order('id', desc=True).limit(10).execute().data or []

    return render_template(
        'admin/pass.html', 
        users=recent_users, 
        search_q=search_q, 
        reset_data=reset_data
    )

@app.route('/gmail')
@login_required
@kyc_required
def gmail_hub():
    sb = get_supabase()
    user_id = session['user_id']
    auto_release_expired_gmail_tasks(sb)

    my_locked_task = sb.table('gmail_tasks').select('*') \
        .eq('locked_by', user_id).in_('status', ['locked', 'submitted']).execute().data

    active_task = my_locked_task[0] if my_locked_task else None
    available_tasks = sb.table('gmail_tasks').select('*') \
        .eq('status', 'available').order('id', desc=True).execute().data or []

    return render_template('gmail.html', active_task=active_task, tasks=available_tasks)

@app.route('/gmail/lock/<int:task_id>', methods=['POST'])
@login_required
def gmail_lock_task(task_id):
    sb = get_supabase()
    user_id = session['user_id']
    auto_release_expired_gmail_tasks(sb)

    existing = sb.table('gmail_tasks').select('id') \
        .eq('locked_by', user_id).eq('status', 'locked').execute().data
    if existing:
        flash("আপনার ইতিমধ্যে একটি কাজ চালু রয়েছে! সেটি সম্পন্ন বা বাতিল করুন।", "warning")
        return redirect(url_for('gmail_hub'))

    task = sb.table('gmail_tasks').select('*').eq('id', task_id).single().execute().data
    if not task or task.get('status') != 'available':
        flash("এই কাজটি ইতিমধ্যে অন্য একজন ইউজার নিয়ে নিয়েছে!", "danger")
        return redirect(url_for('gmail_hub'))

    sb.table('gmail_tasks').update({
        'status': 'locked',
        'locked_by': user_id,
        'locked_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', task_id).execute()

    flash("টাস্কটি আপনার জন্য সফলভাবে ২ ঘণ্টার জন্য লক করা হয়েছে!", "success")
    return redirect(url_for('gmail_hub'))

@app.route('/gmail/submit/<int:task_id>', methods=['POST'])
@login_required
def gmail_submit_task(task_id):
    sb = get_supabase()
    user_id = session['user_id']

    task = sb.table('gmail_tasks').select('*').eq('id', task_id).single().execute().data
    if not task or task.get('locked_by') != user_id:
        flash("অবৈধ রিকোয়েস্ট!", "danger")
        return redirect(url_for('gmail_hub'))

    auto_email = f"{task['email_prefix']}@gmail.com"

    sb.table('gmail_tasks').update({
        'status': 'submitted',
        'submitted_email': auto_email,
        'submitted_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', task_id).execute()

    flash("🎉 কাজ সফলভাবে জমা হয়েছে! অ্যাডমিন চেক করে টাকা ব্যালেন্সে যোগ করে দেবে।", "success")
    return redirect(url_for('gmail_hub'))
    
@app.route('/gmail/cancel/<int:task_id>', methods=['POST'])
@login_required
def gmail_cancel_task(task_id):
    sb = get_supabase()
    user_id = session['user_id']
    sb.table('gmail_tasks').update({
        'status': 'available',
        'locked_by': None,
        'locked_at': None
    }).eq('id', task_id).eq('locked_by', user_id).eq('status', 'locked').execute()

    flash("টাস্কটি বাতিল করা হয়েছে এবং সবার জন্য উন্মুক্ত করে দেওয়া হয়েছে।", "info")
    return redirect(url_for('gmail_hub'))

@app.route('/admin/gmail', methods=['GET', 'POST'])
@admin_required
def admin_gmail():
    sb = get_supabase()
    auto_release_expired_gmail_tasks(sb)

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        email_prefix = request.form.get('email_prefix', '').strip()
        password = request.form.get('password', '').strip()
        try:
            price = float(request.form.get('price', 8.00))
        except ValueError:
            price = 8.00

        sb.table('gmail_tasks').insert({
            'first_name': first_name,
            'email_prefix': email_prefix,
            'password': password,
            'price': price,
            'status': 'available'
        }).execute()

        flash("নতুন জিমেইল ফার্মিং টাস্ক সফলভাবে তৈরি হয়েছে!", "success")
        return redirect(url_for('admin_gmail'))

    submitted_tasks = sb.table('gmail_tasks').select('*, users(name, email)') \
        .eq('status', 'submitted').order('submitted_at', desc=True).execute().data or []
    all_tasks = sb.table('gmail_tasks').select('*').order('id', desc=True).limit(50).execute().data or []

    return render_template('admin/gmail.html', submitted=submitted_tasks, all_tasks=all_tasks)


# ==========================================================
# REFERRAL LEADERBOARD CONTROLLER (/leaderboard)
# ==========================================================
@app.route('/leaderboard')
def referral_leaderboard():
    sb = get_supabase()
    user_id = session.get('user_id')
    my_stats = None
    leaders = []

    try:
        # ১. সরাসরি ডেটাবেস ফাংশন থেকে টপ ৩০ রেফারার আনা
        res = sb.rpc('get_referral_leaderboard', {'limit_count': 30}).execute()
        leaders = res.data or []
    except Exception:
        # ফলব্যাক ব্যাকআপ (যদি কখনো RPC কল মিস হয়)
        users_res = sb.table('users').select('id, name, avatar_url, referral_code').eq('is_banned', False).execute().data or []
        all_refs = sb.table('users').select('referred_by').not_.is_('referred_by', 'null').execute().data or []
        
        ref_counts = {}
        for r in all_refs:
            c = r.get('referred_by')
            ref_counts[c] = ref_counts.get(c, 0) + 1

        for u in users_res:
            c = ref_counts.get(u['referral_code'], 0)
            if c > 0:
                leaders.append({
                    'user_id': u['id'],
                    'name': u['name'],
                    'avatar_url': u.get('avatar_url'),
                    'referral_code': u['referral_code'],
                    'referral_count': c
                })
        leaders.sort(key=lambda x: x['referral_count'], reverse=True)
        leaders = leaders[:30]

    # ২. লগইন করা ইউজারের নিজস্ব পজিশন ও রেফার হিসাব
    if user_id:
        curr_user = sb.table('users').select('id, name, avatar_url, referral_code').eq('id', user_id).single().execute().data
        if curr_user:
            my_ref_count = len(sb.table('users').select('id').eq('referred_by', curr_user['referral_code']).execute().data or [])
            my_rank = "30+"
            for idx, item in enumerate(leaders):
                if item['user_id'] == user_id:
                    my_rank = f"#{idx + 1}"
                    break
            my_stats = {
                'name': curr_user['name'],
                'avatar_url': curr_user.get('avatar_url'),
                'referral_count': my_ref_count,
                'rank': my_rank
            }

    return render_template('leaderboard.html', leaders=leaders, my_stats=my_stats)
    
@app.route('/admin/gmail/<int:task_id>/approve', methods=['POST'])
@admin_required
def admin_gmail_approve(task_id):
    sb = get_supabase()
    task = sb.table('gmail_tasks').select('*').eq('id', task_id).single().execute().data
    if not task or task.get('status') != 'submitted':
        flash("অবৈধ টাস্ক!", "danger")
        return redirect(url_for('admin_gmail'))

    user = sb.table('users').select('balance').eq('id', task['locked_by']).single().execute().data
    new_bal = float(user['balance']) + float(task['price'])
    sb.table('users').update({'balance': new_bal}).eq('id', task['locked_by']).execute()
    sb.table('gmail_tasks').update({'status': 'completed'}).eq('id', task_id).execute()

    flash(f"জিমেইল অ্যাপ্রুভ হয়েছে এবং ইউজারের অ্যাকাউন্টে ৳{task['price']} যোগ হয়েছে!", "success")
    return redirect(url_for('admin_gmail'))

@app.route('/admin/sponsor')
@admin_required
def admin_sponsors():
    sb = get_supabase()
    all_sponsors = sb.table('sponsors').select('*').order('id', desc=True).execute().data or []
    pending_count = sum(1 for s in all_sponsors if s.get('status') == 'pending')
    approved_count = sum(1 for s in all_sponsors if s.get('status') == 'approved')

    return render_template(
        'admin/sponsor.html', 
        sponsors=all_sponsors,
        pending_count=pending_count,
        approved_count=approved_count
    )

@app.route('/admin/sponsor/<int:sponsor_id>/approve', methods=['POST'])
@admin_required
def admin_sponsor_approve(sponsor_id):
    sb = get_supabase()
    sb.table('sponsors').update({'status': 'approved'}).eq('id', sponsor_id).execute()
    flash("স্পনসরশিপ আবেদনটি সফলভাবে অনুমোদন (Approved) করা হয়েছে!", "success")
    return redirect(url_for('admin_sponsors'))

@app.route('/admin/sponsor/<int:sponsor_id>/reject', methods=['POST'])
@admin_required
def admin_sponsor_reject(sponsor_id):
    sb = get_supabase()
    sb.table('sponsors').update({'status': 'rejected'}).eq('id', sponsor_id).execute()
    flash("স্পনসরশিপ আবেদনটি রিজেক্ট করা হয়েছে!", "warning")
    return redirect(url_for('admin_sponsors'))

@app.route('/admin/sponsor/<int:sponsor_id>/delete', methods=['POST'])
@admin_required
def admin_sponsor_delete(sponsor_id):
    sb = get_supabase()
    sb.table('sponsors').delete().eq('id', sponsor_id).execute()
    flash("আবেদনটি ডাটাবেস থেকে মুছে ফেলা হয়েছে!", "success")
    return redirect(url_for('admin_sponsors'))
    
@app.route('/admin/gmail/<int:task_id>/reject', methods=['POST'])
@admin_required
def admin_gmail_reject(task_id):
    sb = get_supabase()
    sb.table('gmail_tasks').update({
        'status': 'available',
        'locked_by': None,
        'locked_at': None,
        'submitted_email': None,
        'submitted_at': None
    }).eq('id', task_id).execute()

    flash("টাস্কটি রিজেক্ট করা হয়েছে এবং পুনরায় সবার জন্য সাইটে লাইভ করে দেওয়া হয়েছে!", "warning")
    return redirect(url_for('admin_gmail'))

@app.route('/admin/gmail/<int:task_id>/delete', methods=['POST'])
@admin_required
def admin_gmail_delete(task_id):
    sb = get_supabase()
    sb.table('gmail_tasks').delete().eq('id', task_id).execute()
    flash("টাস্কটি ডিলিট করা হয়েছে!", "success")
    return redirect(url_for('admin_gmail'))

@app.route('/quiz')
@login_required
@kyc_required
def math_quiz():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    past_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    quizzes_done = sb.table('daily_activities').select('id') \
        .eq('user_id', user_id).eq('activity_type', 'quiz') \
        .gte('created_at', past_24h).execute().data or []

    remaining = max(0, 5 - len(quizzes_done))
    expr, ans, opts = generate_math_problem()
    session['quiz_answer'] = ans

    return render_template(
        'quiz.html', 
        user=user, 
        remaining=remaining, 
        question=expr, 
        options=opts
    )

@app.route('/quiz/submit', methods=['POST'])
@login_required
def quiz_submit():
    sb = get_supabase()
    user_id = session['user_id']
    data = request.get_json() or {}
    user_ans = data.get('answer')

    past_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    quizzes_done = sb.table('daily_activities').select('id') \
        .eq('user_id', user_id).eq('activity_type', 'quiz') \
        .gte('created_at', past_24h).execute().data or []

    if len(quizzes_done) >= 5:
        return jsonify({"success": False, "message": "আপনার আজকের ৫টি কুইজের সুযোগ শেষ! ২৪ ঘণ্টা পর আবার আসুন।", "remaining": 0})

    correct_ans = session.get('quiz_answer')
    if correct_ans is None:
        return jsonify({"success": False, "message": "প্রশ্নটি মেয়াদোত্তীর্ণ, রিফ্রেশ দিন!"})

    if str(user_ans).strip() == str(correct_ans):
        reward_pool = [3.00, 3.50, 4.00, 4.50, 5.00, 5.50, 6.00]
        reward = random.choice(reward_pool)

        user = sb.table('users').select('balance').eq('id', user_id).single().execute().data
        new_bal = float(user['balance']) + reward

        sb.table('users').update({'balance': new_bal}).eq('id', user_id).execute()
        sb.table('daily_activities').insert({
            'user_id': user_id,
            'activity_type': 'quiz',
            'reward_earned': reward
        }).execute()

        remaining = max(0, 5 - (len(quizzes_done) + 1))
        session.pop('quiz_answer', None)

        return jsonify({
            "success": True, 
            "correct": True, 
            "reward": reward, 
            "new_balance": new_bal, 
            "remaining": remaining,
            "message": f"🎉 দারুণ! সঠিক উত্তর। আপনি ৳{reward:.2f} জিতেছেন!"
        })
    else:
        session.pop('quiz_answer', None)
        remaining = max(0, 5 - len(quizzes_done))
        return jsonify({
            "success": True, 
            "correct": False, 
            "correct_ans": correct_ans,
            "remaining": remaining,
            "message": f"ভুল উত্তর! সঠিক উত্তর ছিল: {correct_ans}। টাকা যোগ হয়নি।"
        })

@app.route('/quiz/next', methods=['POST'])
@login_required
def quiz_next():
    expr, ans, opts = generate_math_problem()
    session['quiz_answer'] = ans
    return jsonify({"question": expr, "options": opts})

@app.route('/logout')
def logout():
    session.clear()
    flash("সফলভাবে লগআউট করা হয়েছে!", "info")
    return redirect(url_for('login'))

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    if request.method == 'POST':
        name = request.form.get('name', '').strip() or user['name']
        fb_link = request.form.get('fb_link', '').strip()
        tg_link = request.form.get('tg_link', '').strip()
        avatar_file = request.files.get('avatar')

        update_payload = {
            'name': name,
            'fb_link': fb_link if fb_link else None,
            'tg_link': tg_link if tg_link else None
        }

        if avatar_file and avatar_file.filename != '':
            img_url = upload_to_imgbb(avatar_file.read())
            if img_url:
                update_payload['avatar_url'] = img_url
            else:
                flash("ইমেজ আপলোড ফেইল হয়েছে, সার্ভার ব্যস্ত!", "danger")
                return redirect(url_for('account'))

        sb.table('users').update(update_payload).eq('id', user_id).execute()
        flash("প্রোফাইল তথ্য সফলভাবে আপডেট হয়েছে!", "success")
        return redirect(url_for('account'))

    ref_count = len(sb.table('users').select('id').eq('referred_by', user['referral_code']).execute().data or [])
    completed_tasks = len(sb.table('submissions').select('id').eq('user_id', user_id).eq('status', 'approved').execute().data or [])

    return render_template('account.html', user=user, ref_count=ref_count, completed_tasks=completed_tasks)

@app.route('/refer')
@login_required
def refer_page():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    referred_users = sb.table('users').select('name, email, created_at') \
        .eq('referred_by', user['referral_code']) \
        .order('id', desc=True).execute().data or []

    total_earned = len(referred_users) * 15.00

    return render_template(
        'refer.html',
        user=user,
        referred_users=referred_users,
        total_earned=total_earned
    ) 

@app.route('/app')
@login_required
def dashboard():
    sb = get_supabase()
    user = sb.table('users').select('*').eq('id', session['user_id']).single().execute().data
    
    notice_res = sb.table('settings').select('value').eq('key', 'site_notice').execute().data
    site_notice = notice_res[0]['value'] if notice_res else ""

    ref_count = len(sb.table('users').select('id').eq('referred_by', user['referral_code']).execute().data or [])
    
    return render_template(
        'dashboard.html', 
        user=user, 
        notice=site_notice, 
        referral_count=ref_count
    )

@app.route('/tasks')
@login_required
def tasks():
    sb = get_supabase()
    user_id = session['user_id']

    user_subs = sb.table('submissions').select('task_id, status').eq('user_id', user_id).execute().data or []
    hidden_task_ids = [s['task_id'] for s in user_subs if s['status'] in ['pending', 'approved']]

    all_tasks = sb.table('tasks').select('*').eq('is_active', True).order('id', desc=True).execute().data or []
    available_tasks = [t for t in all_tasks if t['id'] not in hidden_task_ids]

    return render_template('tasks.html', tasks=available_tasks)
    
@app.route('/task/<int:task_id>', methods=['GET', 'POST'])
@login_required
def task_detail(task_id):
    sb = get_supabase()
    task = sb.table('tasks').select('*').eq('id', task_id).single().execute().data
    if not task:
        flash("টাস্কটি খুঁজে পাওয়া যায়নি!", "danger")
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        file = request.files.get('screenshot')
        if not file or file.filename == '':
            flash("প্রমাণের স্ক্রিনশট সিলেক্ট করুন!", "danger")
            return redirect(request.url)

        img_url = upload_to_imgbb(file.read())
        if not img_url:
            flash("ইমেজ হোস্ট সার্ভার ব্যস্ত! অনুগ্রহ করে এডমিনকে জানান।", "danger")
            return redirect(request.url)

        sb.table('submissions').insert({
            'task_id': task_id,
            'user_id': session['user_id'],
            'proof_url': img_url,
            'status': 'pending'
        }).execute()

        flash("টাস্ক প্রুফ জমা হয়েছে! এডমিন রিভিউ শেষে টাকা যোগ হবে।", "success")
        return redirect(url_for('tasks'))

    return render_template('task_details.html', task=task)

@app.route('/spin', methods=['GET', 'POST'])
@login_required
def spin_page():
    sb = get_supabase()
    user_id = session['user_id']
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    spins_today = sb.table('daily_activities').select('id') \
        .eq('user_id', user_id).eq('activity_type', 'spin') \
        .gte('created_at', today_start).execute().data or []

    if request.method == 'POST':
        if len(spins_today) >= 3:
            return jsonify({
                "success": False, 
                "message": "আজকের ৩টি স্পিন সম্পন্ন হয়েছে! আগামীকাল আবার আসুন।", 
                "remaining": 0
            })

        slices = [0.50, 1.00, 1.50, 2.00, 3.00, 5.00]
        reward = random.choice(slices)

        user = sb.table('users').select('balance').eq('id', user_id).single().execute().data
        new_bal = float(user['balance']) + reward

        sb.table('users').update({'balance': new_bal}).eq('id', user_id).execute()
        sb.table('daily_activities').insert({
            'user_id': user_id, 
            'activity_type': 'spin', 
            'reward_earned': reward
        }).execute()

        remaining = max(0, 3 - (len(spins_today) + 1))
        
        return jsonify({
            "success": True, 
            "reward": reward, 
            "new_balance": new_bal, 
            "remaining": remaining
        })

    user = sb.table('users').select('*').eq('id', user_id).single().execute().data
    remaining_spins = max(0, 3 - len(spins_today))
    return render_template('spin.html', user=user, remaining=remaining_spins)

@app.route('/scratch', methods=['GET', 'POST'])
@login_required
def scratch_page():
    sb = get_supabase()
    user_id = session['user_id']
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    scratch_today = sb.table('daily_activities').select('id') \
        .eq('user_id', user_id).eq('activity_type', 'scratch') \
        .gte('created_at', today_start).execute().data or []

    if request.method == 'POST':
        if len(scratch_today) >= 3:
            return jsonify({
                "success": False, 
                "message": "আজকের ৩টি স্ক্র্যাচ ইতিমধ্যে শেষ হয়েছে! আগামীকাল আবার আসুন।",
                "remaining": 0
            })

        reward_pool = [1.00, 1.50, 2.00, 2.50, 3.00, 4.00, 5.00, 6.00]
        reward = random.choice(reward_pool)

        user = sb.table('users').select('balance').eq('id', user_id).single().execute().data
        new_bal = float(user['balance']) + reward

        sb.table('users').update({'balance': new_bal}).eq('id', user_id).execute()
        sb.table('daily_activities').insert({
            'user_id': user_id, 
            'activity_type': 'scratch', 
            'reward_earned': reward
        }).execute()

        remaining = max(0, 3 - (len(scratch_today) + 1))
        
        return jsonify({
            "success": True, 
            "reward": reward, 
            "new_balance": new_bal, 
            "remaining": remaining
        })

    user = sb.table('users').select('*').eq('id', user_id).single().execute().data
    remaining_scratch = max(0, 3 - len(scratch_today))
    return render_template('scratch.html', user=user, remaining=remaining_scratch)
    
@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data
    ref_count = len(sb.table('users').select('id').eq('referred_by', user['referral_code']).execute().data or [])

    if request.method == 'GET':
        return render_template('withdraw.html', user=user, referral_count=ref_count)
        
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0

    method = request.form.get('method', '').strip()
    account = request.form.get('account', '').strip()

    if amount < 500:
        flash("সর্বনিম্ন উইথড্রয়াল অ্যামাউন্ট 500 টাকা!", "danger")
        return redirect(url_for('withdraw'))

    if float(user['balance']) < amount:
        flash("আপনার অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স নেই!", "danger")
        return redirect(url_for('withdraw'))

    if ref_count < 5:
        flash(f"উইথড্র করতে সর্বনিম্ন 5টি রেফারেল প্রয়োজন! আপনার বর্তমান রেফারেল: {ref_count} টি।", "danger")
        return redirect(url_for('withdraw'))
        
    sb.table('users').update({'balance': float(user['balance']) - amount}).eq('id', user_id).execute()
    sb.table('withdrawals').insert({
        'user_id': user_id,
        'amount': amount,
        'method': method,
        'account_number': account,
        'status': 'pending'
    }).execute()

    flash("উইথড্রয়াল রিকোয়েস্ট সফলভাবে জমা হয়েছে!", "success")
    return redirect(url_for('dashboard'))

@app.route('/admin/task/<int:task_id>/edit', methods=['POST'])
@admin_required
def admin_task_edit(task_id):
    sb = get_supabase()
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    link = request.form.get('link', '').strip()
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0.0

    sb.table('tasks').update({
        'title': title,
        'description': description,
        'amount': amount,
        'link': link
    }).eq('id', task_id).execute()

    flash("টাস্কের তথ্য সফলভাবে আপডেট করা হয়েছে!", "success")
    return redirect(url_for('admin_task'))

@app.route('/admin/check')
@admin_required
def admin_user_check():
    sb = get_supabase()
    q = request.args.get('q', '').strip()
    
    target_user = None
    referrer = None
    referred_members = []
    task_subs = []
    withdrawals = []
    stats = {}

    if q:
        if q.isdigit():
            res = sb.table('users').select('*').eq('id', int(q)).execute().data
            if res: target_user = res[0]
            
        if not target_user:
            res = sb.table('users').select('*').eq('email', q.lower()).execute().data
            if res: target_user = res[0]
            
        if not target_user:
            res = sb.table('users').select('*').eq('referral_code', q.upper()).execute().data
            if res: target_user = res[0]

        if target_user:
            u_id = target_user['id']
            ref_code = target_user['referral_code']

            if target_user.get('referred_by'):
                ref_res = sb.table('users').select('id, name, email, referral_code').eq('referral_code', target_user['referred_by']).execute().data
                if ref_res: referrer = ref_res[0]

            referred_members = sb.table('users').select('id, name, email, balance, is_banned, created_at') \
                .eq('referred_by', ref_code).order('id', desc=True).execute().data or []

            task_subs = sb.table('submissions').select('*, tasks(title, amount)') \
                .eq('user_id', u_id).order('id', desc=True).execute().data or []

            withdrawals = sb.table('withdrawals').select('*') \
                .eq('user_id', u_id).order('id', desc=True).execute().data or []

            total_ref_balance = sum(float(m.get('balance', 0)) for m in referred_members)
            rejected_withdraws = sum(1 for w in withdrawals if w.get('status') == 'rejected')
            approved_withdraws = sum(1 for w in withdrawals if w.get('status') == 'approved')
            
            stats = {
                'total_ref_count': len(referred_members),
                'total_ref_balance': total_ref_balance,
                'rejected_withdraws': rejected_withdraws,
                'approved_withdraws': approved_withdraws,
                'total_tasks': len(task_subs),
                'approved_tasks': sum(1 for t in task_subs if t.get('status') == 'approved')
            }

    return render_template(
        'admin/check.html',
        q=q,
        user=target_user,
        referrer=referrer,
        referred_members=referred_members,
        task_subs=task_subs,
        withdrawals=withdrawals,
        stats=stats
    )
    
@app.route('/admin/task/<int:task_id>/delete', methods=['POST'])
@admin_required
def admin_task_delete(task_id):
    sb = get_supabase()
    sb.table('tasks').delete().eq('id', task_id).execute()
    flash("টাস্কটি স্থায়ীভাবে মুছে ফেলা হয়েছে!", "success")
    return redirect(url_for('admin_task'))

# ==========================================================
# USER FINANCIAL HISTORY & STATEMENT CONTROLLER (/history)
# ==========================================================
@app.route('/history')
@login_required
def history():
    sb = get_supabase()
    user_id = session['user_id']
    user = sb.table('users').select('*').eq('id', user_id).single().execute().data

    # ১. উইথড্রয়াল হিস্ট্রি
    withdrawals = sb.table('withdrawals').select('*') \
        .eq('user_id', user_id).order('id', desc=True).execute().data or []

    # ২. টাস্ক সাবমিশন হিস্ট্রি
    task_subs = sb.table('submissions').select('*, tasks(title, amount)') \
        .eq('user_id', user_id).order('id', desc=True).execute().data or []

    # ৩. গেম ও দৈনিক বোনাস হিস্ট্রি (স্পিন, স্ক্র্যাচ, কুইজ)
    daily_acts = sb.table('daily_activities').select('*') \
        .eq('user_id', user_id).order('id', desc=True).limit(50).execute().data or []

    # ৪. রেফারেল হিস্ট্রি
    referrals = sb.table('users').select('name, email, created_at') \
        .eq('referred_by', user.get('referral_code', '')) \
        .order('id', desc=True).limit(50).execute().data or []

    # ৫. ফাইন্যান্সিয়াল সামারি হিসাব
    total_withdrawn = sum(float(w['amount']) for w in withdrawals if w.get('status') == 'approved')
    pending_withdrawals = sum(float(w['amount']) for w in withdrawals if w.get('status') == 'pending')
    total_task_earned = sum(float(t['tasks']['amount']) for t in task_subs if t.get('status') == 'approved' and t.get('tasks'))
    total_games_earned = sum(float(d.get('reward_earned', 0)) for d in daily_acts)

    summary = {
        'total_withdrawn': total_withdrawn,
        'pending_withdrawals': pending_withdrawals,
        'total_task_earned': total_task_earned,
        'total_games_earned': total_games_earned
    }

    return render_template(
        'history.html', 
        user=user, 
        withdrawals=withdrawals,
        task_subs=task_subs, 
        daily_acts=daily_acts,
        referrals=referrals,
        summary=summary
    )
    
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' not in session:
        flash("প্রথমে admin@gmail.com দিয়ে লগইন করুন!", "danger")
        return redirect(url_for('index'))

    sb = get_supabase()
    user = sb.table('users').select('email').eq('id', session['user_id']).single().execute().data
    if not user or user.get('email') != 'admin@gmail.com':
        flash("শুধুমাত্র প্রধান অ্যাডমিন (admin@gmail.com) এর জন্য সংরক্ষিত!", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        secret = request.form.get('admin_key', '')
        if secret == ADMIN_SECRET_PASS:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash("ভুল অ্যাডমিন সিক্রেট কি!", "danger")

    return render_template('admin/login.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    sb = get_supabase()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    try:
        total_res = sb.table('users').select('id', count='exact').execute()
        total_users = total_res.count if total_res.count is not None else len(total_res.data or [])

        today_res = sb.table('users').select('id', count='exact').gte('created_at', today_start).execute()
        today_users = today_res.count if today_res.count is not None else len(today_res.data or [])

        yest_res = sb.table('users').select('id', count='exact').gte('created_at', yesterday_start).lt('created_at', today_start).execute()
        yesterday_users = yest_res.count if yest_res.count is not None else len(yest_res.data or [])

        sub_res = sb.table('submissions').select('id', count='exact').gte('created_at', today_start).execute()
        today_submissions = sub_res.count if sub_res.count is not None else len(sub_res.data or [])
    except Exception:
        total_users = len(sb.table('users').select('id').execute().data or [])
        today_users = len(sb.table('users').select('id').gte('created_at', today_start).execute().data or [])
        yesterday_users = len(sb.table('users').select('id').gte('created_at', yesterday_start).lt('created_at', today_start).execute().data or [])
        today_submissions = len(sb.table('submissions').select('id').gte('created_at', today_start).execute().data or [])

    notice_res = sb.table('settings').select('value').eq('key', 'site_notice').execute().data
    current_notice = notice_res[0]['value'] if notice_res else ""

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        today_users=today_users,
        yesterday_users=yesterday_users,
        today_submissions=today_submissions,
        notice=current_notice
    )
    
@app.context_processor
def inject_global_user():
    if 'user_id' in session:
        sb = get_supabase()
        u = sb.table('users').select('id, name, balance, avatar_url, referral_code') \
            .eq('id', session['user_id']).single().execute().data
        return dict(current_user=u)
    return dict(current_user=None)

@app.route('/allwork')
@login_required
def all_work():
    return render_template('allwork.html')
    
@app.route('/admin/notice', methods=['POST'])
@admin_required
def admin_update_notice():
    sb = get_supabase()
    new_notice = request.form.get('site_notice', '').strip()
    sb.table('settings').upsert({'key': 'site_notice', 'value': new_notice}).execute()
    flash("সাইট নোটিশ সফলভাবে আপডেট হয়েছে!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/users')
@admin_required
def admin_users():
    sb = get_supabase()
    page = int(request.args.get('page', 1))
    search = request.args.get('q', '').strip()
    limit = 20
    offset = (page - 1) * limit

    query = sb.table('users').select('*')
    if search:
        query = query.ilike('email', f"%{search}%")

    users_list = query.order('id', desc=True).range(offset, offset + limit - 1).execute().data or []
    return render_template('admin/users.html', users=users_list, page=page, search=search)

@app.route('/admin/user/<int:user_id>/ban', methods=['POST'])
@admin_required
def admin_toggle_ban(user_id):
    sb = get_supabase()
    user = sb.table('users').select('is_banned').eq('id', user_id).single().execute().data
    if user:
        sb.table('users').update({'is_banned': not user['is_banned']}).eq('id', user_id).execute()
        flash("ইউজার স্ট্যাটাস পরিবর্তন করা হয়েছে।", "success")
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/balance', methods=['POST'])
@admin_required
def admin_modify_balance(user_id):
    sb = get_supabase()
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        amount = 0
        
    user = sb.table('users').select('balance').eq('id', user_id).single().execute().data
    if user:
        new_balance = float(user['balance']) + amount
        sb.table('users').update({'balance': new_balance}).eq('id', user_id).execute()
        flash("ব্যালেন্স আপডেট সফল হয়েছে!", "success")
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    sb = get_supabase()
    sb.table('users').delete().eq('id', user_id).execute()
    flash("ইউজার ডিলিট করা হয়েছে!", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/withdraw')
@admin_required
def admin_withdraw():
    sb = get_supabase()
    reqs = sb.table('withdrawals').select('*, users(email, balance)').eq('status', 'pending').order('id', desc=True).execute().data or []

    for r in reqs:
        rej_count = len(sb.table('withdrawals').select('id').eq('user_id', r['user_id']).eq('status', 'rejected').execute().data or [])
        r['rejection_count'] = rej_count

    return render_template('admin/withdraw.html', requests=reqs)

@app.route('/admin/withdraw/<int:withdraw_id>/<action>', methods=['POST'])
@admin_required
def admin_handle_withdraw(withdraw_id, action):
    sb = get_supabase()
    req = sb.table('withdrawals').select('*').eq('id', withdraw_id).single().execute().data
    if not req or req['status'] != 'pending':
        flash("অবৈধ রিকোয়েস্ট!", "danger")
        return redirect(url_for('admin_withdraw'))

    if action == 'approve':
        sb.table('withdrawals').update({'status': 'approved'}).eq('id', withdraw_id).execute()
        flash("উইথড্রয়াল অ্যাপ্রুভ হয়েছে!", "success")
    elif action == 'reject':
        user = sb.table('users').select('balance').eq('id', req['user_id']).single().execute().data
        sb.table('users').update({'balance': float(user['balance']) + float(req['amount'])}).eq('id', req['user_id']).execute()
        sb.table('withdrawals').update({'status': 'rejected'}).eq('id', withdraw_id).execute()
        flash("উইথড্রয়াল রিজেক্ট করা হয়েছে এবং টাকা ফেরত দেওয়া হয়েছে।", "warning")

    return redirect(url_for('admin_withdraw'))

@app.route('/admin/imgbb', methods=['GET', 'POST'])
@admin_required
def admin_imgbb():
    sb = get_supabase()
    if request.method == 'POST':
        key = request.form.get('api_key', '').strip()
        if key:
            sb.table('imgbb_keys').insert({'api_key': key}).execute()
            flash("ImgBB Key সফলভাবে যুক্ত হয়েছে!", "success")
        return redirect(url_for('admin_imgbb'))

    keys = sb.table('imgbb_keys').select('*').order('id', desc=True).execute().data or []
    return render_template('admin/imgbb.html', keys=keys)

@app.route('/admin/imgbb/delete/<int:key_id>', methods=['POST'])
@admin_required
def admin_imgbb_delete(key_id):
    sb = get_supabase()
    sb.table('imgbb_keys').delete().eq('id', key_id).execute()
    flash("API Key ডিলিট করা হয়েছে!", "success")
    return redirect(url_for('admin_imgbb'))

@app.route('/admin/pay')
@admin_required
def admin_pay_generator():
    return render_template('admin/pay.html')
    
@app.route('/admin/task', methods=['GET', 'POST'])
@admin_required
def admin_task():
    sb = get_supabase()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        amount = float(request.form.get('amount', 0))
        link = request.form.get('link', '').strip()

        sb.table('tasks').insert({
            'title': title,
            'description': description,
            'amount': amount,
            'link': link
        }).execute()
        flash("নতুন টাস্ক তৈরি হয়েছে!", "success")
        return redirect(url_for('admin_task'))

    all_tasks = sb.table('tasks').select('*').order('id', desc=True).execute().data or []
    return render_template('admin/tasks.html', tasks=all_tasks)

@app.route('/admin/submit')
@admin_required
def admin_submissions():
    sb = get_supabase()
    pending = sb.table('submissions').select('*, tasks(title, amount), users(email)').eq('status', 'pending').order('id', desc=True).execute().data or []
    return render_template('admin/submissions.html', submissions=pending)

@app.route('/admin/submit/bulk', methods=['POST'])
@admin_required
def admin_bulk_submissions():
    sb = get_supabase()
    pending = sb.table('submissions').select('*, tasks(amount)').eq('status', 'pending').limit(30).execute().data or []
    
    if not pending:
        flash("কোনো পেন্ডিং টাস্ক নেই।", "info")
        return redirect(url_for('admin_submissions'))

    reject_count = min(3, len(pending))
    rejected_items = random.sample(pending, reject_count)
    rejected_ids = [item['id'] for item in rejected_items]

    approved_count = 0
    for item in pending:
        if item['id'] in rejected_ids:
            sb.table('submissions').update({'status': 'rejected'}).eq('id', item['id']).execute()
        else:
            sb.table('submissions').update({'status': 'approved'}).eq('id', item['id']).execute()
            user = sb.table('users').select('balance').eq('id', item['user_id']).single().execute().data
            reward = float(item['tasks']['amount']) if item.get('tasks') else 0.0
            sb.table('users').update({'balance': float(user['balance']) + reward}).eq('id', item['user_id']).execute()
            approved_count += 1

    flash(f"বাল্ক রিভিউ শেষ! {approved_count}টি অ্যাপ্রুভ এবং {reject_count}টি র‍্যান্ডমলি রিজেক্ট হয়েছে।", "success")
    return redirect(url_for('admin_submissions'))

@app.route('/yt')
@login_required
def yt_videos():
    sb = get_supabase()
    user_id = session['user_id']
    page = int(request.args.get('page', 1))
    limit = 20
    offset = (page - 1) * limit

    claimed_rows = sb.table('yt_claims').select('video_id').eq('user_id', user_id).execute().data or []
    claimed_ids = set(c['video_id'] for c in claimed_rows)

    all_videos = sb.table('yt_videos').select('*').eq('is_active', True).order('id', desc=True).execute().data or []
    available_videos = [v for v in all_videos if v['id'] not in claimed_ids]

    total_available = len(available_videos)
    paginated_videos = available_videos[offset : offset + limit]
    has_next = (offset + limit) < total_available

    return render_template(
        'yt.html', 
        videos=paginated_videos, 
        page=page, 
        has_next=has_next,
        total_available=total_available
    )

@app.route('/yt/claim', methods=['POST'])
@login_required
def yt_claim():
    sb = get_supabase()
    user_id = session['user_id']
    data = request.get_json() or {}
    video_id = data.get('video_id')

    if not video_id:
        return jsonify({'success': False, 'message': 'অবৈধ ভিডিও আইডি!'})

    already_seen = sb.table('yt_claims').select('id').eq('user_id', user_id).eq('video_id', video_id).execute().data
    if already_seen:
        return jsonify({
            'success': False, 
            'message': 'আপনি এই ভিডিওটি ইতিমধ্যে দেখে ফেলেছেন! এটি দ্বিতীয়বার দেখা যাবে না।'
        })

    video = sb.table('yt_videos').select('*').eq('id', video_id).single().execute().data
    if not video or not video.get('is_active'):
        return jsonify({'success': False, 'message': 'ভিডিওটি পাওয়া যায়নি বা নিষ্ক্রিয় রয়েছে!'})

    amount = float(video['amount'])
    user = sb.table('users').select('balance').eq('id', user_id).single().execute().data
    new_balance = float(user['balance']) + amount

    sb.table('users').update({'balance': new_balance}).eq('id', user_id).execute()
    sb.table('yt_claims').insert({
        'video_id': video_id,
        'user_id': user_id,
        'amount_earned': amount
    }).execute()

    return jsonify({
        'success': True,
        'message': f'🎉 অভিনন্দন! আপনি ৳{amount:.2f} সফলভাবে ক্লেইম করেছেন!',
        'new_balance': new_balance
    })

@app.route('/admin/yt', methods=['GET', 'POST'])
@admin_required
def admin_yt():
    sb = get_supabase()
    if request.method == 'POST':
        raw_url = request.form.get('video_url', '').strip()
        title = request.form.get('title', '').strip() or 'YouTube Video'
        try:
            amount = float(request.form.get('amount', 1.00))
        except ValueError:
            amount = 1.00

        vid = extract_yt_id(raw_url)
        if not vid:
            flash("ইউটিউব লিংক সঠিক নয়! (যেমন: https://youtu.be/... বা watch?v=... দিন)", "danger")
            return redirect(url_for('admin_yt'))

        sb.table('yt_videos').insert({
            'video_url': raw_url,
            'video_id': vid,
            'title': title,
            'amount': amount
        }).execute()

        flash("নতুন YouTube ভিডিও সফলভাবে যুক্ত হয়েছে!", "success")
        return redirect(url_for('admin_yt'))

    videos = sb.table('yt_videos').select('*').order('id', desc=True).execute().data or []
    return render_template('admin/yt.html', videos=videos)

@app.route('/admin/yt/delete/<int:video_id>', methods=['POST'])
@admin_required
def admin_yt_delete(video_id):
    sb = get_supabase()
    sb.table('yt_videos').delete().eq('id', video_id).execute()
    flash("ভিডিওটি সফলভাবে ডিলিট করা হয়েছে!", "success")
    return redirect(url_for('admin_yt'))

@app.route('/promote', methods=['GET', 'POST'])
def promote():
    sb = get_supabase()
    user = None
    is_logged_in = 'user_id' in session

    if is_logged_in:
        user = sb.table('users').select('*').eq('id', session['user_id']).single().execute().data

    if request.method == 'POST':
        if not is_logged_in:
            flash("প্রমোশন ফর্ম জমা দিতে অনুগ্রহ করে প্রথমে লগইন করুন!", "danger")
            return redirect(url_for('index'))

        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        service_type = request.form.get('service_type', 'General').strip()
        requirement = request.form.get('requirement', '').strip()

        if not name or not email or not phone or not requirement:
            flash("ফর্মের সবকটি তথ্য সঠিকভাবে পূরণ করুন!", "danger")
            return redirect(url_for('promote'))

        sb.table('promotions').insert({
            'user_id': session['user_id'],
            'name': name,
            'email': email,
            'phone': phone,
            'service_type': service_type,
            'requirement': requirement
        }).execute()

        flash("🎉 আপনার রিকোয়েস্ট সফলভাবে জমা হয়েছে! আমাদের টিম দ্রুতই আপনার সাথে যোগাযোগ করবে।", "success")
        return redirect(url_for('promote'))

    return render_template('promote.html', is_logged_in=is_logged_in, user=user)

@app.route('/admin/submit/<int:sub_id>/approve', methods=['POST'])
@admin_required
def admin_single_approve_submission(sub_id):
    sb = get_supabase()
    sub = sb.table('submissions').select('*, tasks(amount)').eq('id', sub_id).single().execute().data
    
    if not sub or sub.get('status') != 'pending':
        flash("অবৈধ বা ইতিমধ্যে সম্পন্ন হওয়া সাবমিশন!", "danger")
        return redirect(url_for('admin_submissions'))

    sb.table('submissions').update({'status': 'approved'}).eq('id', sub_id).execute()

    user = sb.table('users').select('balance').eq('id', sub['user_id']).single().execute().data
    task_amount = float(sub['tasks']['amount']) if sub.get('tasks') else 0.0
    new_balance = float(user['balance']) + task_amount

    sb.table('users').update({'balance': new_balance}).eq('id', sub['user_id']).execute()

    flash(f"টাস্কটি সফলভাবে অ্যাপ্রুভ করা হয়েছে এবং ইউজারের অ্যাকাউন্টে ৳{task_amount:.2f} যোগ হয়েছে!", "success")
    return redirect(url_for('admin_submissions'))

@app.route('/admin/submit/<int:sub_id>/reject', methods=['POST'])
@admin_required
def admin_single_reject_submission(sub_id):
    sb = get_supabase()
    sub = sb.table('submissions').select('id, status').eq('id', sub_id).single().execute().data
    
    if not sub or sub.get('status') != 'pending':
        flash("অবৈধ বা ইতিমধ্যে সম্পন্ন হওয়া সাবমিশন!", "danger")
        return redirect(url_for('admin_submissions'))

    sb.table('submissions').update({'status': 'rejected'}).eq('id', sub_id).execute()
    flash("টাস্কটি রিজেক্ট করা হয়েছে!", "warning")
    return redirect(url_for('admin_submissions'))
    
# ==========================================================
# PWA MANIFEST & SERVICE WORKER CONTROLLER
# ==========================================================
@app.route('/manifest.json')
def pwa_manifest():
    logo_url = "https://i.ibb.co.com/1wxLMwW/IMG-20261104-WA0022.jpg"
    manifest_data = {
        "id": "/",
        "name": "TaskWallet - Minimal Fintech & Earning",
        "short_name": "TaskWallet",
        "description": "TaskWallet Micro Task & Earning Platform",
        "start_url": "/app",
        "scope": "/",
        "display": "standalone",
        "background_color": "#04060b",
        "theme_color": "#04060b",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": logo_url,
                "sizes": "192x192",
                "type": "image/jpeg",
                "purpose": "any"
            },
            {
                "src": logo_url,
                "sizes": "512x512",
                "type": "image/jpeg",
                "purpose": "any"
            },
            {
                "src": logo_url,
                "sizes": "512x512",
                "type": "image/jpeg",
                "purpose": "maskable"
            }
        ]
    }
    response = jsonify(manifest_data)
    response.headers['Content-Type'] = 'application/manifest+json; charset=utf-8'
    return response

@app.route('/sw.js')
def pwa_sw():
    sw_code = """
    const CACHE_NAME = 'taskwallet-cache-v1';
    self.addEventListener('install', (e) => {
        self.skipWaiting();
    });
    self.addEventListener('activate', (e) => {
        e.waitUntil(clients.claim());
    });
    self.addEventListener('fetch', (e) => {
        e.respondWith(
            fetch(e.request).catch(() => caches.match(e.request))
        );
    });
    """
    response = app.response_class(sw_code, mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    return response
@app.route('/install')
def install_app_page():
    return render_template('install.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
