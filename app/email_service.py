"""
email_service.py — Gmail SMTP email sender
Uses Python's built-in smtplib — no new packages needed.

Setup required (one-time):
  1. Go to myaccount.google.com → Security → 2-Step Verification → ON
  2. Then: myaccount.google.com → Security → App Passwords
  3. Generate password for "Mail" → copy the 16-char password
  4. Set env vars: GMAIL_ADDRESS and GMAIL_APP_PASSWORD

On Render: add both as environment variables in your service settings.
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


GMAIL_ADDRESS  = os.environ.get("GMAIL_ADDRESS", "professionaldevanshsharma@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # App password, not your Gmail password


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """
    Core send function. Returns True if sent, False if failed.
    Never raises — email failure should never crash the signup flow.
    """
    if not GMAIL_PASSWORD:
        print(f"[Email] GMAIL_APP_PASSWORD not set — skipping email to {to_email}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"Revenue Intelligence <{GMAIL_ADDRESS}>"
        msg["To"]      = to_email

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())

        print(f"[Email] Sent '{subject}' to {to_email}")
        return True

    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str) -> bool:
    """
    Sent immediately after successful signup.
    Confirms account creation and links to login.
    """
    subject = "Welcome to Revenue Intelligence 📊"
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#0f1117;font-family:'Segoe UI',Arial,sans-serif;">

  <div style="max-width:560px;margin:40px auto;background:#1a1d2e;border-radius:16px;overflow:hidden;border:1px solid #2a2d3e;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#7c3aed,#db2777);padding:32px;text-align:center;">
      <div style="font-size:36px;margin-bottom:8px;">📊</div>
      <h1 style="color:#fff;font-size:22px;font-weight:800;margin:0;">Revenue Intelligence</h1>
      <p style="color:rgba(255,255,255,0.8);font-size:14px;margin:6px 0 0;">Your AI-powered sales analyst</p>
    </div>

    <!-- Body -->
    <div style="padding:36px 40px;">
      <h2 style="color:#e2e8f0;font-size:20px;font-weight:700;margin:0 0 12px;">
        Welcome aboard! 🎉
      </h2>
      <p style="color:#9ca3af;font-size:15px;line-height:1.6;margin:0 0 24px;">
        Your account has been created successfully. You're one step away from getting
        AI-powered insights on your sales data.
      </p>

      <!-- What you get -->
      <div style="background:#0f1117;border-radius:10px;padding:20px;margin-bottom:28px;">
        <p style="color:#a78bfa;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin:0 0 14px;">
          What you get
        </p>
        <div style="color:#c4cad6;font-size:14px;line-height:1.8;">
          ✓ &nbsp;Revenue analysis by state &amp; category<br>
          ✓ &nbsp;AI-generated founder-ready action plan<br>
          ✓ &nbsp;Fulfillment gap detection<br>
          ✓ &nbsp;Market expansion opportunity map<br>
          ✓ &nbsp;Works with any CSV — Amazon, Flipkart, Shopify
        </div>
      </div>

      <!-- CTA -->
      <div style="text-align:center;margin-bottom:28px;">
        <a href="https://data-driven-profitability-and-market.onrender.com/pricing"
           style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#9333ea);
                  color:#fff;text-decoration:none;padding:14px 36px;border-radius:10px;
                  font-size:15px;font-weight:700;">
          View Plans &amp; Get Started →
        </a>
      </div>

      <p style="color:#6b7280;font-size:13px;line-height:1.6;margin:0;">
        Already have a plan? 
        <a href="https://data-driven-profitability-and-market.onrender.com/login"
           style="color:#a78bfa;text-decoration:none;">Log in here</a>
        and upload your first CSV.
      </p>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid #2a2d3e;padding:20px 40px;text-align:center;">
      <p style="color:#4b5563;font-size:12px;margin:0;">
        © 2025 Revenue Intelligence · Built for Indian D2C founders<br>
        Questions? Reply to this email.
      </p>
    </div>

  </div>

</body>
</html>"""
    return _send(to_email, subject, html)


def send_payment_confirmation(to_email: str, plan: str, end_date: str) -> bool:
    """
    Sent after successful Razorpay payment + subscription activation.
    Confirms plan, access duration, and links to upload page.
    """
    plan_label  = "Monthly Plan" if plan == "monthly" else "6-Month Plan"
    plan_amount = "₹2,000" if plan == "monthly" else "₹10,000"

    subject = f"Payment confirmed — {plan_label} activated 🎉"
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:'Segoe UI',Arial,sans-serif;">

  <div style="max-width:560px;margin:40px auto;background:#1a1d2e;border-radius:16px;overflow:hidden;border:1px solid #2a2d3e;">

    <div style="background:linear-gradient(135deg,#7c3aed,#db2777);padding:32px;text-align:center;">
      <div style="font-size:36px;margin-bottom:8px;">✅</div>
      <h1 style="color:#fff;font-size:22px;font-weight:800;margin:0;">Payment Confirmed</h1>
      <p style="color:rgba(255,255,255,0.8);font-size:14px;margin:6px 0 0;">Revenue Intelligence</p>
    </div>

    <div style="padding:36px 40px;">
      <h2 style="color:#e2e8f0;font-size:20px;font-weight:700;margin:0 0 20px;">
        Your subscription is active 🚀
      </h2>

      <!-- Plan details -->
      <div style="background:#0f1117;border-radius:10px;padding:20px;margin-bottom:28px;">
        <table style="width:100%;border-collapse:collapse;">
          <tr>
            <td style="color:#6b7280;font-size:13px;padding:6px 0;">Plan</td>
            <td style="color:#e2e8f0;font-size:13px;font-weight:600;text-align:right;">{plan_label}</td>
          </tr>
          <tr>
            <td style="color:#6b7280;font-size:13px;padding:6px 0;">Amount paid</td>
            <td style="color:#34d399;font-size:13px;font-weight:700;text-align:right;">{plan_amount}</td>
          </tr>
          <tr>
            <td style="color:#6b7280;font-size:13px;padding:6px 0;">Access until</td>
            <td style="color:#a78bfa;font-size:13px;font-weight:600;text-align:right;">{end_date}</td>
          </tr>
        </table>
      </div>

      <div style="text-align:center;margin-bottom:28px;">
        <a href="https://data-driven-profitability-and-market.onrender.com/upload"
           style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#9333ea);
                  color:#fff;text-decoration:none;padding:14px 36px;border-radius:10px;
                  font-size:15px;font-weight:700;">
          Upload Your First CSV →
        </a>
      </div>

      <p style="color:#6b7280;font-size:13px;line-height:1.6;margin:0;">
        Need help? Just reply to this email — we respond within 24 hours.
      </p>
    </div>

    <div style="border-top:1px solid #2a2d3e;padding:20px 40px;text-align:center;">
      <p style="color:#4b5563;font-size:12px;margin:0;">
        © 2025 Revenue Intelligence · Built for Indian D2C founders
      </p>
    </div>

  </div>

</body>
</html>"""
    return _send(to_email, subject, html)