from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key)


register = template.Library()


@register.filter
def make_range(value):
    try:
        return range(int(value))
    except:
        return range(0)
