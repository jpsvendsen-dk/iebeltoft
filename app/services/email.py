import os
import logging
import httpx

logger = logging.getLogger(__name__)


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
