import os
import logging
import httpx

logger = logging.getLogger(__name__)


def send_calendar_login(email: str, login_url: str) -> bool:
    """Send the requested one-time link; never log recipients or link tokens."""
    from html import escape
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        return False
    text = f"Log ind på Jul på torvet:\n\n{login_url}\n\nLinket gælder i 15 minutter og kan kun bruges én gang.\nPå en ny enhed kan du bestille et nyt link med samme e-mailadresse.\nHvis du ikke har bedt om linket, kan du ignorere denne mail."
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": os.getenv("CHRISTMAS_MAIL_FROM", "Jul på torvet <noreply@iebeltoft.dk>"),
                "to": [email],
                "subject": "Dit loginlink til Jul på torvet",
                "text": text,
                "html": f'<div style="font-family:Georgia,serif;max-width:520px;margin:auto;padding:30px;background:#f9f2e4;color:#263b35"><h1>Jul på torvet</h1><p>Gem dine juleøjeblikke, og tag dem med fra mobil til computer.</p><p><a href="{escape(login_url, quote=True)}" style="display:inline-block;background:#7d322d;color:#fff;padding:14px 22px;border-radius:5px">Åbn min julekalender</a></p><p>Bekræft login på siden. Linket gælder i 15 minutter og kan bruges én gang.</p><p>Hvis du ikke har bedt om linket, kan du ignorere denne mail.</p></div>',
            },
            timeout=10,
        )
        if response.status_code in (200, 201):
            return True
        logger.warning("Kalenderlogin: mailtjenesten svarede med status %s", response.status_code)
    except httpx.HTTPError:
        logger.warning("Kalenderlogin: mailtjenesten kunne ikke kontaktes")
    return False


def send_booking_notification(booking, admin_email: str) -> bool:
    """
    Sender e-mail til admin ved ny bookingforespørgsel.
    Returnerer True hvis mailen blev sendt, False ellers.
    Fejler lydløst — krasjer ikke appen.
    """
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key or not admin_email:
        logger.warning("E-mail ikke sendt: RESEND_API_KEY eller admin_email mangler.")
        return False

    naetter = (booking.check_out - booking.check_in).days
    adresse = ""
    if booking.guest_address:
        adresse = f"{booking.guest_address}, {booking.guest_zip} {booking.guest_city}"

    body_html = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1d4ed8;">Ny bookingforespørgsel — iebeltoft.dk</h2>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
            <tr><td style="padding:6px 0; color:#666;">Navn</td>
                <td style="padding:6px 0; font-weight:bold;">{booking.guest_name}</td></tr>
            <tr><td style="padding:6px 0; color:#666;">E-mail</td>
                <td style="padding:6px 0;">{booking.guest_email}</td></tr>
            <tr><td style="padding:6px 0; color:#666;">Telefon</td>
                <td style="padding:6px 0;">{booking.guest_phone or "—"}</td></tr>
            <tr><td style="padding:6px 0; color:#666;">Adresse</td>
                <td style="padding:6px 0;">{adresse or "—"}</td></tr>
            <tr><td colspan="2" style="padding-top:12px;"></td></tr>
            <tr><td style="padding:6px 0; color:#666;">Ankomst</td>
                <td style="padding:6px 0; font-weight:bold;">{booking.check_in.strftime("%d.%m.%Y")}</td></tr>
            <tr><td style="padding:6px 0; color:#666;">Afrejse</td>
                <td style="padding:6px 0; font-weight:bold;">{booking.check_out.strftime("%d.%m.%Y")}</td></tr>
            <tr><td style="padding:6px 0; color:#666;">Antal nætter</td>
                <td style="padding:6px 0;">{naetter}</td></tr>
            <tr><td style="padding:6px 0; color:#666;">Pris (leje)</td>
                <td style="padding:6px 0;">{int(booking.total_price):,} kr.".replace(",", ".")</td></tr>
        </table>
        {"<p><strong>Bemærkninger:</strong><br>" + booking.guest_remarks + "</p>" if booking.guest_remarks else ""}
        <hr style="margin:20px 0;">
        <p style="font-size:12px; color:#999;">
            Se og håndter bookingen på
            <a href="https://iebeltoft.dk/admin/bookinger">admin-panelet</a>.
            Booking-id: #{booking.id}
        </p>
    </div>
    """

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": "noreply@iebeltoft.dk",
                "to": [admin_email],
                "subject": f"Ny forespørgsel — {booking.guest_name} ({booking.check_in.strftime('%d.%m.%Y')})",
                "html": body_html,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.error(f"Resend fejl {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"E-mail afsendelse fejlede: {e}")
        return False
