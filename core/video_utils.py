"""Built-in WebRTC room and IST slot time-window helpers for MediCate video consultations."""
from datetime import datetime, timedelta
import secrets
from zoneinfo import ZoneInfo
from django.utils import timezone

IST = ZoneInfo('Asia/Kolkata')


def get_appointment_window(appointment):
    """
    Compute timezone-aware Asia/Kolkata bounds for an Appointment's slot.
    For video consultations:
      - Join window: 5 minutes before slot start until 5 minutes after slot start.
      - Room/session expiry: 15 minutes after slot end so calls running slightly
        over are not cut off abruptly.
    """
    slot = appointment.slot
    start_dt = datetime.combine(slot.date, slot.start_time, tzinfo=IST)
    end_dt = datetime.combine(slot.date, slot.end_time, tzinfo=IST)
    default_mins = 10 if appointment.appointment_type == 'video' else 30
    if end_dt == start_dt:
        end_dt = start_dt + timedelta(minutes=default_mins)
    elif end_dt < start_dt:
        end_dt += timedelta(days=1)

    if appointment.appointment_type == 'video':
        window_open = start_dt - timedelta(minutes=5)
        window_close = start_dt + timedelta(minutes=5)
        room_expiry = end_dt + timedelta(minutes=15)
    else:
        window_open = start_dt - timedelta(minutes=10)
        window_close = end_dt + timedelta(minutes=60)
        room_expiry = window_close

    now = timezone.now().astimezone(IST)
    is_open = window_open <= now <= window_close
    is_session_active = window_open <= now <= room_expiry

    return {
        'slot_start': start_dt,
        'slot_end': end_dt,
        'window_open': window_open,
        'window_close': window_close,
        'room_expiry': room_expiry,
        'is_open': is_open,
        'is_session_active': is_session_active,
        'is_before': now < window_open,
        'is_after': now > window_close,
        'slot_seconds_remaining': max(0, int((end_dt - now).total_seconds())),
        'cutoff_seconds_remaining': max(0, int((room_expiry - now).total_seconds())),
        'slot_end_label': end_dt.strftime('%I:%M %p IST').lstrip('0'),
        'room_expiry_label': room_expiry.strftime('%I:%M %p IST').lstrip('0'),
        'window_label': (
            f"Join {window_open.strftime('%d %b %Y, %I:%M %p')} – "
            f"{window_close.strftime('%I:%M %p IST')}"
        ),
    }


def ensure_video_room(appointment):
    """
    Ensure each video appointment has its own dedicated room identifier
    stored on Appointment.video_room_name (no external API or billing required).
    """
    if not appointment.video_room_name or not appointment.video_room_name.startswith('medicate-'):
        appointment.video_room_name = f"medicate-{appointment.id}-{secrets.token_hex(4)}"
        appointment.video_room_url = f"/appointments/{appointment.id}/video/"
        appointment.save(update_fields=['video_room_name', 'video_room_url'])
    return appointment.video_room_name
