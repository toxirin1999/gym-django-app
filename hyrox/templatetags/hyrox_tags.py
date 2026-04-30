from django import template

register = template.Library()


@register.filter
def fmt_diff_secs(secs):
    """Formatea una diferencia de segundos como '+3:47' o '-1:20'."""
    if secs is None:
        return ''
    try:
        secs = int(secs)
        sign = '+' if secs >= 0 else '-'
        abs_s = abs(secs)
        m, s = divmod(abs_s, 60)
        return f"{sign}{m}:{s:02d}"
    except (TypeError, ValueError):
        return ''
